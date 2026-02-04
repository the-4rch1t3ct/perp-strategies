#!/usr/bin/env python3
"""
Liquidation Heatmap API
Provides real-time liquidation cluster data via API endpoint
Accessible at api.wagmi-global.eu
"""

import sys
import os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_api = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _api)   # so hyperliquid_batch imports when run as script
sys.path.append(_root)      # so predictive_liquidation_heatmap imports

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
import logging
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
from fastapi import Body

# Import predictive heatmap (replaces post-mortem approach)
from predictive_liquidation_heatmap import PredictiveLiquidationHeatmap, LiquidationLevel
# Hyperliquid batch (same response shape, HL data source)
try:
    from hyperliquid_batch import fetch_hyperliquid_batch_data, SUPPORTED_SYMBOLS_HL, SYMBOL_TO_COIN, _enhanced_confidence_score
except ImportError:
    fetch_hyperliquid_batch_data = None
    SUPPORTED_SYMBOLS_HL = []
    SYMBOL_TO_COIN = {}
    _enhanced_confidence_score = None

app = FastAPI(title="Liquidation Heatmap API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global predictive heatmap instance
heatmap: Optional[PredictiveLiquidationHeatmap] = None
heatmap_lock = threading.Lock()
TREND_CACHE = {}

# Batching system for performance optimization
BATCH_SIZE = 10  # Process assets in batches of 10
BATCH_CACHE = {}  # Cache for batch results
BATCH_UPDATE_LOCK = threading.Lock()
BATCH_LAST_UPDATE = {}  # Track last update time per batch

# Performance optimizations - Balanced for freshness and performance
HYPERLIQUID_DATA_CACHE = None  # Cache Hyperliquid data fetch
HYPERLIQUID_DATA_CACHE_TIME = 0
# Reduced to 1.5s for fresher prices while maintaining performance (clusters can be slightly stale)
HYPERLIQUID_DATA_CACHE_TTL = 1.5  # Cache Hyperliquid data for 1.5 seconds (shared across all requests)
# Reduced to 5s for fresher signals while maintaining cache benefits
BATCH_CACHE_TTL = 5  # Balance between freshness (5s) and performance

# Rate limiting protection
# Hyperliquid: 1200 weight/minute per IP
# - metaAndAssetCtxs: weight 20, ~40/min = 800 weight/min
# - candleSnapshot: weight 20 each, need to throttle to stay under 1200
HYPERLIQUID_RATE_LIMIT_WEIGHT_PER_MIN = 1200
HYPERLIQUID_META_WEIGHT = 20  # metaAndAssetCtxs weight
HYPERLIQUID_CANDLE_WEIGHT = 20  # candleSnapshot weight per call
HYPERLIQUID_CANDLE_THROTTLE_DELAY = 0.1  # Delay between candleSnapshot calls (seconds) to prevent spikes
KLINES_CACHE_STAGGER_SEC = 2  # Stagger klines cache expiration to prevent simultaneous cache misses

# Supported symbols (Binance Futures format - USDT pairs)
SUPPORTED_SYMBOLS = [
    'ETHUSDT',   # Ethereum
    'SOLUSDT',   # Solana
    'BNBUSDT',   # Binance Coin
    'XRPUSDT',   # Ripple
    'TRXUSDT',   # Tron
    'DOGEUSDT',  # Dogecoin
    'ADAUSDT',   # Cardano
    'BCHUSDT',   # Bitcoin Cash
    'LINKUSDT',  # Chainlink
    'XMRUSDT',   # Monero
    'ASTERUSDT', 'HYPEUSDT', 'SUIUSDT', 'PUMPUSDT',  # HL/Binance clusters
    # Tier 1 - High Liquidity, Major Coins
    'BTCUSDT',   # Bitcoin
    'MATICUSDT', # Polygon
    'AVAXUSDT',  # Avalanche
    # Tier 2 - Strong Additions
    'ATOMUSDT',  # Cosmos
    'DOTUSDT',   # Polkadot
    'UNIUSDT',   # Uniswap
    'LTCUSDT',   # Litecoin
    # Tier 3 - L2s
    'ARBUSDT',   # Arbitrum
    'OPUSDT',    # Optimism
    # Tier 4 - Emerging L1s
    'APTUSDT',   # Aptos
    'INJUSDT',   # Injective
    'TIAUSDT',   # Celestia
    # Tier 5 - High-Volume Meme Coins
    'PEPEUSDT',  # Pepe
    'WIFUSDT',   # dogwifhat
    # Batch 2 - Additional High-Quality Assets (21 more to reach 50)
    # Tier 1 - Major Coins
    'ETCUSDT',   # Ethereum Classic
    'ALGOUSDT',  # Algorand
    'NEARUSDT',  # NEAR Protocol
    'ICPUSDT',   # Internet Computer
    'FILUSDT',   # Filecoin (replaces FTM - not available for perp)
    'JTOUSDT',   # Jupiter (replaces MYRO - not available for perp)
    'RUNEUSDT',  # THORChain (replaces MKR - not available for perp)
    # Tier 2 - DeFi Tokens
    'AAVEUSDT',  # Aave
    'COMPUSDT',  # Compound
    'CRVUSDT',   # Curve
    'SNXUSDT',   # Synthetix
    'GMXUSDT',   # GMX
    'DYDXUSDT',  # dYdX
    # Tier 3 - Layer 2s & Scaling
    'STRKUSDT',  # Starknet
    'ZROUSDT',   # LayerZero
    'METISUSDT', # Metis
    # Tier 4 - Emerging L1s
    'SEIUSDT',   # Sei
    'SUPERUSDT', # Superchain
    'TNSRUSDT',  # Tensor
    # Tier 5 - High-Volume Memes
    'BONKUSDT',  # Bonk
    'FLOKIUSDT', # Floki
    'SHIBUSDT',  # Shiba Inu
]

# Response models (updated for predictive levels)
class ClusterData(BaseModel):
    price_level: float
    side: str
    liquidation_count: int
    total_notional: float  # Open Interest USD value
    strength: float
    distance_from_price: float
    cluster_id: int
    last_updated: str
    leverage_tier: Optional[float] = None  # Average leverage for this cluster

class HeatmapResponse(BaseModel):
    success: bool
    symbol: str
    current_price: Optional[float] = None
    clusters: List[ClusterData]
    timestamp: str
    total_clusters: int

class SymbolListResponse(BaseModel):
    success: bool
    symbols: List[str]
    count: int

def initialize_heatmap():
    """Initialize global predictive heatmap instance"""
    global heatmap
    
    with heatmap_lock:
        if heatmap is None:
            heatmap = PredictiveLiquidationHeatmap(
                leverage_tiers=[100, 50, 25, 10, 5],  # Common leverage levels
                price_bucket_pct=0.005,  # 0.5% price buckets (reduced noise)
                min_oi_threshold=25000,  # Absolute OI floor (USD)
                min_oi_threshold_pct=0.02,  # Relative OI floor (% of total OI)
                min_cluster_distance_pct=0.3,  # Minimum 0.3% distance between clusters
                update_interval=3.0  # Recalc levels every 3s (uses cached prices/OI)
            )
            
            # Start predictive heatmap for all supported symbols
            heatmap.start(symbols=SUPPORTED_SYMBOLS)
            
            print(f"✅ Initialized PREDICTIVE heatmap with {len(SUPPORTED_SYMBOLS)} symbols")
            print(f"   Calculating liquidation levels BEFORE they occur")
            print(f"   Leverage tiers: {heatmap.leverage_tiers}")

# Price updates are now handled internally by PredictiveLiquidationHeatmap
# No need for separate background task

# Initialize on startup
@app.on_event("startup")
async def startup_event():
    initialize_heatmap()
    # Rolling trend refresh: keep TREND_CACHE warm in sync with batch updates (one batch every 5s).
    threading.Thread(target=_rolling_trend_refresh_worker, daemon=True).start()
    # Parallel warmup: fill trend cache for first 2 batches so first request is fast (trend is mandatory).
    def _parallel_warm_trend():
        batches = [SUPPORTED_SYMBOLS[i:i + BATCH_SIZE] for i in range(0, len(SUPPORTED_SYMBOLS), BATCH_SIZE)]
        warm_symbols = []
        for b in batches[:2]:  # first 2 batches
            warm_symbols.extend(b)
        with ThreadPoolExecutor(max_workers=TREND_ROLLING_WORKERS) as ex:
            for _ in ex.map(get_mtf_trend, warm_symbols):
                pass
    threading.Thread(target=_parallel_warm_trend, daemon=True).start()
    print("🚀 Predictive Liquidation Heatmap API started")
    print("   Showing RISK ZONES before liquidations occur")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the heatmap UI"""
    html_path = os.path.join(os.path.dirname(__file__), "liquidation_heatmap_ui.html")
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Liquidation Heatmap API</h1><p>UI not found</p>")

@app.get("/api/symbols", response_model=SymbolListResponse)
async def get_symbols():
    """Get list of supported symbols"""
    return SymbolListResponse(
        success=True,
        symbols=SUPPORTED_SYMBOLS,
        count=len(SUPPORTED_SYMBOLS)
    )

@app.get("/api/heatmap/{symbol}", response_model=HeatmapResponse)
async def get_heatmap(
    symbol: str,
    min_strength: float = Query(0.0, ge=0.0, le=1.0, description="Minimum cluster strength"),
    max_distance: float = Query(10.0, ge=0.0, le=50.0, description="Maximum distance from price (%)")
):
    """
    Get liquidation clusters for a symbol
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        min_strength: Minimum cluster strength (0-1)
        max_distance: Maximum distance from current price (%)
    """
    # Normalize symbol
    symbol = symbol.upper().replace('/', '').replace('USDT:USDT', 'USDT')
    
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not supported")
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        
        # Get predictive liquidation levels
        levels = heatmap.get_levels(symbol, min_strength=min_strength, max_distance=max_distance)
        current_price = heatmap.current_prices.get(symbol)
        
        # Convert to response format
        filtered_clusters = []
        for level in levels:
            filtered_clusters.append(ClusterData(
                price_level=level.price_level,
                side=level.side,
                liquidation_count=level.liquidation_count,
                total_notional=level.open_interest,  # OI USD value
                strength=level.strength,
                distance_from_price=level.distance_from_price,
                cluster_id=level.cluster_id,
                last_updated=level.last_updated.isoformat(),
                leverage_tier=level.leverage_tier
            ))
        
        return HeatmapResponse(
            success=True,
            symbol=symbol,
            current_price=current_price,
            clusters=filtered_clusters,
            timestamp=datetime.now().isoformat(),
            total_clusters=len(filtered_clusters)
        )

@app.get("/api/heatmap/{symbol}/best", response_model=ClusterData)
async def get_best_cluster(
    symbol: str,
    min_strength: float = Query(0.6, ge=0.0, le=1.0)
):
    """Get best trading cluster for a symbol"""
    symbol = symbol.upper().replace('/', '').replace('USDT:USDT', 'USDT')
    
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not supported")
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        
        # Get all levels and find the strongest one
        levels = heatmap.get_levels(symbol, min_strength=min_strength, max_distance=10.0)
        
        if not levels:
            raise HTTPException(status_code=404, detail="No suitable cluster found")
        
        # Find best cluster (highest strength, closest to price)
        best = max(levels, key=lambda x: (x.strength, -x.distance_from_price))
        
        return ClusterData(
            price_level=best.price_level,
            side=best.side,
            liquidation_count=best.liquidation_count,
            total_notional=best.open_interest,  # Use open_interest field
            strength=best.strength,
            distance_from_price=best.distance_from_price,
            cluster_id=best.cluster_id,
            last_updated=best.last_updated.isoformat(),
            leverage_tier=best.leverage_tier
        )

@app.get("/api/stats")
async def get_stats():
    """Get overall statistics and debug info"""
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        
        # Get predictive heatmap stats
        oi_data_summary = {}
        for symbol in SUPPORTED_SYMBOLS[:10]:  # Check first 10 symbols
            if symbol in heatmap.open_interest_data:
                oi_data_summary[symbol] = {
                    "total_oi_usd": heatmap.open_interest_data[symbol].get('total_oi_usd', 0),
                    "long_short_ratio": heatmap.open_interest_data[symbol].get('long_short_ratio', 1.0)
                }
        
        stats = {
            "total_symbols": len(SUPPORTED_SYMBOLS),
            "active_symbols": len([s for s in SUPPORTED_SYMBOLS if s in heatmap.liquidation_levels]),
            "total_clusters": sum(len(levels) for levels in heatmap.liquidation_levels.values()),
            "last_update": datetime.now().isoformat(),
            "debug": {
                "heatmap_running": heatmap.running,
                "open_interest_summary": oi_data_summary,
                "config": {
                    "leverage_tiers": heatmap.leverage_tiers,
                    "price_bucket_pct": heatmap.price_bucket_pct,
                    "min_oi_threshold": heatmap.min_oi_threshold,
                    "update_interval": heatmap.update_interval
                },
                "type": "PREDICTIVE"  # Indicates this is predictive, not post-mortem
            }
        }
        
        return {"success": True, "stats": stats}

# ============================================================================
# TRADING STRATEGY ENDPOINTS (Recommended Data Feed)
# ============================================================================

class TradingSignalResponse(BaseModel):
    """Trading signal response"""
    symbol: str
    current_price: float
    signal: Dict  # {direction, entry, stop_loss, take_profit, confidence, risk_reward, reason}
    cluster_data: Optional[Dict] = None
    timestamp: str

class SupportResistanceResponse(BaseModel):
    """Support/Resistance levels response"""
    symbol: str
    current_price: float
    support: List[Dict]
    resistance: List[Dict]
    timestamp: str

class MarketSentimentResponse(BaseModel):
    """Market sentiment response"""
    symbol: str
    sentiment: str
    long_short_ratio: float
    total_oi_usd: float
    long_oi_usd: Optional[float] = None
    short_oi_usd: Optional[float] = None
    interpretation: str
    bias_strength: str

@app.get("/api/trading-signal/{symbol}", response_model=TradingSignalResponse)
async def get_trading_signal(
    symbol: str,
    min_strength: float = Query(0.6, ge=0.0, le=1.0),
    max_distance: float = Query(3.0, ge=0.0, le=10.0)
):
    """
    Get pre-computed trading signal for a symbol
    
    Returns ready-to-use trading signal with entry, stop loss, and take profit levels
    """
    symbol = symbol.upper().replace('/', '').replace('USDT:USDT', 'USDT')
    
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not supported")
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        
        levels = heatmap.get_levels(symbol, min_strength=min_strength, max_distance=max_distance)
        current_price = heatmap.current_prices.get(symbol, 0)
        
        if not levels or not current_price:
            return TradingSignalResponse(
                symbol=symbol,
                current_price=current_price,
                signal={
                    "direction": "NEUTRAL",
                    "entry": current_price,
                    "stop_loss": None,
                    "take_profit": None,
                    "confidence": 0.0,
                    "risk_reward": None,
                    "reason": "No strong clusters found"
                },
                timestamp=datetime.now().isoformat()
            )
        
        # Separate clusters by side and position
        long_clusters_below = [l for l in levels if l.side == 'long' and l.price_level < current_price]
        short_clusters_above = [l for l in levels if l.side == 'short' and l.price_level > current_price]
        
        # Sort by strength
        long_clusters_below.sort(key=lambda x: x.strength, reverse=True)
        short_clusters_above.sort(key=lambda x: x.strength, reverse=True)
        
        # Strategy: Trade towards strongest cluster (SL aligned with trader: ATR-based dynamic)
        sl_pct = _sl_pct_for_rr(symbol, current_price)
        if sl_pct <= 0:
            sl_pct = ESTIMATED_SL_PCT
        signal_data = None
        cluster_data = None
        
        if short_clusters_above and short_clusters_above[0].strength >= min_strength:
            strongest_short = short_clusters_above[0]
            distance = strongest_short.distance_from_price
            
            if distance < max_distance:
                # Enter LONG, target short liquidation cluster
                entry = current_price
                stop_loss = current_price * (1 - sl_pct / 100.0)
                take_profit = strongest_short.price_level * (1 + TP_CLUSTER_OFFSET_PCT / 100.0)  # TP above cluster (targeting short liquidations)
                
                risk = entry - stop_loss
                reward = take_profit - entry
                risk_reward = reward / risk if risk > 0 else 0
                
                signal_data = {
                    "direction": "LONG",
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "confidence": strongest_short.strength,
                    "risk_reward": round(risk_reward, 2),
                    "reason": f"Strong short liquidation cluster at ${strongest_short.price_level:.2f} "
                             f"(strength: {strongest_short.strength:.2f}, OI: ${strongest_short.open_interest:,.0f})"
                }
                cluster_data = {
                    "price_level": strongest_short.price_level,
                    "side": strongest_short.side,
                    "strength": strongest_short.strength,
                    "distance_from_price": strongest_short.distance_from_price,
                    "open_interest": strongest_short.open_interest
                }
        
        elif long_clusters_below and long_clusters_below[0].strength >= min_strength:
            strongest_long = long_clusters_below[0]
            distance = strongest_long.distance_from_price
            
            if distance < max_distance:
                # Enter SHORT, target long liquidation cluster
                entry = current_price
                stop_loss = current_price * (1 + sl_pct / 100.0)
                take_profit = strongest_long.price_level * (1 - TP_CLUSTER_OFFSET_PCT / 100.0)  # TP below cluster (targeting long liquidations)
                
                risk = stop_loss - entry
                reward = entry - take_profit
                risk_reward = reward / risk if risk > 0 else 0
                
                signal_data = {
                    "direction": "SHORT",
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "confidence": strongest_long.strength,
                    "risk_reward": round(risk_reward, 2),
                    "reason": f"Strong long liquidation cluster at ${strongest_long.price_level:.2f} "
                             f"(strength: {strongest_long.strength:.2f}, OI: ${strongest_long.open_interest:,.0f})"
                }
                cluster_data = {
                    "price_level": strongest_long.price_level,
                    "side": strongest_long.side,
                    "strength": strongest_long.strength,
                    "distance_from_price": strongest_long.distance_from_price,
                    "open_interest": strongest_long.open_interest
                }
        
        if not signal_data:
            signal_data = {
                "direction": "NEUTRAL",
                "entry": current_price,
                "stop_loss": None,
                "take_profit": None,
                "confidence": 0.0,
                "risk_reward": None,
                "reason": "No immediate trading opportunities found"
            }
        
        return TradingSignalResponse(
            symbol=symbol,
            current_price=current_price,
            signal=signal_data,
            cluster_data=cluster_data,
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/levels/{symbol}", response_model=SupportResistanceResponse)
async def get_support_resistance(
    symbol: str,
    min_strength: float = Query(0.3, ge=0.0, le=1.0),
    max_distance: float = Query(10.0, ge=0.0, le=50.0)
):
    """
    Get support and resistance levels for a symbol
    
    Support = Long clusters below current price
    Resistance = Short clusters above current price
    """
    symbol = symbol.upper().replace('/', '').replace('USDT:USDT', 'USDT')
    
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not supported")
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        
        levels = heatmap.get_levels(symbol, min_strength=min_strength, max_distance=max_distance)
        current_price = heatmap.current_prices.get(symbol, 0)
        
        # Support levels (long clusters below price, sorted by price descending)
        support = sorted(
            [l for l in levels if l.side == 'long' and l.price_level < current_price],
            key=lambda x: x.price_level,
            reverse=True
        )[:5]  # Top 5 support levels
        
        # Resistance levels (short clusters above price, sorted by price ascending)
        resistance = sorted(
            [l for l in levels if l.side == 'short' and l.price_level > current_price],
            key=lambda x: x.price_level
        )[:5]  # Top 5 resistance levels
        
        return SupportResistanceResponse(
            symbol=symbol,
            current_price=current_price,
            support=[
                {
                    "price": l.price_level,
                    "strength": l.strength,
                    "oi_usd": l.open_interest,
                    "distance_pct": l.distance_from_price
                } for l in support
            ],
            resistance=[
                {
                    "price": l.price_level,
                    "strength": l.strength,
                    "oi_usd": l.open_interest,
                    "distance_pct": l.distance_from_price
                } for l in resistance
            ],
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/sentiment/{symbol}", response_model=MarketSentimentResponse)
async def get_market_sentiment(symbol: str):
    """
    Get market sentiment based on Open Interest data
    
    Analyzes long/short ratio to determine market bias
    """
    symbol = symbol.upper().replace('/', '').replace('USDT:USDT', 'USDT')
    
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not supported")
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        
        oi_data = heatmap.open_interest_data.get(symbol, {})
        
        if not oi_data:
            return MarketSentimentResponse(
                symbol=symbol,
                sentiment="UNKNOWN",
                long_short_ratio=1.0,
                total_oi_usd=0.0,
                interpretation="No OI data available",
                bias_strength="UNKNOWN"
            )
        
        long_short_ratio = oi_data.get('long_short_ratio', 1.0)
        total_oi = oi_data.get('total_oi_usd', 0)
        long_oi = oi_data.get('long_oi_usd', 0)
        short_oi = oi_data.get('short_oi_usd', 0)
        
        # Determine sentiment (adaptive thresholds based on funding trend strength)
        bull, bear, bull_high, bear_high = _sentiment_thresholds(oi_data)
        if long_short_ratio > bull:
            sentiment = "BULLISH_BIAS"
            bias_strength = "HIGH" if long_short_ratio > bull_high else "MODERATE"
            interpretation = f"More long positions ({long_short_ratio:.2f}:1) - Short liquidations more likely on price rise"
        elif long_short_ratio < bear:
            sentiment = "BEARISH_BIAS"
            bias_strength = "HIGH" if long_short_ratio < bear_high else "MODERATE"
            interpretation = f"More short positions ({1/long_short_ratio:.2f}:1) - Long liquidations more likely on price fall"
        else:
            sentiment = "NEUTRAL"
            bias_strength = "LOW"
            interpretation = f"Balanced long/short ratio ({long_short_ratio:.2f}:1) - No clear bias"
        
        return MarketSentimentResponse(
            symbol=symbol,
            sentiment=sentiment,
            long_short_ratio=long_short_ratio,
            total_oi_usd=total_oi,
            long_oi_usd=long_oi,
            short_oi_usd=short_oi,
            interpretation=interpretation,
            bias_strength=bias_strength
        )

# ============================================================================
# COMPACT API - 2 ENDPOINTS ONLY (All Essential Data)
# ============================================================================

class CompactTradeResponse(BaseModel):
    """Compact trading data - all essential info in one response"""
    symbol: str
    price: float
    signal: Dict  # {dir, entry, sl, tp, conf, rr} - primary (best) direction
    levels: Dict  # {support: [prices], resistance: [prices]}
    sentiment: Dict  # {bias, lsr, oi}
    clusters: Dict  # {best: {price, side, str, dist}, count}
    trend: Optional[Dict] = None  # {5m, 15m, 5m_diff, 15m_diff, status}
    ts: str  # timestamp
    signal_long: Optional[Dict] = None   # {dir, entry, sl, tp, conf, rr} when long has valid clusters
    signal_short: Optional[Dict] = None  # {dir, entry, sl, tp, conf, rr} when short has valid clusters

class SymbolTradeData(BaseModel):
    """Per-symbol trade data in batch response. price is always present (last price, refreshed on request)."""
    price: float  # last price (refreshed from Binance on request); 0.0 if unavailable
    signal: Dict
    levels: Optional[Dict] = None
    sentiment: Optional[Dict] = None
    clusters: Optional[Dict] = None

    class Config:
        extra = "allow"

class BatchTradeResponse(BaseModel):
    """Batch trading data response"""
    results: Dict[str, SymbolTradeData]  # symbol -> compact trade data (includes price)
    ts: str  # Timestamp (HH:MM:SS)
    data_age_ms: Optional[int] = None  # Age of Hyperliquid data in milliseconds (for freshness tracking)

# Reject signals where TP is too close to entry (poor cluster data, not a real setup)
# HL impact levels are often 0.1–0.5% away; 0.25% minimum TP distance allows direction signals while filtering noise
MIN_TP_DISTANCE_PCT = 0.25
TP_CLUSTER_OFFSET_PCT = 0.3  # take profit just before/after cluster
# Minimum distance from current price for cluster to be actionable
MIN_CLUSTER_DISTANCE_PCT = 0.0

# Minimum risk:reward to emit LONG/SHORT (below this we return NEUTRAL). HL impact clusters are often close;
# 0.35 allows trend-aligned signals from close clusters while filtering very poor RR.
MIN_RR_FOR_SIGNAL = 0.35

# Stop Loss estimation for RR calculation
ESTIMATED_SL_PCT = 1.5  # Estimated SL % for RR calculation (matches trader's ATR-based approach)

# Adaptive sentiment bands (use funding trend strength when available)
SENTIMENT_BASE_DEVIATION = 0.20
SENTIMENT_MIN_DEVIATION = 0.06
SENTIMENT_HIGH_MULTIPLIER = 1.5

def _round_price(price: float) -> float:
    """
    Round price with appropriate precision based on price level.
    Matches Hyperliquid exchange precision to avoid losing significant digits.
    - Price >= 100: 2 decimals (e.g., ETH: 2263.7, BTC: 77330.0)
    - Price >= 10: 2 decimals (e.g., SOL: 101.03)
    - Price >= 1: 4 decimals (e.g., XRP: 1.5871, LINK: 9.5444)
    - Price >= 0.1: 5 decimals (e.g., TRX: 0.28262, DOGE: 0.10629, ADA: 0.29528)
    - Price >= 0.01: 5 decimals (e.g., TNSR: 0.04856)
    - Price >= 0.001: 6 decimals (e.g., MYRO: 0.015813, SEI: 0.087675)
    - Price < 0.001: 7 decimals (e.g., PUMP: 0.00238)
    """
    if not price or price <= 0:
        return 0.0
    
    if price >= 100.0:
        return round(price, 2)  # High-value coins: 2 decimals
    elif price >= 10.0:
        return round(price, 2)  # Mid-value coins: 2 decimals
    elif price >= 1.0:
        return round(price, 4)  # Low-value coins: 4 decimals (XRP, LINK, etc.)
    elif price >= 0.1:
        return round(price, 5)  # Very low-value coins: 5 decimals (TRX, DOGE, ADA)
    elif price >= 0.01:
        return round(price, 5)  # Micro coins: 5 decimals (TNSR)
    elif price >= 0.001:
        return round(price, 6)  # Nano coins: 6 decimals (MYRO, SEI)
    else:
        return round(price, 7)  # Pico coins: 7 decimals


def _sentiment_thresholds(oi_data: Dict) -> tuple:
    """Return (bull, bear, bull_high, bear_high) thresholds for sentiment."""
    trend_strength = 0.0
    if isinstance(oi_data, dict):
        ts = oi_data.get("funding_trend_strength")
        if isinstance(ts, (int, float)):
            trend_strength = max(0.0, min(1.0, float(ts)))
    deviation = SENTIMENT_BASE_DEVIATION - (
        (SENTIMENT_BASE_DEVIATION - SENTIMENT_MIN_DEVIATION) * trend_strength
    )
    bull = 1.0 + deviation
    bear = 1.0 - deviation
    bull_high = 1.0 + (deviation * SENTIMENT_HIGH_MULTIPLIER)
    bear_high = 1.0 - (deviation * SENTIMENT_HIGH_MULTIPLIER)
    return bull, bear, bull_high, bear_high

# Multi-timeframe trend filter (fast confirmation for short-horizon entries)
TREND_FILTER_ENABLED = True
TREND_FAIL_OPEN = False  # block signals if trend data is unavailable
TREND_TIMEFRAMES = ["5m", "15m"]
TREND_EMA_FAST = 9
TREND_EMA_SLOW = 21
TREND_NEUTRAL_BAND_PCT = 0.05  # % diff between EMAs to consider a trend
TREND_CACHE_TTL_SEC = 55
TREND_STALE_FALLBACK_SEC = 6 * 3600  # allow stale trend fallback when live fetch fails
TREND_WARMUP_DELAY_SEC = 0.05  # small delay to avoid bursty warmup calls
TREND_WARN_COOLDOWN_SEC = 60  # min seconds between same-symbol trend failure warnings
# Rolling trend refresh: same cycle as batch cache so trend is always warm when batch is served
TREND_ROLLING_INTERVAL_SEC = BATCH_CACHE_TTL  # refresh one batch of trends every 5s
TREND_ROLLING_WORKERS = 4  # parallel workers for trend refresh (avoid rate-limit spike)
BINANCE_FAPI_URL = "https://fapi.binance.com"
HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"
ATR_CACHE = {}
ATR_CACHE_TTL_SEC = 55
ATR_INTERVAL = "5m"
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
ATR_FALLBACK_PCT = 0.02
SL_BUFFER_PCT = 0.001


def _levels_with_distance_for_price(levels: List[LiquidationLevel], current_price: float) -> List[LiquidationLevel]:
    """Recompute distance_from_price for each level using current_price (e.g. when levels are from Binance/HL)."""
    if not levels or not current_price or current_price <= 0:
        return levels
    from dataclasses import replace
    out = []
    for l in levels:
        dist_pct = abs(l.price_level - current_price) / current_price * 100.0
        out.append(replace(l, distance_from_price=dist_pct))
    return out

def _ema(values: List[float], period: int) -> Optional[float]:
    if not values or len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = (v * k) + (ema * (1 - k))
    return ema

def _fetch_klines_hyperliquid(symbol: str, interval: str, limit: int = 120) -> List[float]:
    """Fetch OHLC closes from Hyperliquid (prioritized for trading venue)."""
    if not SYMBOL_TO_COIN:
        return []
    coin = SYMBOL_TO_COIN.get(symbol)
    if not coin:
        return []
    
    # Map interval to Hyperliquid format
    interval_map = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "4h", "1d": "1d"
    }
    hl_interval = interval_map.get(interval)
    if not hl_interval:
        return []
    
    try:
        # Calculate time range (limit candles back from now)
        import time
        end_time_ms = int(time.time() * 1000)
        # Approximate milliseconds per candle
        ms_per_candle = {
            "1m": 60000, "5m": 300000, "15m": 900000,
            "1h": 3600000, "4h": 14400000, "1d": 86400000
        }
        ms_per = ms_per_candle.get(hl_interval, 60000)
        start_time_ms = end_time_ms - (limit * ms_per)
        
        # Hyperliquid requires nested "req" object
        response = requests.post(
            HYPERLIQUID_INFO_URL,
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": hl_interval,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms
                }
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            # HL format: {"t": start_time, "c": close, ...}; sort by t for chronological order (EMA needs oldest-first)
            pairs = []
            for candle in data:
                try:
                    t = candle.get("t")
                    c = candle.get("c")
                    if t is not None and c is not None:
                        pairs.append((int(t), float(c)))
                except (TypeError, ValueError):
                    continue
            if pairs:
                pairs.sort(key=lambda x: x[0])
                return [c for _t, c in pairs]
    except Exception:
        pass
    return []

# Cache for OHLC to avoid redundant ATR calls
def _fetch_ohlc_hyperliquid(symbol: str, interval: str, limit: int = 120) -> List[tuple]:
    """Fetch OHLC tuples from Hyperliquid (prioritized for trading venue)."""
    if not SYMBOL_TO_COIN:
        return []
    coin = SYMBOL_TO_COIN.get(symbol)
    if not coin:
        return []

    interval_map = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "4h", "1d": "1d"
    }
    hl_interval = interval_map.get(interval)
    if not hl_interval:
        return []

    try:
        end_time_ms = int(time.time() * 1000)
        ms_per_candle = {
            "1m": 60000, "5m": 300000, "15m": 900000,
            "1h": 3600000, "4h": 14400000, "1d": 86400000
        }
        ms_per = ms_per_candle.get(hl_interval, 60000)
        start_time_ms = end_time_ms - (limit * ms_per)
        response = requests.post(
            HYPERLIQUID_INFO_URL,
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": hl_interval,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms
                }
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            rows = []
            for candle in data:
                try:
                    t = candle.get("t")
                    h = candle.get("h")
                    l = candle.get("l")
                    c = candle.get("c")
                    if None not in (t, h, l, c):
                        rows.append((int(t), float(h), float(l), float(c)))
                except (TypeError, ValueError):
                    continue
            if rows:
                rows.sort(key=lambda x: x[0])
                return [(h, l, c) for _t, h, l, c in rows]
    except Exception:
        pass
    return []


def _fetch_ohlc(symbol: str, interval: str, limit: int = 120) -> List[tuple]:
    """Fetch OHLC tuples: try Hyperliquid first, fallback to Binance."""
    time.sleep(HYPERLIQUID_CANDLE_THROTTLE_DELAY)
    ohlc = _fetch_ohlc_hyperliquid(symbol, interval, limit)
    if ohlc:
        return ohlc
    for endpoint in ["/fapi/v1/klines", "/fapi/v3/klines"]:
        try:
            response = requests.get(
                f"{BINANCE_FAPI_URL}{endpoint}",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=3
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                rows = []
                for k in data:
                    try:
                        rows.append((float(k[2]), float(k[3]), float(k[4])))
                    except Exception:
                        continue
                if rows:
                    return rows
        except Exception:
            continue
    return []


def _compute_atr(ohlc: List[tuple], period: int) -> Optional[float]:
    if not ohlc or len(ohlc) < period + 1:
        return None
    trs = []
    prev_close = None
    for h, l, c in ohlc:
        if prev_close is None:
            tr = h - l
        else:
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def _get_atr(symbol: str) -> Optional[float]:
    now = time.time()
    cached = ATR_CACHE.get(symbol)
    if cached and (now - cached.get("ts", 0)) < ATR_CACHE_TTL_SEC:
        return cached.get("atr")
    ohlc = _fetch_ohlc(symbol, ATR_INTERVAL, ATR_PERIOD + 10)
    atr = _compute_atr(ohlc, ATR_PERIOD)
    ATR_CACHE[symbol] = {"atr": atr, "ts": now}
    return atr


def _sl_pct_for_rr(symbol: Optional[str], entry_price: float) -> float:
    if not symbol or not entry_price or entry_price <= 0:
        return 0.0
    atr = _get_atr(symbol)
    if (atr is None or atr <= 0) and ATR_FALLBACK_PCT and ATR_FALLBACK_PCT > 0:
        atr = entry_price * ATR_FALLBACK_PCT
    if not atr or atr <= 0:
        return 0.0
    sl_dist = atr * ATR_MULTIPLIER
    sl_pct = (sl_dist / entry_price) * 100.0
    if SL_BUFFER_PCT and SL_BUFFER_PCT > 0:
        sl_pct += SL_BUFFER_PCT * 100.0
    return sl_pct

# Cache for klines to avoid redundant API calls
KLINES_CACHE = {}
KLINES_CACHE_TTL = 30  # Cache klines for 30 seconds

def _fetch_klines(symbol: str, interval: str, limit: int = 120) -> List[float]:
    """Fetch OHLC closes: try Hyperliquid first (trading venue), fallback to Binance. Uses caching with staggered expiration."""
    cache_key = f"{symbol}_{interval}_{limit}"
    now = time.time()
    
    # Check cache first with staggered expiration (rate limit protection)
    cached = KLINES_CACHE.get(cache_key)
    if cached:
        cache_age = now - cached.get("ts", 0)
        # Stagger cache expiration to prevent simultaneous cache misses
        # Add small offset based on symbol hash to spread expiration times
        symbol_hash = hash(symbol) % 1000  # 0-999
        staggered_ttl = KLINES_CACHE_TTL + (symbol_hash / 1000.0 * KLINES_CACHE_STAGGER_SEC)
        if cache_age < staggered_ttl:
            return cached.get("data", [])
    
    # Try Hyperliquid first (trading venue)
    # Add small delay to throttle candleSnapshot calls (rate limit protection)
    time.sleep(HYPERLIQUID_CANDLE_THROTTLE_DELAY)
    closes = _fetch_klines_hyperliquid(symbol, interval, limit)
    if closes:
        KLINES_CACHE[cache_key] = {"ts": now, "data": closes}
        return closes
    
    # Fallback to Binance
    for endpoint in ["/fapi/v1/klines", "/fapi/v3/klines"]:
        try:
            response = requests.get(
                f"{BINANCE_FAPI_URL}{endpoint}",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=3  # Reduced timeout from 5s to 3s
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                closes = []
                for k in data:
                    try:
                        closes.append(float(k[4]))
                    except Exception:
                        continue
                if closes:
                    KLINES_CACHE[cache_key] = {"ts": now, "data": closes}
                    return closes
        except Exception:
            continue
    return []

def _trend_dir_from_closes(closes: List[float]) -> tuple:
    ema_fast = _ema(closes, TREND_EMA_FAST)
    ema_slow = _ema(closes, TREND_EMA_SLOW)
    if ema_fast is None or ema_slow in (None, 0):
        return None, None
    diff_pct = (ema_fast - ema_slow) / ema_slow * 100
    if abs(diff_pct) < TREND_NEUTRAL_BAND_PCT:
        return 0, diff_pct
    return (1 if diff_pct > 0 else -1), diff_pct

def _mark_stale_trend(data: Dict, age_sec: float) -> Dict:
    """Annotate trend data as stale for downstream visibility."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    out["_stale"] = True
    out["_stale_age_sec"] = int(age_sec)
    return out

# Rate-limit trend failure warnings per symbol (avoid log spam)
_TREND_WARN_LAST: Dict[str, float] = {}
# Round-robin index for rolling trend refresh (synced with batch boundaries)
_TREND_ROLLING_BATCH_INDEX = 0
_TREND_ROLLING_LOCK = threading.Lock()

def _rolling_trend_refresh_worker():
    """Background thread: refresh trend for one batch of symbols every TREND_ROLLING_INTERVAL_SEC, in sync with batch cache."""
    global _TREND_ROLLING_BATCH_INDEX
    batches = [SUPPORTED_SYMBOLS[i:i + BATCH_SIZE] for i in range(0, len(SUPPORTED_SYMBOLS), BATCH_SIZE)]
    if not batches:
        return
    executor = ThreadPoolExecutor(max_workers=TREND_ROLLING_WORKERS)
    try:
        while True:
            with _TREND_ROLLING_LOCK:
                idx = _TREND_ROLLING_BATCH_INDEX % len(batches)
                _TREND_ROLLING_BATCH_INDEX = (idx + 1) % len(batches)
            batch_symbols = batches[idx]
            for _ in executor.map(get_mtf_trend, batch_symbols):
                pass  # side effect: fill TREND_CACHE
            time.sleep(TREND_ROLLING_INTERVAL_SEC)
    except Exception as e:
        logger.warning("Rolling trend refresh worker error: %s", e)
    finally:
        executor.shutdown(wait=False)

def get_mtf_trend(symbol: str) -> Optional[Dict]:
    """Return multi-timeframe EMA trend for a symbol with caching."""
    now = time.time()
    cached = TREND_CACHE.get(symbol)
    # Extended cache TTL for better performance (was 55s, now 120s)
    extended_ttl = TREND_CACHE_TTL_SEC * 2
    if cached and (now - cached.get("ts", 0)) < extended_ttl:
        return cached.get("data")
    stale_data = None
    stale_age = None
    if cached:
        age = now - cached.get("ts", 0)
        if age < TREND_STALE_FALLBACK_SEC:
            stale_data = cached.get("data")
            stale_age = age
    data = {}
    limit = max(TREND_EMA_SLOW * 3, 60)
    for tf in TREND_TIMEFRAMES:
        closes = _fetch_klines(symbol, tf, limit=limit)
        if not closes or len(closes) < TREND_EMA_SLOW:
            if now - _TREND_WARN_LAST.get(symbol, 0) >= TREND_WARN_COOLDOWN_SEC:
                _TREND_WARN_LAST[symbol] = now
                if stale_data is not None:
                    logger.warning(
                        "Live trend data failed for %s (klines missing/insufficient), using stale cache (age %.0fs)",
                        symbol, stale_age,
                    )
                else:
                    logger.warning(
                        "Live trend data failed for %s (no klines and no stale cache); signals will be blocked",
                        symbol,
                    )
            return _mark_stale_trend(stale_data, stale_age) if stale_data else None
        direction, diff = _trend_dir_from_closes(closes)
        if direction is None:
            if now - _TREND_WARN_LAST.get(symbol, 0) >= TREND_WARN_COOLDOWN_SEC:
                _TREND_WARN_LAST[symbol] = now
                if stale_data is not None:
                    logger.warning(
                        "Live trend data failed for %s (EMA invalid), using stale cache (age %.0fs)",
                        symbol, stale_age,
                    )
                else:
                    logger.warning(
                        "Live trend data failed for %s (EMA invalid, no stale cache); signals will be blocked",
                        symbol,
                    )
            return _mark_stale_trend(stale_data, stale_age) if stale_data else None
        data[tf] = direction
        data[f"{tf}_diff"] = diff
    TREND_CACHE[symbol] = {"ts": now, "data": data}
    return data

def _trend_label(val: int) -> str:
    if val > 0:
        return "UP"
    if val < 0:
        return "DOWN"
    return "FLAT"

def mtf_trend_allows(symbol: str, direction: str) -> tuple:
    """Fast MTF trend filter: require 5m trend with 15m not opposing."""
    if not TREND_FILTER_ENABLED:
        return True, {}
    trend = get_mtf_trend(symbol)
    if not trend:
        return (True, {"reason": "no_data"}) if TREND_FAIL_OPEN else (False, {"reason": "no_data"})
    fast_tf = TREND_TIMEFRAMES[0] if TREND_TIMEFRAMES else None
    slow_tf = TREND_TIMEFRAMES[1] if len(TREND_TIMEFRAMES) > 1 else fast_tf
    fast = trend.get(fast_tf, 0) if fast_tf else 0
    slow = trend.get(slow_tf, 0) if slow_tf else 0
    dir_up = str(direction).upper()
    if dir_up == "LONG":
        ok = (fast > 0) and (slow >= 0)
    elif dir_up == "SHORT":
        ok = (fast < 0) and (slow <= 0)
    else:
        ok = True
    meta = {
        "fast": _trend_label(fast),
        "slow": _trend_label(slow),
        "fast_diff": trend.get(f"{fast_tf}_diff"),
        "slow_diff": trend.get(f"{slow_tf}_diff")
    }
    return ok, meta

def build_trend_meta(symbol: str) -> Dict:
    if not TREND_FILTER_ENABLED:
        return {"status": "DISABLED"}
    trend = get_mtf_trend(symbol)
    if not trend:
        return {"status": "NO_DATA"}
    fast_tf = TREND_TIMEFRAMES[0] if TREND_TIMEFRAMES else "fast"
    slow_tf = TREND_TIMEFRAMES[1] if len(TREND_TIMEFRAMES) > 1 else fast_tf
    status = "STALE" if trend.get("_stale") else "OK"
    out = {
        "status": status,
        fast_tf: _trend_label(trend.get(fast_tf, 0)),
        slow_tf: _trend_label(trend.get(slow_tf, 0)),
        f"{fast_tf}_diff": trend.get(f"{fast_tf}_diff"),
        f"{slow_tf}_diff": trend.get(f"{slow_tf}_diff"),
    }
    if trend.get("_stale"):
        out["stale_age_sec"] = trend.get("_stale_age_sec")
    return out


def _build_compact_signal(levels: List[LiquidationLevel], current_price: float, 
                         min_strength: float, max_distance: float, symbol: Optional[str] = None,
                         funding_rate: Optional[float] = None) -> Dict:
    """Build compact signal from levels - minimal for NEUTRAL"""
    if not levels or not current_price:
        return {"dir": "NEUTRAL"}  # Minimal for NEUTRAL signals
    
    long_clusters_below = [l for l in levels if l.side == 'long' and l.price_level < current_price]
    short_clusters_above = [l for l in levels if l.side == 'short' and l.price_level > current_price]
    
    long_clusters_below.sort(key=lambda x: x.strength, reverse=True)
    short_clusters_above.sort(key=lambda x: x.strength, reverse=True)

    sl_pct_dynamic = _sl_pct_for_rr(symbol, current_price) if symbol else 0.0
    if sl_pct_dynamic <= 0:
        sl_pct_dynamic = ESTIMATED_SL_PCT
    
    candidates = []

    if short_clusters_above and short_clusters_above[0].strength >= min_strength:
        strongest_short = short_clusters_above[0]
        if strongest_short.distance_from_price >= MIN_CLUSTER_DISTANCE_PCT and strongest_short.distance_from_price < max_distance:
            entry = current_price
            stop_loss = current_price * (1 - sl_pct_dynamic / 100.0)
            take_profit = strongest_short.price_level * (1 + TP_CLUSTER_OFFSET_PCT / 100.0)
            tp_distance_pct = (take_profit - entry) / entry * 100.0 if entry else 0
            if tp_distance_pct >= MIN_TP_DISTANCE_PCT:
                base_strength = strongest_short.strength
                if _enhanced_confidence_score and funding_rate is not None:
                    enhanced_conf = _enhanced_confidence_score(
                        base_strength, strongest_short.distance_from_price, "LONG", funding_rate, max_distance
                    )
                else:
                    enhanced_conf = base_strength
                trend_ok = True
                if symbol:
                    trend_ok, _ = mtf_trend_allows(symbol, "LONG")
                risk = entry - stop_loss
                reward = take_profit - entry
                risk_reward = round(reward / risk, 2) if risk > 0 else 0
                if risk_reward >= MIN_RR_FOR_SIGNAL:
                    candidates.append({
                        "dir": "LONG",
                        "entry": _round_price(entry),
                        "sl": _round_price(stop_loss),
                        "tp": _round_price(take_profit),
                        "conf": round(enhanced_conf, 2),
                        "rr": risk_reward,
                        "trend_aligned": trend_ok,
                    })

    if long_clusters_below and long_clusters_below[0].strength >= min_strength:
        strongest_long = long_clusters_below[0]
        if strongest_long.distance_from_price >= MIN_CLUSTER_DISTANCE_PCT and strongest_long.distance_from_price < max_distance:
            entry = current_price
            stop_loss = current_price * (1 + sl_pct_dynamic / 100.0)
            take_profit = strongest_long.price_level * (1 - TP_CLUSTER_OFFSET_PCT / 100.0)
            tp_distance_pct = (entry - take_profit) / entry * 100.0 if entry else 0
            if tp_distance_pct >= MIN_TP_DISTANCE_PCT:
                base_strength = strongest_long.strength
                if _enhanced_confidence_score and funding_rate is not None:
                    enhanced_conf = _enhanced_confidence_score(
                        base_strength, strongest_long.distance_from_price, "SHORT", funding_rate, max_distance
                    )
                else:
                    enhanced_conf = base_strength
                trend_ok = True
                if symbol:
                    trend_ok, _ = mtf_trend_allows(symbol, "SHORT")
                risk = stop_loss - entry
                reward = entry - take_profit
                risk_reward = round(reward / risk, 2) if risk > 0 else 0
                if risk_reward >= MIN_RR_FOR_SIGNAL:
                    candidates.append({
                        "dir": "SHORT",
                        "entry": _round_price(entry),
                        "sl": _round_price(stop_loss),
                        "tp": _round_price(take_profit),
                        "conf": round(enhanced_conf, 2),
                        "rr": risk_reward,
                        "trend_aligned": trend_ok,
                    })

    if not candidates:
        return {"dir": "NEUTRAL"}

    if symbol:
        aligned = [c for c in candidates if c.get("trend_aligned")]
        if aligned:
            candidates = aligned
    candidates.sort(key=lambda c: (c.get("conf", 0), c.get("rr", 0)), reverse=True)
    return candidates[0]

def _build_signal_for_direction(
    levels: List[LiquidationLevel],
    current_price: float,
    direction: str,
    min_strength: float,
    max_distance: float,
    symbol: Optional[str] = None,
) -> Optional[Dict]:
    """Build signal for one direction only (LONG or SHORT). Returns None if no valid cluster."""
    if not levels or not current_price:
        return None
    long_clusters_below = [l for l in levels if l.side == "long" and l.price_level < current_price]
    short_clusters_above = [l for l in levels if l.side == "short" and l.price_level > current_price]
    long_clusters_below.sort(key=lambda x: x.strength, reverse=True)
    short_clusters_above.sort(key=lambda x: x.strength, reverse=True)
    sl_pct_dynamic = _sl_pct_for_rr(symbol, current_price) if symbol else 0.0
    if sl_pct_dynamic <= 0:
        sl_pct_dynamic = ESTIMATED_SL_PCT

    if direction == "LONG" and short_clusters_above and short_clusters_above[0].strength >= min_strength:
        strongest = short_clusters_above[0]
        # Filter: cluster must be far enough from entry to be actionable
        if strongest.distance_from_price < MIN_CLUSTER_DISTANCE_PCT or strongest.distance_from_price >= max_distance:
            return None
        entry = current_price
        stop_loss = current_price * (1 - sl_pct_dynamic / 100.0)
        take_profit = strongest.price_level * (1 + TP_CLUSTER_OFFSET_PCT / 100.0)  # TP above cluster (targeting short liquidations)
        tp_distance_pct = (take_profit - entry) / entry * 100.0 if entry else 0
        if tp_distance_pct >= MIN_TP_DISTANCE_PCT:
            trend_ok = True
            if symbol:
                trend_ok, _ = mtf_trend_allows(symbol, "LONG")
            risk = entry - stop_loss
            reward = take_profit - entry
            rr = round(reward / risk, 2) if risk > 0 else 0
            if rr < MIN_RR_FOR_SIGNAL:
                return None  # Reject low RR signals
            return {
                "dir": "LONG",
                "entry": _round_price(entry),
                "sl": _round_price(stop_loss),
                "tp": _round_price(take_profit),
                "conf": round(strongest.strength, 2),
                "rr": rr,
                "trend_aligned": trend_ok,
            }

    if direction == "SHORT" and long_clusters_below and long_clusters_below[0].strength >= min_strength:
        strongest = long_clusters_below[0]
        # Filter: cluster must be far enough from entry to be actionable
        if strongest.distance_from_price < MIN_CLUSTER_DISTANCE_PCT or strongest.distance_from_price >= max_distance:
            return None
        entry = current_price
        stop_loss = current_price * (1 + sl_pct_dynamic / 100.0)
        take_profit = strongest.price_level * (1 - TP_CLUSTER_OFFSET_PCT / 100.0)  # TP below cluster (targeting long liquidations)
        tp_distance_pct = (entry - take_profit) / entry * 100.0 if entry else 0
        if tp_distance_pct >= MIN_TP_DISTANCE_PCT:
            trend_ok = True
            if symbol:
                trend_ok, _ = mtf_trend_allows(symbol, "SHORT")
            risk = stop_loss - entry
            reward = entry - take_profit
            rr = round(reward / risk, 2) if risk > 0 else 0
            if rr < MIN_RR_FOR_SIGNAL:
                return None  # Reject low RR signals
            return {
                "dir": "SHORT",
                "entry": _round_price(entry),
                "sl": _round_price(stop_loss),
                "tp": _round_price(take_profit),
                "conf": round(strongest.strength, 2),
                "rr": rr,
                "trend_aligned": trend_ok,
            }
    return None

def _build_compact_levels(levels: List[LiquidationLevel], current_price: float) -> Dict:
    """Build compact support/resistance levels - only top 2, omit if empty"""
    support = sorted(
        [l.price_level for l in levels if l.side == 'long' and l.price_level < current_price],
        reverse=True
    )[:2]  # Reduced to top 2
    
    resistance = sorted(
        [l.price_level for l in levels if l.side == 'short' and l.price_level > current_price]
    )[:2]  # Reduced to top 2
    
    result = {}
    if support:
        result["support"] = [_round_price(p) for p in support]
    if resistance:
        result["resistance"] = [_round_price(p) for p in resistance]
    
    return result

def _build_compact_sentiment(oi_data: Dict) -> Dict:
    """Build compact sentiment data - omit if no OI"""
    if not oi_data:
        return {}
    
    long_short_ratio = oi_data.get('long_short_ratio', 1.0)
    total_oi = oi_data.get('total_oi_usd', 0)
    
    # Skip if OI is too low (likely invalid data)
    if total_oi < 10000:
        return {}
    
    bull, bear, _bull_high, _bear_high = _sentiment_thresholds(oi_data)
    if long_short_ratio > bull:
        bias = "BULLISH"
    elif long_short_ratio < bear:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    
    return {
        "bias": bias,
        "lsr": round(long_short_ratio, 2),
        "oi": round(total_oi / 1000000, 1)  # Convert to millions, 1 decimal
    }

def _build_compact_clusters(levels: List[LiquidationLevel], current_price: float) -> Dict:
    """Build compact cluster data - omit if no clusters"""
    if not levels:
        return {}
    
    # Find best cluster (highest strength, closest to price)
    best = max(levels, key=lambda x: (x.strength, -x.distance_from_price))
    
    # Recalculate distance from current_price (more accurate than stored distance)
    # This ensures dist reflects actual distance even if price changed since level was built
    if current_price and current_price > 0:
        actual_dist = abs(best.price_level - current_price) / current_price * 100.0
    else:
        actual_dist = best.distance_from_price  # Fallback to stored distance
    
    return {
        "best": {
            "price": _round_price(best.price_level),
            "side": best.side,
            "str": round(best.strength, 1),  # 1 decimal instead of 2
            "dist": round(actual_dist, 2)  # 2 decimals to show small distances (0.01%, 0.03%, etc.)
        }
        # Removed "count" - redundant
    }

# More specific path first so /api/trade/batch/hyperliquid is not matched by /api/trade/{symbol}
def _process_symbol_batch(symbols: List[str], data: Dict, min_strength: float, max_distance: float, skip_trend: bool = False) -> Dict:
    """Process a batch of symbols and return results. skip_trend=True skips trend calculation for speed."""
    current_prices = data["current_prices"]
    open_interest_data = data["open_interest_data"]
    liquidation_levels = data["liquidation_levels"]
    results = {}
    for symbol in symbols:
        # Early skip if no price data
        current_price = current_prices.get(symbol, 0.0)
        if not current_price:
            continue
        
        levels = liquidation_levels.get(symbol, [])
        signal_levels = [l for l in levels if l.distance_from_price >= MIN_CLUSTER_DISTANCE_PCT and l.distance_from_price < max_distance and l.strength >= min_strength]
        oi_data = open_interest_data.get(symbol, {})
        funding_rate = oi_data.get("funding_rate_smooth") if isinstance(oi_data, dict) else None
        if funding_rate is None and isinstance(oi_data, dict):
            funding_rate = oi_data.get("funding_rate")
        signal = _build_compact_signal(signal_levels, current_price, min_strength, max_distance, symbol, funding_rate)
        symbol_data = {
            "price": _round_price(current_price) if current_price else 0.0,
            "signal": signal,
            "trend": {} if skip_trend else build_trend_meta(symbol),  # Skip trend for speed if requested
        }
        levels_data = _build_compact_levels(levels, current_price)
        if levels_data:
            symbol_data["levels"] = levels_data
        sentiment_data = _build_compact_sentiment(oi_data)
        if sentiment_data:
            symbol_data["sentiment"] = sentiment_data
        clusters_data = _build_compact_clusters(levels, current_price)
        if clusters_data:
            symbol_data["clusters"] = clusters_data
        results[symbol] = symbol_data
    return results

@app.get("/api/trade/batch/hyperliquid", response_model=BatchTradeResponse)
async def get_batch_trade_data_hyperliquid(
    min_strength: float = Query(0.70, ge=0.0, le=1.0),
    max_distance: float = Query(3.0, ge=0.0, le=10.0),
    batch_id: Optional[int] = Query(None, description="Optional: Get specific batch (0-indexed). If not provided, returns all batches.")
):
    """
    Same response shape as /api/trade/batch but data is pulled from Hyperliquid.
    GET https://api.hyperliquid.xyz/info (metaAndAssetCtxs: mark price, OI, impact prices).
    Returns all symbols that exist on Hyperliquid.
    
    Batching: Assets are processed in batches of 10 for performance. Use batch_id to get specific batch,
    or omit to get all batches (may be slower for 50+ assets).
    """
    if fetch_hyperliquid_batch_data is None:
        raise HTTPException(status_code=503, detail="Hyperliquid batch module not available")
    
    # Cache Hyperliquid data fetch (shared across all batches/requests)
    global HYPERLIQUID_DATA_CACHE, HYPERLIQUID_DATA_CACHE_TIME
    current_time = time.time()
    cache_age = current_time - HYPERLIQUID_DATA_CACHE_TIME
    data_age_ms = int(cache_age * 1000) if HYPERLIQUID_DATA_CACHE_TIME > 0 else 0
    
    if HYPERLIQUID_DATA_CACHE is None or cache_age >= HYPERLIQUID_DATA_CACHE_TTL:
        # Fetch fresh data
        data = fetch_hyperliquid_batch_data()
        HYPERLIQUID_DATA_CACHE = data
        HYPERLIQUID_DATA_CACHE_TIME = current_time
        data_age_ms = 0  # Fresh data
    else:
        # Use cached data
        data = HYPERLIQUID_DATA_CACHE
    
    # Split symbols into batches
    all_symbols = SUPPORTED_SYMBOLS
    batches = [all_symbols[i:i + BATCH_SIZE] for i in range(0, len(all_symbols), BATCH_SIZE)]
    
    # If batch_id specified, return only that batch
    if batch_id is not None:
        if batch_id < 0 or batch_id >= len(batches):
            raise HTTPException(status_code=400, detail=f"batch_id must be between 0 and {len(batches)-1}")
        batch_symbols = batches[batch_id]
        # Skip trend for single batch requests (faster, trader can request trend separately if needed)
        results = _process_symbol_batch(batch_symbols, data, min_strength, max_distance, skip_trend=False)
        return BatchTradeResponse(
            results=results,
            ts=datetime.now().strftime("%H:%M:%S"),
            data_age_ms=data_age_ms
        )
    
    # Process all batches (for backward compatibility)
    # Use cached results where possible, update in background
    results = {}
    
    # Check cache and process batches
    for batch_idx, batch_symbols in enumerate(batches):
        cache_key = f"{batch_idx}_{min_strength}_{max_distance}"
        cache_age = current_time - BATCH_LAST_UPDATE.get(cache_key, 0)
        
        # Use cache if fresh (< BATCH_CACHE_TTL seconds old)
        if cache_key in BATCH_CACHE and cache_age < BATCH_CACHE_TTL:
            results.update(BATCH_CACHE[cache_key])
        else:
            # Process batch and cache result
            # Skip trend calculation for all-batch requests to speed up (trend can be calculated on-demand)
            batch_results = _process_symbol_batch(batch_symbols, data, min_strength, max_distance, skip_trend=False)
            results.update(batch_results)
            with BATCH_UPDATE_LOCK:
                BATCH_CACHE[cache_key] = batch_results
                BATCH_LAST_UPDATE[cache_key] = current_time
    
    return BatchTradeResponse(
        results=results,
        ts=datetime.now().strftime("%H:%M:%S"),
        data_age_ms=data_age_ms
    )

@app.get("/api/trade/batch", response_model=BatchTradeResponse)
async def get_batch_trade_data(
    min_strength: float = Query(0.70, ge=0.0, le=1.0),
    max_distance: float = Query(3.0, ge=0.0, le=10.0)
):
    """
    COMPACT API - Get ALL essential trading data for ALL supported symbols automatically
    
    No request body needed - automatically returns data for all 10 supported symbols:
    ETH, SOL, BNB, XRP, TRX, DOGE, ADA, BCH, LINK, XMR
    
    Query params:
    - min_strength: Minimum cluster strength (default: 0.6)
    - max_distance: Maximum distance from price % (default: 3.0)
    
    Returns: All symbols' data in compact format, including last price per symbol (refreshed from Binance on each request).
    """
    results = {}
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        # Refresh prices from Binance so response is as fresh as possible (1 req for all symbols)
        heatmap.refresh_prices()
        
        # Automatically process ALL supported symbols
        for symbol in SUPPORTED_SYMBOLS:
            levels = heatmap.get_levels(symbol, min_strength=0.3, max_distance=10.0)
            signal_levels = heatmap.get_levels(symbol, min_strength=min_strength, max_distance=max_distance)
            current_price = heatmap.current_prices.get(symbol, 0)
            oi_data = heatmap.open_interest_data.get(symbol, {})
            
            # Build signal (needs price for calculations)
            signal = _build_compact_signal(signal_levels, current_price, min_strength, max_distance, symbol)
            
            # Build compact data: price first so it's always at top level in JSON
            symbol_data = {
                "price": _round_price(current_price) if current_price else 0.0,
                "signal": signal,
                "trend": build_trend_meta(symbol),
            }
            
            # Only add non-empty sections
            levels_data = _build_compact_levels(levels, current_price)
            if levels_data:
                symbol_data["levels"] = levels_data
            
            sentiment_data = _build_compact_sentiment(oi_data)
            if sentiment_data:
                symbol_data["sentiment"] = sentiment_data
            
            clusters_data = _build_compact_clusters(levels, current_price)
            if clusters_data:
                symbol_data["clusters"] = clusters_data
            
            results[symbol] = symbol_data
    
    return BatchTradeResponse(
        results=results,
        ts=datetime.now().strftime("%H:%M:%S"),  # Shorter timestamp format
        data_age_ms=0  # Always fresh data from heatmap
    )

@app.get("/api/trade/{symbol}", response_model=CompactTradeResponse)
async def get_compact_trade_data(
    symbol: str,
    min_strength: float = Query(0.70, ge=0.0, le=1.0),
    max_distance: float = Query(3.0, ge=0.0, le=10.0)
):
    """
    COMPACT API - Get ALL essential trading data for ONE symbol in a single call
    
    Returns: signal, levels, sentiment, clusters, price (refreshed from Binance on each request).
    """
    symbol = symbol.upper().replace('/', '').replace('USDT:USDT', 'USDT')
    
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not supported")
    
    with heatmap_lock:
        if not heatmap:
            initialize_heatmap()
        # Refresh prices so response has freshest price (1 req for all symbols)
        heatmap.refresh_prices()
        
        levels = heatmap.get_levels(symbol, min_strength=0.3, max_distance=10.0)  # Get all for levels
        signal_levels = heatmap.get_levels(symbol, min_strength=min_strength, max_distance=max_distance)  # Filtered for signal
        current_price = heatmap.current_prices.get(symbol, 0)
        oi_data = heatmap.open_interest_data.get(symbol, {})
        primary_signal = _build_compact_signal(signal_levels, current_price, min_strength, max_distance, symbol)
        signal_long = _build_signal_for_direction(signal_levels, current_price, "LONG", min_strength, max_distance, symbol)
        signal_short = _build_signal_for_direction(signal_levels, current_price, "SHORT", min_strength, max_distance, symbol)
        return CompactTradeResponse(
            symbol=symbol,
            price=_round_price(current_price),
            signal=primary_signal,
            levels=_build_compact_levels(levels, current_price),
            sentiment=_build_compact_sentiment(oi_data),
            clusters=_build_compact_clusters(levels, current_price),
            trend=build_trend_meta(symbol),
            ts=datetime.now().isoformat(),
            signal_long=signal_long,
            signal_short=signal_short,
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
