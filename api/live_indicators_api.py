"""
Live Indicators API for Memecoin Trading Strategy
Provides all required indicators in real-time via API endpoint
Uses api.wagmi.global for data fetching
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import httpx
from datetime import datetime, timedelta
import asyncio

app = FastAPI(title="Memecoin Trading Indicators API")

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

# Response models
class IndicatorData(BaseModel):
    symbol: str
    timestamp: str
    price: float
    volume: float
    indicators: Dict[str, float]
    signal_strength: Optional[float] = None
    entry_signal: Optional[str] = None  # 'LONG', 'SHORT', or None
    leverage: Optional[float] = None

class IndicatorsResponse(BaseModel):
    success: bool
    data: List[IndicatorData]
    timestamp: str

class SingleSymbolResponse(BaseModel):
    success: bool
    data: IndicatorData
    timestamp: str

# Indicator calculation functions
def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high_low = high - low
    high_close = abs(high - close.shift())
    low_close = abs(low - close.shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_momentum(close: pd.Series, period: int = 12) -> pd.Series:
    """Calculate Momentum (Rate of Change)"""
    return close.pct_change(periods=period)

def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """Calculate MACD"""
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }

def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate all required indicators for the strategy"""
    if len(df) < 50:  # Need enough data
        return {}
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # Get latest values
    latest_idx = -1
    
    # EMAs
    ema_fast = calculate_ema(close, 12)
    ema_slow = calculate_ema(close, 36)
    
    # RSI
    rsi = calculate_rsi(close, 14)
    
    # Momentum
    momentum = calculate_momentum(close, 12)
    
    # ATR
    atr = calculate_atr(high, low, close, 14)
    
    # Volume indicators
    volume_ma = volume.rolling(window=36).mean()
    volume_ratio = volume / volume_ma
    volume_percentile = volume.rolling(window=100).rank(pct=True) * 100
    
    # MACD
    macd_data = calculate_macd(close)
    
    # Trend strength
    trend_strength = abs(ema_fast - ema_slow) / ema_slow
    
    # Price position
    high_20 = high.rolling(window=20).max()
    low_20 = low.rolling(window=20).min()
    price_position = (close - low_20) / (high_20 - low_20)
    
    # Return latest values
    return {
        'ema_fast': float(ema_fast.iloc[latest_idx]) if not pd.isna(ema_fast.iloc[latest_idx]) else None,
        'ema_slow': float(ema_slow.iloc[latest_idx]) if not pd.isna(ema_slow.iloc[latest_idx]) else None,
        'rsi': float(rsi.iloc[latest_idx]) if not pd.isna(rsi.iloc[latest_idx]) else None,
        'momentum': float(momentum.iloc[latest_idx]) if not pd.isna(momentum.iloc[latest_idx]) else None,
        'atr': float(atr.iloc[latest_idx]) if not pd.isna(atr.iloc[latest_idx]) else None,
        'atr_pct': float((atr.iloc[latest_idx] / close.iloc[latest_idx]) * 100) if not pd.isna(atr.iloc[latest_idx]) else None,
        'volume_ma': float(volume_ma.iloc[latest_idx]) if not pd.isna(volume_ma.iloc[latest_idx]) else None,
        'volume_ratio': float(volume_ratio.iloc[latest_idx]) if not pd.isna(volume_ratio.iloc[latest_idx]) else None,
        'volume_percentile': float(volume_percentile.iloc[latest_idx]) if not pd.isna(volume_percentile.iloc[latest_idx]) else None,
        'macd': float(macd_data['macd'].iloc[latest_idx]) if not pd.isna(macd_data['macd'].iloc[latest_idx]) else None,
        'macd_signal': float(macd_data['signal'].iloc[latest_idx]) if not pd.isna(macd_data['signal'].iloc[latest_idx]) else None,
        'macd_histogram': float(macd_data['histogram'].iloc[latest_idx]) if not pd.isna(macd_data['histogram'].iloc[latest_idx]) else None,
        'trend_strength': float(trend_strength.iloc[latest_idx]) if not pd.isna(trend_strength.iloc[latest_idx]) else None,
        'price_position': float(price_position.iloc[latest_idx]) if not pd.isna(price_position.iloc[latest_idx]) else None,
    }

def calculate_signal_strength(indicators: Dict[str, float], direction: str = 'LONG') -> float:
    """Calculate signal strength"""
    if not all(k in indicators for k in ['momentum', 'volume_ratio', 'trend_strength', 'rsi']):
        return 0.0
    
    momentum_val = indicators['momentum']
    volume_ratio = indicators['volume_ratio']
    trend_strength = indicators['trend_strength']
    rsi = indicators['rsi']
    
    if direction == 'LONG':
        momentum_strength = min(momentum_val / (0.004 * 2.5), 1.0) if momentum_val > 0 else 0.0
        rsi_strength = min(max((rsi - 50) / 15, 0), 1.0)
    else:  # SHORT
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
    """Check entry conditions and return (signal, leverage)"""
    if not all(k in indicators for k in ['ema_fast', 'ema_slow', 'momentum', 'rsi', 'volume_ratio', 
                                         'volume_percentile', 'trend_strength', 'macd_histogram', 'price_position']):
        return None, None
    
    # Check LONG conditions
    long_core = (
        indicators['ema_fast'] > indicators['ema_slow'] and
        indicators['momentum'] > 0.004 and
        indicators['rsi'] > 45 and indicators['rsi'] < 65 and indicators['rsi'] > 50
    )
    
    long_filters = sum([
        indicators['trend_strength'] > 0.0008,
        indicators['volume_ratio'] > 1.08,
        indicators['macd_histogram'] > 0,
        indicators['price_position'] > 0.3
    ]) >= 2
    
    long_volume = (
        indicators['volume_ratio'] > 1.08 and
        indicators['volume_percentile'] > 25
    )
    
    long_price_move = abs(indicators['momentum']) > 0.002
    
    if long_core and long_filters and long_volume and long_price_move:
        strength = calculate_signal_strength(indicators, 'LONG')
        if strength > 0.25:
            leverage = 20.0 if strength >= 0.65 else (15.0 if strength >= 0.35 else 10.0)
            return 'LONG', leverage
    
    # Check SHORT conditions
    short_core = (
        indicators['ema_fast'] < indicators['ema_slow'] and
        indicators['momentum'] < -0.004 and
        indicators['rsi'] < 55 and indicators['rsi'] > 35 and indicators['rsi'] < 50
    )
    
    short_filters = sum([
        indicators['trend_strength'] > 0.0008,
        indicators['volume_ratio'] > 1.08,
        indicators['macd_histogram'] < 0,
        indicators['price_position'] < 0.7
    ]) >= 2
    
    short_volume = (
        indicators['volume_ratio'] > 1.08 and
        indicators['volume_percentile'] > 25
    )
    
    short_price_move = abs(indicators['momentum']) > 0.002
    
    if short_core and short_filters and short_volume and short_price_move:
        strength = calculate_signal_strength(indicators, 'SHORT')
        if strength > 0.25:
            leverage = 20.0 if strength >= 0.65 else (15.0 if strength >= 0.35 else 10.0)
            return 'SHORT', leverage
    
    return None, None

async def fetch_ohlcv_wagmi(symbol: str, timeframe: str = '5m', limit: int = 200) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data from api.wagmi.global"""
    try:
        # Convert symbol format for wagmi.global
        # Remove /USDT:USDT suffix and keep prefixes (1000, 1M, etc.)
        base_symbol = symbol.replace('/USDT:USDT', '')
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try wagmi.global API - common patterns
            # Pattern 1: /api/v1/ohlcv
            try:
                url = "https://api.wagmi.global/api/v1/ohlcv"
                params = {
                    'symbol': base_symbol,
                    'timeframe': timeframe,
                    'limit': limit,
                    'exchange': 'binance'
                }
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    # Handle different response formats
                    if isinstance(data, list):
                        df = pd.DataFrame(data)
                    elif 'data' in data and isinstance(data['data'], list):
                        df = pd.DataFrame(data['data'])
                    elif 'ohlcv' in data and isinstance(data['ohlcv'], list):
                        df = pd.DataFrame(data['ohlcv'])
                    else:
                        raise ValueError("Unexpected response format")
                    
                    # Standardize column names
                    if len(df.columns) >= 6:
                        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
                        df = df.dropna(subset=['timestamp'])
                        df.set_index('timestamp', inplace=True)
                        return df[['open', 'high', 'low', 'close', 'volume']]
            except Exception as e1:
                # Pattern 2: /v1/market/candles
                try:
                    url = "https://api.wagmi.global/v1/market/candles"
                    params = {
                        'symbol': base_symbol,
                        'interval': timeframe,
                        'limit': limit
                    }
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'candles' in data:
                            df = pd.DataFrame(data['candles'])
                            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
                            df = df.dropna(subset=['timestamp'])
                            df.set_index('timestamp', inplace=True)
                            return df[['open', 'high', 'low', 'close', 'volume']]
                except Exception as e2:
                    print(f"Wagmi pattern 2 failed: {e2}")
                    
    except Exception as e:
        print(f"Error fetching from wagmi.global: {e}")
    
    # Fallback to CCXT (Binance Futures)
    try:
        import ccxt
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if ohlcv:
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
    except Exception as e:
        print(f"Error fetching from CCXT: {e}")
    
    return None

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Memecoin Trading Indicators API",
        "version": "1.0.0",
        "endpoints": {
            "/indicators/{symbol}": "Get indicators for a single symbol",
            "/indicators": "Get indicators for all symbols",
            "/symbols": "List all allowed symbols"
        }
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
async def get_indicators_single(symbol: str):
    """Get live indicators for a single symbol"""
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not in allowed list")
    
    # Fetch data
    df = await fetch_ohlcv_wagmi(symbol, timeframe='5m', limit=200)
    
    if df is None or len(df) < 50:
        raise HTTPException(status_code=500, detail="Insufficient data or fetch error")
    
    # Calculate indicators
    indicators = calculate_all_indicators(df)
    
    if not indicators:
        raise HTTPException(status_code=500, detail="Failed to calculate indicators")
    
    # Check entry signals
    entry_signal, leverage = check_entry_conditions(indicators)
    signal_strength = None
    if entry_signal:
        signal_strength = calculate_signal_strength(indicators, entry_signal)
    
    # Prepare response
    latest = df.iloc[-1]
    data = IndicatorData(
        symbol=symbol,
        timestamp=df.index[-1].isoformat(),
        price=float(latest['close']),
        volume=float(latest['volume']),
        indicators=indicators,
        signal_strength=signal_strength,
        entry_signal=entry_signal,
        leverage=leverage
    )
    
    return SingleSymbolResponse(
        success=True,
        data=data,
        timestamp=datetime.now().isoformat()
    )

@app.get("/indicators", response_model=IndicatorsResponse)
async def get_indicators_all():
    """Get live indicators for all symbols"""
    results = []
    
    # Fetch all symbols in parallel
    tasks = [fetch_indicators_for_symbol(symbol) for symbol in ALLOWED_SYMBOLS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out errors
    valid_results = [r for r in results if isinstance(r, IndicatorData)]
    
    return IndicatorsResponse(
        success=True,
        data=valid_results,
        timestamp=datetime.now().isoformat()
    )

async def fetch_indicators_for_symbol(symbol: str) -> Optional[IndicatorData]:
    """Helper to fetch indicators for a single symbol"""
    try:
        df = await fetch_ohlcv_wagmi(symbol, timeframe='5m', limit=200)
        
        if df is None or len(df) < 50:
            return None
        
        indicators = calculate_all_indicators(df)
        
        if not indicators:
            return None
        
        entry_signal, leverage = check_entry_conditions(indicators)
        signal_strength = None
        if entry_signal:
            signal_strength = calculate_signal_strength(indicators, entry_signal)
        
        latest = df.iloc[-1]
        return IndicatorData(
            symbol=symbol,
            timestamp=df.index[-1].isoformat(),
            price=float(latest['close']),
            volume=float(latest['volume']),
            indicators=indicators,
            signal_strength=signal_strength,
            entry_signal=entry_signal,
            leverage=leverage
        )
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
