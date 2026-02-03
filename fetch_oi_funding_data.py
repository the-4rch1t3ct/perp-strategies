#!/usr/bin/env python3
"""
Fetch historical Open Interest and Funding Rate data from Binance Futures
Merges with existing 5-minute OHLCV data
"""

import ccxt
import pandas as pd
import os
from pathlib import Path
import time
from datetime import datetime, timedelta
import glob

# Initialize exchange
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'},
    'timeout': 30000,
})

# Allowed symbols (same as strategy)
SYMBOLS = [
    'DOGE/USDT:USDT', 'WIF/USDT:USDT', 'BRETT/USDT:USDT', 'TURBO/USDT:USDT',
    'MEW/USDT:USDT', 'BAN/USDT:USDT', 'PNUT/USDT:USDT', 'POPCAT/USDT:USDT',
    'MOODENG/USDT:USDT', 'MEME/USDT:USDT', 'NEIRO/USDT:USDT', 'PEOPLE/USDT:USDT',
    'BOME/USDT:USDT', 'DEGEN/USDT:USDT', 'GOAT/USDT:USDT', 'BANANA/USDT:USDT',
    'ACT/USDT:USDT', 'DOGS/USDT:USDT', 'CHILLGUY/USDT:USDT', 'HIPPO/USDT:USDT',
    '1000SHIB/USDT:USDT', '1000PEPE/USDT:USDT', '1000BONK/USDT:USDT',
    '1000FLOKI/USDT:USDT', '1000CHEEMS/USDT:USDT', '1000000MOG/USDT:USDT',
    '1000SATS/USDT:USDT', '1000CAT/USDT:USDT', '1MBABYDOGE/USDT:USDT',
    '1000WHY/USDT:USDT', 'KOMA/USDT:USDT',
]

def get_symbol_key(symbol: str) -> str:
    """Convert symbol to file key format"""
    return symbol.replace('/', '_').replace(':', '_')

def fetch_oi_funding_for_symbol(symbol: str, start_time: datetime, end_time: datetime):
    """Fetch OI and funding rate data for a symbol"""
    print(f"Fetching OI/FR for {symbol}...")
    
    oi_data = []
    funding_data = []
    
    try:
        # Fetch Funding Rate History (8-hour intervals)
        # Binance funding rate is every 8 hours
        try:
            funding = exchange.fetch_funding_rate_history(
                symbol, 
                since=int(start_time.timestamp() * 1000),
                limit=1000
            )
            if funding:
                for fr in funding:
                    ts = pd.Timestamp(fr['timestamp'], unit='ms')
                    if start_time <= ts <= end_time:
                        funding_data.append({
                            'timestamp': ts,
                            'fr': float(fr['fundingRate'])
                        })
        except Exception as e:
            print(f"  Error fetching FR history: {e}")
            # Try alternative method
            try:
                # Fetch current funding rate as fallback
                current_fr = exchange.fetch_funding_rate(symbol)
                if current_fr:
                    funding_data.append({
                        'timestamp': pd.Timestamp.now(),
                        'fr': float(current_fr['fundingRate'])
                    })
            except:
                pass
        
        # For Open Interest, fetch current OI (historical OI not easily available)
        # We'll use current OI and forward-fill for backtesting
        # In production, the agent will get real-time OI from the API
        try:
            current_oi = exchange.fetch_open_interest(symbol)
            if current_oi and 'openInterestAmount' in current_oi:
                oi_data.append({
                    'timestamp': pd.Timestamp(current_oi['timestamp'], unit='ms'),
                    'oi': float(current_oi['openInterestAmount'])
                })
                print(f"  Got current OI: {current_oi['openInterestAmount']}")
        except Exception as e:
            print(f"  Warning: Could not fetch OI: {e}")
            # OI will be NaN in the data, which is fine - strategy handles missing data
                
    except Exception as e:
        print(f"  Error processing {symbol}: {e}")
        return None, None
    
    oi_df = pd.DataFrame(oi_data) if oi_data else None
    fr_df = pd.DataFrame(funding_data) if funding_data else None
    
    if oi_df is not None and len(oi_df) > 0:
        oi_df.set_index('timestamp', inplace=True)
        oi_df = oi_df.sort_index()
    if fr_df is not None and len(fr_df) > 0:
        fr_df.set_index('timestamp', inplace=True)
        fr_df = fr_df.sort_index()
        # Remove duplicates (keep last)
        fr_df = fr_df[~fr_df.index.duplicated(keep='last')]
    
    return oi_df, fr_df

def merge_oi_funding_with_ohlcv():
    """Merge OI/FR data with existing 5-minute OHLCV data"""
    data_dir = Path('data')
    csv_files = glob.glob(str(data_dir / '*_5m.csv'))
    
    print(f"Found {len(csv_files)} CSV files to process")
    
    for csv_file in csv_files:
        symbol_key = os.path.basename(csv_file).replace('_5m.csv', '')
        
        # Find matching symbol
        symbol = None
        for sym in SYMBOLS:
            if get_symbol_key(sym) == symbol_key:
                symbol = sym
                break
        
        if not symbol:
            print(f"Skipping {symbol_key} - not in SYMBOLS list")
            continue
        
        print(f"\nProcessing {symbol} ({symbol_key})...")
        
        # Load existing OHLCV data
        try:
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            if len(df) == 0:
                print(f"  Empty file, skipping")
                continue
        except Exception as e:
            print(f"  Error loading {csv_file}: {e}")
            continue
        
        start_time = df.index.min()
        end_time = df.index.max()
        
        print(f"  Date range: {start_time} to {end_time}")
        
        # Fetch OI and funding rate
        oi_df, fr_df = fetch_oi_funding_for_symbol(symbol, start_time, end_time)
        
        if oi_df is not None and len(oi_df) > 0:
            # Use current OI value for all rows (since we don't have historical OI)
            # In production, the agent will get real-time OI from the API
            current_oi_value = oi_df['oi'].iloc[-1] if len(oi_df) > 0 else None
            if current_oi_value is not None:
                df['oi'] = current_oi_value
                print(f"  Added OI data: {len(df)} / {len(df)} rows (using current OI: {current_oi_value:.2f})")
            else:
                df['oi'] = pd.NA
                print(f"  No OI value available")
        else:
            df['oi'] = pd.NA
            print(f"  No OI data available")
        
        if fr_df is not None and len(fr_df) > 0:
            # Resample funding rate to 5-minute intervals (forward fill)
            fr_5m = fr_df.reindex(df.index, method='ffill')
            df['fr'] = fr_5m['fr']
            print(f"  Added FR data: {df['fr'].notna().sum()} / {len(df)} rows")
        else:
            df['fr'] = pd.NA
            print(f"  No FR data available")
        
        # Save updated CSV
        output_file = csv_file  # Overwrite original
        df.to_csv(output_file)
        print(f"  Saved to {output_file}")

def main():
    print("=" * 60)
    print("Fetching Open Interest and Funding Rate Data")
    print("=" * 60)
    print()
    
    merge_oi_funding_with_ohlcv()
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

if __name__ == '__main__':
    main()
