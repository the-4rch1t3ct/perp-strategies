#!/usr/bin/env python3
"""
Fetch 30 days of 5-minute OHLCV data for all memecoin symbols
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data.fetch_data import MemecoinDataFetcher
from datetime import datetime, timedelta
import time

# All symbols from AGENT_PROMPT_COMPACT.md
ALLOWED_SYMBOLS = [
    'DOGE/USDT:USDT',
    'WIF/USDT:USDT',
    'BRETT/USDT:USDT',
    'TURBO/USDT:USDT',
    'MEW/USDT:USDT',
    'BAN/USDT:USDT',
    'PNUT/USDT:USDT',
    'POPCAT/USDT:USDT',
    'MOODENG/USDT:USDT',
    'MEME/USDT:USDT',
    'NEIRO/USDT:USDT',
    'PEOPLE/USDT:USDT',
    'BOME/USDT:USDT',
    'DEGEN/USDT:USDT',
    'GOAT/USDT:USDT',
    'BANANA/USDT:USDT',
    'ACT/USDT:USDT',
    'DOGS/USDT:USDT',
    'CHILLGUY/USDT:USDT',
    'HIPPO/USDT:USDT',
    '1000SHIB/USDT:USDT',
    '1000PEPE/USDT:USDT',
    '1000BONK/USDT:USDT',
    '1000FLOKI/USDT:USDT',
    '1000CHEEMS/USDT:USDT',
    '1000000MOG/USDT:USDT',
    '1000SATS/USDT:USDT',
    '1000CAT/USDT:USDT',
    '1MBABYDOGE/USDT:USDT',
    '1000WHY/USDT:USDT',
    'KOMA/USDT:USDT',
]

def fetch_30day_5m_data():
    """Fetch 30 days of 5-minute data for all symbols"""
    fetcher = MemecoinDataFetcher()
    
    print("=" * 60)
    print("FETCHING 30 DAYS OF 5-MINUTE DATA")
    print("=" * 60)
    print()
    
    # Calculate start date (30 days ago)
    start_date = datetime.now() - timedelta(days=30)
    print(f"Start date: {start_date}")
    print(f"End date: {datetime.now()}")
    print(f"Timeframe: 5m")
    print(f"Total symbols: {len(ALLOWED_SYMBOLS)}")
    print()
    
    results = {}
    failed = []
    
    for i, symbol in enumerate(ALLOWED_SYMBOLS, 1):
        print(f"[{i}/{len(ALLOWED_SYMBOLS)}] Fetching {symbol}...")
        try:
            # Fetch 5-minute data
            # Binance allows up to 1000 candles per request
            # 30 days * 24 hours * 12 (5-min periods per hour) = 8640 candles
            # We need multiple requests
            
            df_list = []
            current_since = start_date
            max_candles_per_request = 1000
            
            while current_since < datetime.now():
                try:
                    df_chunk = fetcher.fetch_ohlcv(
                        symbol,
                        timeframe='5m',
                        since=current_since,
                        limit=max_candles_per_request
                    )
                    
                    if df_chunk.empty:
                        break
                    
                    df_list.append(df_chunk)
                    
                    # Move to next chunk (1000 candles * 5 minutes = 5000 minutes = ~3.5 days)
                    if len(df_chunk) > 0:
                        last_timestamp = df_chunk.index[-1]
                        current_since = last_timestamp + timedelta(minutes=5)
                    else:
                        break
                    
                    time.sleep(0.2)  # Rate limiting
                    
                except Exception as e:
                    print(f"    Warning: {e}")
                    break
            
            if df_list:
                # Combine all chunks
                df = pd.concat(df_list)
                df = df[~df.index.duplicated(keep='last')]  # Remove duplicates
                df = df.sort_index()
                
                # Filter to exactly 30 days
                end_date = datetime.now()
                df = df[(df.index >= start_date) & (df.index <= end_date)]
                
                if not df.empty:
                    # Save to CSV
                    safe_name = symbol.replace('/', '_').replace(':', '_')
                    filepath = f"data/{safe_name}_5m.csv"
                    df.to_csv(filepath)
                    results[symbol] = df
                    print(f"    ✓ Saved {len(df)} candles ({df.index.min()} to {df.index.max()})")
                else:
                    failed.append(symbol)
                    print(f"    ✗ No data after filtering")
            else:
                failed.append(symbol)
                print(f"    ✗ No data fetched")
                
        except Exception as e:
            print(f"    ✗ Failed: {e}")
            failed.append(symbol)
        
        time.sleep(0.3)  # Rate limiting between symbols
        print()
    
    print("=" * 60)
    print("FETCH COMPLETE")
    print("=" * 60)
    print(f"Successfully fetched: {len(results)}/{len(ALLOWED_SYMBOLS)}")
    print(f"Failed: {len(failed)}")
    
    if failed:
        print(f"\nFailed symbols: {', '.join(failed)}")
    
    # Show date ranges
    if results:
        print("\nDate ranges:")
        all_min = min(df.index.min() for df in results.values())
        all_max = max(df.index.max() for df in results.values())
        print(f"  Overall: {all_min} to {all_max}")
        print(f"  Days covered: {(all_max - all_min).days} days")
    
    return results

if __name__ == '__main__':
    import pandas as pd
    fetch_30day_5m_data()
