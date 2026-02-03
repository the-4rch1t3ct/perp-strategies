"""
Memecoin Perpetual Futures Data Fetcher
Fetches historical data from Binance Futures via CCXT
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json
from typing import List, Dict, Optional

# Memecoin symbols (Binance Futures format)
MEMECOINS = [
    'DOGE/USDT:USDT',
    '1000SHIB/USDT:USDT',
    '1000PEPE/USDT:USDT',
    'WIF/USDT:USDT',
    '1000BONK/USDT:USDT',
    '1000FLOKI/USDT:USDT',
    '1000SATS/USDT:USDT',
    'BOME/USDT:USDT',
    'MEME/USDT:USDT',
    '1000CAT/USDT:USDT',
    'BRETT/USDT:USDT',
    'TURBO/USDT:USDT',
    'MEW/USDT:USDT',
    'POPCAT/USDT:USDT',
    'PNUT/USDT:USDT',
    'DEGEN/USDT:USDT',
    'PEOPLE/USDT:USDT',
    'GOAT/USDT:USDT',
    'BANANA/USDT:USDT',
    'ACT/USDT:USDT',
]

# Privex-specific symbols from screenshots
PRIVEX_MEMECOINS = [
    'DOGS/USDT:USDT',
    'CHILLGUY/USDT:USDT',
    'HIPPO/USDT:USDT',
    '1000CHEEMS/USDT:USDT',
    '1000000MOG/USDT:USDT',
    '1MBABYDOGE/USDT:USDT',
    '1000WHY/USDT:USDT',
    'KOMA/USDT:USDT',
]

class MemecoinDataFetcher:
    """Fetches and stores memecoin perpetual futures data"""
    
    def __init__(self, exchange_name='binance', data_dir='data'):
        self.exchange = getattr(ccxt, exchange_name)({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use futures
            }
        })
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', 
                    since: Optional[datetime] = None, 
                    limit: int = 1000) -> pd.DataFrame:
        """
        Fetch OHLCV data for a symbol
        
        Args:
            symbol: Trading pair (e.g., 'DOGE/USDT:USDT')
            timeframe: '1m', '5m', '15m', '1h', '4h', '1d'
            since: Start datetime (default: 90 days ago)
            limit: Max candles per request
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if since is None:
            since = datetime.now() - timedelta(days=90)
        
        since_ms = int(since.timestamp() * 1000)
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol, 
                timeframe, 
                since=since_ms, 
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_funding_rate(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """Fetch historical funding rates"""
        try:
            # Binance funding rate history
            funding = self.exchange.fetch_funding_rate_history(symbol, limit=limit)
            if funding:
                df = pd.DataFrame(funding)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
        except Exception as e:
            print(f"Error fetching funding rate for {symbol}: {e}")
        return pd.DataFrame()
    
    def fetch_open_interest(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """Fetch open interest data"""
        try:
            oi = self.exchange.fetch_open_interest_history(symbol, timeframe='1h', limit=limit)
            if oi:
                df = pd.DataFrame(oi)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
        except Exception as e:
            print(f"Error fetching OI for {symbol}: {e}")
        return pd.DataFrame()
    
    def fetch_all_memecoins(self, timeframe: str = '1h', days: int = 90):
        """Fetch data for all memecoins"""
        results = {}
        failed = []
        
        all_symbols = MEMECOINS + PRIVEX_MEMECOINS
        
        for symbol in all_symbols:
            print(f"Fetching {symbol}...")
            try:
                df = self.fetch_ohlcv(symbol, timeframe, 
                                     since=datetime.now() - timedelta(days=days))
                
                if not df.empty:
                    # Save to CSV
                    safe_name = symbol.replace('/', '_').replace(':', '_')
                    filepath = os.path.join(self.data_dir, f"{safe_name}_{timeframe}.csv")
                    df.to_csv(filepath)
                    results[symbol] = df
                    print(f"  ✓ Saved {len(df)} candles to {filepath}")
                else:
                    failed.append(symbol)
                    
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                failed.append(symbol)
        
        # Save metadata
        metadata = {
            'fetched_at': datetime.now().isoformat(),
            'timeframe': timeframe,
            'days': days,
            'successful': list(results.keys()),
            'failed': failed,
            'total_symbols': len(all_symbols)
        }
        
        with open(os.path.join(self.data_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return results
    
    def load_data(self, symbol: str, timeframe: str = '1h') -> pd.DataFrame:
        """Load previously fetched data"""
        safe_name = symbol.replace('/', '_').replace(':', '_')
        filepath = os.path.join(self.data_dir, f"{safe_name}_{timeframe}.csv")
        
        if os.path.exists(filepath):
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            return df
        return pd.DataFrame()


if __name__ == '__main__':
    fetcher = MemecoinDataFetcher()
    
    print("Fetching memecoin perpetual futures data...")
    print("=" * 60)
    
    # Fetch 1h data for last 90 days
    data = fetcher.fetch_all_memecoins(timeframe='1h', days=90)
    
    print("\n" + "=" * 60)
    print(f"Successfully fetched {len(data)} symbols")
    print(f"Data saved to: {fetcher.data_dir}/")
