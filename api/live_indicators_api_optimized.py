"""
Optimized Live Indicators API for Memecoin Trading Strategy
- Low latency with caching
- Rate limit compliant
- Parallel data fetching
- All 31 symbols with complete indicators
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import httpx
from datetime import datetime, timedelta
import asyncio
from functools import lru_cache
import time
import os
from collections import deque

app = FastAPI(title="Memecoin Trading Indicators API - Optimized")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Allowed symbols
ALLOWED_SYMBOLS = [
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

# Rate limiting and caching
class RateLimiter:
    def __init__(self, max_calls: int = 10, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    async def acquire(self):
        now = time.time()
        # Remove old calls
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()
        
        self.calls.append(time.time())

# Global rate limiter (increased for better performance)
# Binance allows higher rate limits for public data
rate_limiter = RateLimiter(max_calls=20, period=1.0)  # 20 req/sec (increased from 10)

# Data cache with rolling refresh (staggered expiry)
data_cache = {}
cache_ttl = 60.0  # Maximum data age: 60 seconds - data must never be older than this
# Rolling refresh: Each symbol gets a random offset (0-15 seconds) so they don't all expire at once
# This ensures data is refreshed before it exceeds 60 seconds

# Cache hit tracking for performance monitoring
_cache_hits = 0
_cache_misses = 0

# Symbol-specific cache offsets for rolling refresh
_cache_offsets = {}

# Simplified response models - only core trading data
class TradingSignal(BaseModel):
    symbol: str
    price: float
    entry_signal: Optional[str] = None  # "LONG", "SHORT", or None
    signal_strength: Optional[float] = None  # 0.0-1.0
    leverage: Optional[float] = None  # 10x, 15x, or 20x
    stop_loss_price: Optional[float] = None  # Calculated stop loss level
    take_profit_price: Optional[float] = None  # Calculated take profit level
    exit_signal: Optional[str] = None  # "CLOSE_LONG", "CLOSE_SHORT", or None (for existing positions)
    data_age_seconds: Optional[float] = None  # How old is the latest candle

class TradingSignalsResponse(BaseModel):
    success: bool
    data: List[TradingSignal]
    timestamp: str
    latency_ms: float

class SingleSymbolResponse(BaseModel):
    success: bool
    data: TradingSignal
    timestamp: str
    latency_ms: float

# Optimized indicator calculations (vectorized)
def calculate_indicators_vectorized(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate all indicators using vectorized operations for speed"""
    if len(df) < 50:
        return {}
    
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values
    
    latest_idx = -1
    
    # EMAs (vectorized)
    alpha_fast = 2.0 / (12 + 1)
    alpha_slow = 2.0 / (36 + 1)
    ema_fast = pd.Series(close).ewm(alpha=alpha_fast, adjust=False).mean().values
    ema_slow = pd.Series(close).ewm(alpha=alpha_slow, adjust=False).mean().values
    
    # RSI (vectorized)
    delta = np.diff(close, prepend=close[0])
    gain = pd.Series(np.where(delta > 0, delta, 0)).rolling(14).mean().values
    loss = pd.Series(np.where(delta < 0, -delta, 0)).rolling(14).mean().values
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    # Momentum
    momentum = (close / np.roll(close, 12) - 1)
    momentum[0:12] = np.nan
    
    # ATR (vectorized)
    high_low = high - low
    high_close = np.abs(high - np.roll(close, 1))
    low_close = np.abs(low - np.roll(close, 1))
    tr = np.maximum(high_low, np.maximum(high_close, low_close))
    atr = pd.Series(tr).rolling(14).mean().values
    
    # Volume indicators
    volume_ma = pd.Series(volume).rolling(36).mean().values
    volume_ratio = volume / (volume_ma + 1e-10)
    volume_percentile = pd.Series(volume).rolling(100).rank(pct=True).values * 100
    
    # MACD
    macd_fast = pd.Series(close).ewm(span=12, adjust=False).mean().values
    macd_slow = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = macd_fast - macd_slow
    macd_signal = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - macd_signal
    
    # Trend strength
    trend_strength = np.abs(ema_fast - ema_slow) / (ema_slow + 1e-10)
    
    # Price position
    high_20 = pd.Series(high).rolling(20).max().values
    low_20 = pd.Series(low).rolling(20).min().values
    price_position = (close - low_20) / ((high_20 - low_20) + 1e-10)
    
    # Return latest values
    return {
        'ema_fast': float(ema_fast[latest_idx]) if not np.isnan(ema_fast[latest_idx]) else None,
        'ema_slow': float(ema_slow[latest_idx]) if not np.isnan(ema_slow[latest_idx]) else None,
        'rsi': float(rsi[latest_idx]) if not np.isnan(rsi[latest_idx]) else None,
        'momentum': float(momentum[latest_idx]) if not np.isnan(momentum[latest_idx]) else None,
        'atr': float(atr[latest_idx]) if not np.isnan(atr[latest_idx]) else None,
        'atr_pct': float((atr[latest_idx] / close[latest_idx]) * 100) if not np.isnan(atr[latest_idx]) else None,
        'volume_ma': float(volume_ma[latest_idx]) if not np.isnan(volume_ma[latest_idx]) else None,
        'volume_ratio': float(volume_ratio[latest_idx]) if not np.isnan(volume_ratio[latest_idx]) else None,
        'volume_percentile': float(volume_percentile[latest_idx]) if not np.isnan(volume_percentile[latest_idx]) else None,
        'macd': float(macd_line[latest_idx]) if not np.isnan(macd_line[latest_idx]) else None,
        'macd_signal': float(macd_signal[latest_idx]) if not np.isnan(macd_signal[latest_idx]) else None,
        'macd_histogram': float(macd_hist[latest_idx]) if not np.isnan(macd_hist[latest_idx]) else None,
        'trend_strength': float(trend_strength[latest_idx]) if not np.isnan(trend_strength[latest_idx]) else None,
        'price_position': float(price_position[latest_idx]) if not np.isnan(price_position[latest_idx]) else None,
    }

def calculate_signal_strength(indicators: Dict[str, float], direction: str = 'LONG') -> float:
    """Calculate signal strength"""
    if not all(k in indicators and indicators[k] is not None 
               for k in ['momentum', 'volume_ratio', 'trend_strength', 'rsi']):
        return 0.0
    
    momentum_val = indicators['momentum']
    volume_ratio = indicators['volume_ratio']
    trend_strength = indicators['trend_strength']
    rsi = indicators['rsi']
    
    if direction == 'LONG':
        momentum_strength = min(momentum_val / (0.004 * 2.5), 1.0) if momentum_val > 0 else 0.0
        rsi_strength = min(max((rsi - 50) / 15, 0), 1.0)
    else:
        momentum_strength = min(abs(momentum_val) / (0.004 * 2.5), 1.0) if momentum_val < 0 else 0.0
        rsi_strength = min(max((50 - rsi) / 15, 0), 1.0)
    
    volume_strength = min((volume_ratio - 1.0) / 1.5, 1.0) if volume_ratio > 1.0 else 0.0
    trend_strength_norm = min(trend_strength / 0.3, 1.0)
    
    signal_strength = (
        momentum_strength * 0.35 +
        volume_strength * 0.25 +
        trend_strength_norm * 0.25 +
        rsi_strength * 0.15
    )
    
    return max(0.0, min(1.0, signal_strength))

def check_entry_conditions(indicators: Dict[str, float]) -> tuple:
    """Check entry conditions"""
    if not all(k in indicators and indicators[k] is not None 
               for k in ['ema_fast', 'ema_slow', 'momentum', 'rsi', 'volume_ratio', 
                         'volume_percentile', 'trend_strength', 'macd_histogram', 'price_position']):
        return None, None
    
    # LONG
    long_core = (
        indicators['ema_fast'] > indicators['ema_slow'] and
        indicators['momentum'] > 0.004 and
        45 < indicators['rsi'] < 65 and indicators['rsi'] > 50
    )
    
    long_filters = sum([
        indicators['trend_strength'] > 0.0008,
        indicators['volume_ratio'] > 1.08,
        indicators['macd_histogram'] > 0,
        indicators['price_position'] > 0.3
    ]) >= 2
    
    if long_core and long_filters and indicators['volume_ratio'] > 1.08 and indicators['volume_percentile'] > 25 and abs(indicators['momentum']) > 0.002:
        strength = calculate_signal_strength(indicators, 'LONG')
        if strength > 0.25:
            leverage = 20.0 if strength >= 0.65 else (15.0 if strength >= 0.35 else 10.0)
            return 'LONG', leverage
    
    # SHORT
    short_core = (
        indicators['ema_fast'] < indicators['ema_slow'] and
        indicators['momentum'] < -0.004 and
        35 < indicators['rsi'] < 55 and indicators['rsi'] < 50
    )
    
    short_filters = sum([
        indicators['trend_strength'] > 0.0008,
        indicators['volume_ratio'] > 1.08,
        indicators['macd_histogram'] < 0,
        indicators['price_position'] < 0.7
    ]) >= 2
    
    if short_core and short_filters and indicators['volume_ratio'] > 1.08 and indicators['volume_percentile'] > 25 and abs(indicators['momentum']) > 0.002:
        strength = calculate_signal_strength(indicators, 'SHORT')
        if strength > 0.25:
            leverage = 20.0 if strength >= 0.65 else (15.0 if strength >= 0.35 else 10.0)
            return 'SHORT', leverage
    
    return None, None

# Global CCXT exchange instance (reuse for performance)
_ccxt_exchange = None

def get_ccxt_exchange():
    """Get or create CCXT exchange instance (singleton)"""
    global _ccxt_exchange
    if _ccxt_exchange is None:
        import ccxt
        _ccxt_exchange = ccxt.binance({
            'enableRateLimit': False,  # We handle rate limiting ourselves
            'options': {'defaultType': 'future'},
            'timeout': 5000,  # 5 second timeout
        })
    return _ccxt_exchange

async def fetch_ohlcv_ccxt(symbol: str, timeframe: str = '5m', limit: int = 200) -> Optional[pd.DataFrame]:
    """Fetch OHLCV using CCXT (optimized with connection reuse)"""
    try:
        # Rate limit
        await rate_limiter.acquire()
        
        # Get exchange instance (reused)
        exchange = get_ccxt_exchange()
        
        # Fetch with timeout
        ohlcv = await asyncio.to_thread(exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
        
        if ohlcv and len(ohlcv) > 0:
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
    except Exception as e:
        print(f"CCXT error for {symbol}: {e}")
    return None

async def fetch_ohlcv_wagmi(symbol: str, timeframe: str = '5m', limit: int = 200, force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from api.wagmi.global with fallback
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe (default: 5m)
        limit: Number of candles to fetch
        force_refresh: If True, bypasses cache
    """
    global _cache_hits, _cache_misses, _cache_offsets
    base_symbol = symbol.replace('/USDT:USDT', '')
    
    # Check cache first (unless force refresh)
    cache_key = f"{base_symbol}_{timeframe}"
    
    # Get or create cache offset for this symbol (rolling refresh)
    if cache_key not in _cache_offsets:
        import random
        # Stagger cache expiry: 0-15 second offset per symbol
        # This creates rolling refreshes, ensuring data is refreshed before it exceeds 60 seconds
        _cache_offsets[cache_key] = random.uniform(0, 15)
    
    cache_offset = _cache_offsets[cache_key]
    
    if not force_refresh and cache_key in data_cache:
        cached_data, cached_time = data_cache[cache_key]
        # Check actual candle data age, not just cache timestamp
        if len(cached_data) > 0:
            latest_timestamp = cached_data.index[-1]
            if latest_timestamp.tzinfo is None:
                age_seconds = (datetime.now() - latest_timestamp).total_seconds()
            else:
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                age_seconds = (now_utc - latest_timestamp).total_seconds()
            
            # CRITICAL: Data must never be older than 60 seconds
            # Account for cache offset to ensure rolling refresh happens before 60s
            max_allowed_age = cache_ttl - cache_offset  # Refresh before hitting 60s limit
            
            if age_seconds < max_allowed_age:
                _cache_hits += 1
                return cached_data
            else:
                # Data is too old, force refresh
                if cache_key in data_cache:
                    del data_cache[cache_key]
                _cache_misses += 1
    
    # Skip CSV files - they may be stale, always fetch fresh from API
    
    # Always fetch fresh from CCXT (Binance) - most reliable source
    # Skip api.wagmi.global as it may return stale data
    ccxt_df = await fetch_ohlcv_ccxt(symbol, timeframe, limit)
    if ccxt_df is not None and len(ccxt_df) > 0:
        # Verify data is fresh (must be < 60 seconds old)
        latest_timestamp = ccxt_df.index[-1]
        if latest_timestamp.tzinfo is None:
            age_seconds = (datetime.now() - latest_timestamp).total_seconds()
        else:
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            age_seconds = (now_utc - latest_timestamp).total_seconds()
        
        # CRITICAL: Only use if data is less than 60 seconds old
        if age_seconds < cache_ttl:
            # Cache it with current timestamp
            # The offset is already set, so this symbol will expire at a different time
            data_cache[cache_key] = (ccxt_df, time.time())
            _cache_misses += 1
            return ccxt_df
        else:
            print(f"Warning: CCXT data for {symbol} is {age_seconds:.1f} seconds old (exceeds {cache_ttl}s limit)")
    
    # Fallback to wagmi.global only if CCXT fails
    try:
        await rate_limiter.acquire()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try wagmi.global endpoints
            endpoints = [
                f"https://api.wagmi.global/api/v1/ohlcv?symbol={base_symbol}&timeframe={timeframe}&limit={limit}&exchange=binance",
                f"https://api.wagmi.global/v1/market/candles?symbol={base_symbol}&interval={timeframe}&limit={limit}",
            ]
            
            for url in endpoints:
                try:
                    response = await client.get(url, timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        df = None
                        
                        if isinstance(data, list):
                            df = pd.DataFrame(data)
                        elif 'data' in data:
                            df = pd.DataFrame(data['data'])
                        elif 'candles' in data:
                            df = pd.DataFrame(data['candles'])
                        elif 'ohlcv' in data:
                            df = pd.DataFrame(data['ohlcv'])
                        
                        if df is not None and len(df) > 0:
                            # Standardize columns
                            if len(df.columns) >= 6:
                                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
                                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
                                df = df.dropna(subset=['timestamp'])
                                df.set_index('timestamp', inplace=True)
                                df = df[['open', 'high', 'low', 'close', 'volume']]
                                
                                # Check data freshness
                                latest_timestamp = df.index[-1]
                                if latest_timestamp.tzinfo is None:
                                    age_seconds = (datetime.now() - latest_timestamp).total_seconds()
                                else:
                                    from datetime import timezone
                                    now_utc = datetime.now(timezone.utc)
                                    age_seconds = (now_utc - latest_timestamp).total_seconds()
                                
                                # CRITICAL: Only use if data is less than 60 seconds old
                                if age_seconds < cache_ttl:
                                    # Cache with current timestamp (offset already set)
                                    data_cache[cache_key] = (df, time.time())
                                    return df
                                else:
                                    print(f"Warning: Wagmi data for {symbol} is {age_seconds:.1f} seconds old (exceeds {cache_ttl}s limit), skipping")
                except Exception as e:
                    print(f"Wagmi endpoint error for {symbol}: {e}")
                    continue
    except Exception as e:
        print(f"Wagmi error for {symbol}: {e}")
    
    # If we get here, both CCXT and wagmi failed or returned stale data
    return None

def check_exit_conditions(indicators: Dict[str, float], current_price: float, entry_price: float, entry_direction: str) -> Optional[str]:
    """Check if existing position should be closed
    Returns: "CLOSE_LONG", "CLOSE_SHORT", or None
    """
    if not all(k in indicators and indicators[k] is not None 
               for k in ['atr', 'ema_fast', 'ema_slow', 'macd_histogram']):
        return None
    
    atr = indicators['atr']
    
    # Trend reversal check
    if entry_direction == 'LONG':
        # Close LONG if: EMA crossover OR MACD histogram flips negative
        if indicators['ema_fast'] < indicators['ema_slow'] or indicators['macd_histogram'] < 0:
            return "CLOSE_LONG"
    else:  # SHORT
        # Close SHORT if: EMA crossover OR MACD histogram flips positive
        if indicators['ema_fast'] > indicators['ema_slow'] or indicators['macd_histogram'] > 0:
            return "CLOSE_SHORT"
    
    return None

async def process_symbol(symbol: str, force_refresh: bool = False) -> Optional[TradingSignal]:
    """Process a single symbol and return simplified trading signal data"""
    try:
        df = await fetch_ohlcv_wagmi(symbol, timeframe='5m', limit=200, force_refresh=force_refresh)
        
        if df is None or len(df) < 50:
            return None
        
        indicators = calculate_indicators_vectorized(df)
        if not indicators or indicators.get('atr') is None:
            return None
        
        # Always calculate signal strength for both directions (even if no entry signal)
        long_strength = calculate_signal_strength(indicators, 'LONG')
        short_strength = calculate_signal_strength(indicators, 'SHORT')
        
        # Check entry conditions
        entry_signal, leverage = check_entry_conditions(indicators)
        signal_strength = None
        if entry_signal:
            signal_strength = long_strength if entry_signal == 'LONG' else short_strength
        else:
            # Even if no entry signal, show the stronger signal strength for reference
            signal_strength = max(long_strength, short_strength) if max(long_strength, short_strength) > 0.1 else None
        
        latest = df.iloc[-1]
        current_price = float(latest['close'])
        latest_timestamp = df.index[-1]
        atr = indicators['atr']
        
        # Calculate stop loss and take profit levels (if entry signal exists)
        stop_loss_price = None
        take_profit_price = None
        if entry_signal:
            if entry_signal == 'LONG':
                stop_loss_price = round(current_price - (1.5 * atr), 8)
                take_profit_price = round(current_price + (2.5 * atr), 8)
            else:  # SHORT
                stop_loss_price = round(current_price + (1.5 * atr), 8)
                take_profit_price = round(current_price - (2.5 * atr), 8)
        
        # Check exit conditions for existing positions (trend reversal)
        # Note: This is a simplified check - in production, you'd track actual positions
        exit_signal = None
        if indicators.get('ema_fast') and indicators.get('ema_slow'):
            # Check for trend reversal (could indicate exit for existing positions)
            if indicators['ema_fast'] < indicators['ema_slow'] and indicators.get('macd_histogram', 0) < 0:
                exit_signal = "CLOSE_LONG"  # Signal to close any LONG positions
            elif indicators['ema_fast'] > indicators['ema_slow'] and indicators.get('macd_histogram', 0) > 0:
                exit_signal = "CLOSE_SHORT"  # Signal to close any SHORT positions
        
        # Calculate data age (how old is the latest candle)
        if latest_timestamp.tzinfo is None:
            data_age_seconds = (datetime.now() - latest_timestamp).total_seconds()
        else:
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            data_age_seconds = (now_utc - latest_timestamp).total_seconds()
        
        # CRITICAL: Reject data older than 60 seconds
        if data_age_seconds > cache_ttl:
            print(f"Rejecting {symbol}: data is {data_age_seconds:.1f} seconds old (exceeds {cache_ttl}s limit)")
            return None
        
        return TradingSignal(
            symbol=symbol,
            price=current_price,
            entry_signal=entry_signal,
            signal_strength=round(signal_strength, 4) if signal_strength else None,
            leverage=leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            exit_signal=exit_signal,
            data_age_seconds=round(data_age_seconds, 1)
        )
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Memecoin Trading Indicators API",
        "version": "2.0.0-optimized",
        "endpoints": {
            "/indicators": "Get trading signals for all 31 symbols (simplified - only core data)",
            "/indicators/{symbol}": "Get trading signal for single symbol",
            "/symbols": "List all allowed symbols"
        },
        "features": [
            "Simplified response - only core trading data",
            "Pre-calculated stop loss and take profit levels",
            "Entry/exit signals ready to use",
            "Low latency (caching, vectorized calculations)",
            "Rate limit compliant (20 req/sec)",
            "1-minute cache TTL with rolling refreshes"
        ]
    }

@app.get("/symbols")
async def get_symbols():
    """Get list of all allowed trading symbols"""
    return {
        "success": True,
        "symbols": ALLOWED_SYMBOLS,
        "count": len(ALLOWED_SYMBOLS)
    }

@app.get("/indicators/{symbol}", response_model=SingleSymbolResponse)
async def get_indicators_single(symbol: str, refresh: bool = False):
    """Get live indicators for a single symbol
    
    Args:
        symbol: Trading symbol (e.g., DOGE/USDT:USDT)
        refresh: If True, bypasses cache and forces fresh data fetch
    """
    start_time = time.time()
    
    # Force cache clear for this symbol if refresh requested
    if refresh:
        base_symbol = symbol.replace('/USDT:USDT', '')
        cache_key = f"{base_symbol}_5m"
        if cache_key in data_cache:
            del data_cache[cache_key]
    
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not in allowed list")
    
    data = await process_symbol(symbol)
    
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch or calculate indicators")
    
    latency_ms = (time.time() - start_time) * 1000
    
    return SingleSymbolResponse(
        success=True,
        data=data,
        timestamp=datetime.now().isoformat(),
        latency_ms=round(latency_ms, 2)
    )

@app.get("/indicators", response_model=TradingSignalsResponse)
async def get_indicators_all(refresh: bool = False):
    """Get live indicators for all 31 symbols (optimized parallel fetch)
    
    Args:
        refresh: If True, bypasses cache and forces fresh data fetch
    """
    start_time = time.time()
    
    # Force cache clear if refresh requested
    if refresh:
        data_cache.clear()
    
    # Process all symbols in parallel with timeout per symbol
    async def process_with_timeout(symbol):
        try:
            return await asyncio.wait_for(process_symbol(symbol, force_refresh=refresh), timeout=8.0)
        except asyncio.TimeoutError:
            print(f"Timeout processing {symbol}")
            return None
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            return None
    
    # Process in larger batches for better parallelism
    # CCXT can handle more concurrent requests
    batch_size = 20  # Increased from 10
    results = []
    
    for i in range(0, len(ALLOWED_SYMBOLS), batch_size):
        batch = ALLOWED_SYMBOLS[i:i+batch_size]
        batch_results = await asyncio.gather(*[process_with_timeout(symbol) for symbol in batch], return_exceptions=True)
        
        # Filter valid results
        valid = [r for r in batch_results if isinstance(r, TradingSignal)]
        results.extend(valid)
        
        # Minimal delay between batches (only if not last batch)
        if i + batch_size < len(ALLOWED_SYMBOLS):
            await asyncio.sleep(0.02)  # Very small delay
    
    latency_ms = (time.time() - start_time) * 1000
    
    # Calculate cache statistics
    cache_stats = {
        "cache_size": len(data_cache),
        "cache_ttl_seconds": cache_ttl,
        "refresh_requested": refresh
    }
    
    return TradingSignalsResponse(
        success=True,
        data=results,
        timestamp=datetime.now().isoformat(),
        latency_ms=round(latency_ms, 2),
        cache_info=cache_stats
    )

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Allow port override via environment variable
    port = int(os.environ.get('PORT', 8001))
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        workers=1,  # Single worker for rate limiting
        loop="asyncio"
    )
