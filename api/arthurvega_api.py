#!/usr/bin/env python3
"""
ArthurVega API - Modular Trading Data Endpoints
Endpoint: /arthurvega/fundingOI
Returns Open Interest and Funding Rate for all symbols
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import ccxt
from datetime import datetime, timedelta
import asyncio
from collections import deque
import time

app = FastAPI(title="ArthurVega API - Modular Trading Data")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Allowed symbols
SYMBOLS = [
    'ETH/USDT:USDT', 'SOL/USDT:USDT', 'BNB/USDT:USDT', 'XRP/USDT:USDT',
    'TRX/USDT:USDT', 'DOGE/USDT:USDT', 'ADA/USDT:USDT', 'BCH/USDT:USDT',
    'LINK/USDT:USDT', 'XMR/USDT:USDT', 'XLM/USDT:USDT', 'ZEC/USDT:USDT',
    'HYPE/USDT:USDT', 'LTC/USDT:USDT', 'SUI/USDT:USDT', 'AVAX/USDT:USDT',
]

# Compact response model - OI, Funding, and Funding History
class VantageSignal(BaseModel):
    s: str  # symbol
    oi: Optional[float] = None  # open_interest
    fr: Optional[float] = None  # funding_rate (current)
    fr_1h_ago: Optional[float] = None  # funding_rate from 1 hour ago
    fr_diff: Optional[float] = None  # difference: fr - fr_1h_ago

class VantageResponse(BaseModel):
    ok: bool  # success
    d: List[VantageSignal]  # data
    t: str  # timestamp

# Rate limiter
class RateLimiter:
    def __init__(self, max_calls: int = 20, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    async def acquire(self):
        now = time.time()
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()
        self.calls.append(time.time())

# Rate limiter: Binance allows 20 req/sec (1200 req/min) for public endpoints
# We need 2 requests per symbol (OI + funding) = 62 requests total
# At 20 req/sec, that's ~3 seconds for all symbols
# Safe refresh: 15 seconds = 4 refreshes/min = 248 req/min (well within 1200 limit)
rate_limiter = RateLimiter(max_calls=20, period=1.0)

# Cache with aggressive refresh - 15 seconds for maximum freshness
oi_funding_cache = {}
cache_ttl = 15.0  # Refresh every 15 seconds (4x per minute, 248 req/min total)

# CCXT exchange (singleton)
_exchange = None

def get_exchange():
    global _exchange
    if _exchange is None:
        _exchange = ccxt.binance({
            'enableRateLimit': False,
            'options': {'defaultType': 'future'},
            'timeout': 5000,
        })
    return _exchange


async def fetch_oi_funding(symbol: str) -> tuple:
    """Fetch Open Interest, Current Funding Rate, and Funding Rate from 1 hour ago"""
    cache_key = symbol
    if cache_key in oi_funding_cache:
        cached_data, cached_time = oi_funding_cache[cache_key]
        age_seconds = (datetime.now() - cached_time).total_seconds()
        if age_seconds < cache_ttl:  # Use cache_ttl (15 seconds)
            return cached_data
    
    try:
        exchange = get_exchange()
        
        # Fetch OI (rate limited)
        await rate_limiter.acquire()
        oi_data = await asyncio.to_thread(exchange.fetch_open_interest, symbol)
        oi = oi_data.get('openInterestAmount', None) if oi_data else None
        
        # Fetch current funding rate (rate limited)
        await rate_limiter.acquire()
        funding_data = await asyncio.to_thread(exchange.fetch_funding_rate, symbol)
        funding_rate = funding_data.get('fundingRate', None) if funding_data else None
        
        # Fetch funding rate from 1 hour ago
        funding_rate_1h_ago = None
        try:
            await rate_limiter.acquire()
            # Calculate timestamp for 1 hour ago (in milliseconds)
            one_hour_ago_ms = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
            
            # Fetch funding rate history (get entries from last 24 hours to ensure we have data)
            # Funding rates update every 8 hours, so we need enough history
            funding_history = await asyncio.to_thread(
                exchange.fetch_funding_rate_history,
                symbol,
                since=one_hour_ago_ms - (24 * 60 * 60 * 1000),  # Start 24 hours ago
                limit=20  # Get enough entries to find the one active 1h ago
            )
            
            if funding_history and len(funding_history) > 0:
                # Find the funding rate that was active 1 hour ago
                # This is the most recent funding rate that was set BEFORE 1 hour ago
                target_time = one_hour_ago_ms
                active_entry = None
                
                # Sort by timestamp (oldest first) to find the one that was active at target_time
                sorted_history = sorted(funding_history, key=lambda x: x.get('timestamp', 0))
                
                for entry in sorted_history:
                    entry_time = entry.get('timestamp', 0)
                    # Find the most recent entry that was set before or at 1 hour ago
                    if entry_time <= target_time:
                        active_entry = entry
                    else:
                        # We've passed the target time, use the last entry before it
                        break
                
                # If we found an entry, use it (even if it's older than 1h, it's what was active then)
                if active_entry:
                    funding_rate_1h_ago = active_entry.get('fundingRate', None)
                elif len(sorted_history) > 0:
                    # Fallback: use the oldest entry if no entry was before 1h ago
                    # (shouldn't happen, but handle edge case)
                    funding_rate_1h_ago = sorted_history[0].get('fundingRate', None)
        except Exception as e:
            print(f"Warning: Could not fetch 1h ago funding rate for {symbol}: {e}")
            # Continue without 1h ago data
        
        # Calculate difference
        fr_diff = None
        if funding_rate is not None and funding_rate_1h_ago is not None:
            fr_diff = funding_rate - funding_rate_1h_ago
        
        result = (oi, funding_rate, funding_rate_1h_ago, fr_diff)
        oi_funding_cache[cache_key] = (result, datetime.now())
        return result
    except Exception as e:
        print(f"OI/Funding error {symbol}: {e}")
        # Return cached data if available, even if expired
        if cache_key in oi_funding_cache:
            cached_data, _ = oi_funding_cache[cache_key]
            return cached_data
        return None, None, None, None

@app.get("/arthurvega/fundingOI", response_model=VantageResponse)
async def get_funding_oi():
    """Funding & Open Interest endpoint
    Returns:
    - oi: Current open interest
    - fr: Current funding rate
    - fr_1h_ago: Funding rate from 1 hour ago (most recent rate active at that time)
    - fr_diff: Difference between current and 1h ago funding rate (fr - fr_1h_ago)
    
    Refreshes every 15 seconds, fetches all symbols in parallel
    Rate limit: ~496 req/min (well within Binance's 1200 req/min limit)
    """
    results = []
    
    # Fetch all OI/Funding data in parallel with staggered rate limiting
    # This ensures we stay within Binance's 20 req/sec limit
    tasks = []
    for symbol in SYMBOLS:
        tasks.append((symbol, asyncio.create_task(fetch_oi_funding(symbol))))
    
    # Process results as they complete
    for symbol, oi_funding_task in tasks:
        try:
            oi_funding_result = await oi_funding_task
            if isinstance(oi_funding_result, tuple) and len(oi_funding_result) >= 2:
                oi = oi_funding_result[0] if len(oi_funding_result) > 0 else None
                funding_rate = oi_funding_result[1] if len(oi_funding_result) > 1 else None
                funding_rate_1h_ago = oi_funding_result[2] if len(oi_funding_result) > 2 else None
                fr_diff = oi_funding_result[3] if len(oi_funding_result) > 3 else None
            else:
                oi, funding_rate, funding_rate_1h_ago, fr_diff = None, None, None, None
            
            results.append(VantageSignal(
                s=symbol,
                oi=round(oi, 2) if oi is not None else None,
                fr=round(funding_rate, 6) if funding_rate is not None else None,
                fr_1h_ago=round(funding_rate_1h_ago, 6) if funding_rate_1h_ago is not None else None,
                fr_diff=round(fr_diff, 6) if fr_diff is not None else None,
            ))
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            # Return cached data if available, otherwise None
            cache_key = symbol
            if cache_key in oi_funding_cache:
                cached_data, _ = oi_funding_cache[cache_key]
                if isinstance(cached_data, tuple) and len(cached_data) >= 2:
                    oi = cached_data[0] if len(cached_data) > 0 else None
                    funding_rate = cached_data[1] if len(cached_data) > 1 else None
                    funding_rate_1h_ago = cached_data[2] if len(cached_data) > 2 else None
                    fr_diff = cached_data[3] if len(cached_data) > 3 else None
                    results.append(VantageSignal(
                        s=symbol,
                        oi=round(oi, 2) if oi is not None else None,
                        fr=round(funding_rate, 6) if funding_rate is not None else None,
                        fr_1h_ago=round(funding_rate_1h_ago, 6) if funding_rate_1h_ago is not None else None,
                        fr_diff=round(fr_diff, 6) if fr_diff is not None else None,
                    ))
                    continue
            results.append(VantageSignal(s=symbol))
    
    return VantageResponse(
        ok=True,
        d=results,
        t=datetime.now().isoformat(),
    )

@app.get("/")
async def root():
    return {
        "name": "ArthurVega API",
        "endpoints": {
            "/arthurvega/fundingOI": "Open Interest & Funding Rate data"
        },
        "description": "Modular API for trading data"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
