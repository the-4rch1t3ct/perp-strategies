"""
Hyperliquid batch data fetcher.
Returns the same shape as the Wagmi/Binance batch API (results.{SYMBOL}.price, signal, levels, sentiment, clusters)
using data from Hyperliquid's public API (metaAndAssetCtxs: mark price, OI, impact prices).
"""

from datetime import datetime
from math import sqrt
from typing import Dict, List, Optional, Any
import httpx

# Reuse same dataclass as predictive heatmap so _build_compact_* helpers work
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from predictive_liquidation_heatmap import LiquidationLevel

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

# Funding → positioning controls (keep centralized for consistency)
FUNDING_RATIO_MULTIPLIER = 1000.0
FUNDING_EXTREME_THRESHOLD = 0.000035
FUNDING_SMOOTH_ALPHA = 0.5
_FUNDING_SMOOTH_CACHE: Dict[str, float] = {}
FUNDING_TREND_WINDOW = 3
FUNDING_TREND_EPS = 0.000003
_FUNDING_TREND_HISTORY: Dict[str, List[float]] = {}

# Map to Hyperliquid coin names (strip USDT). Includes Aster batch symbols.
SYMBOL_TO_COIN: Dict[str, str] = {
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
    "BNBUSDT": "BNB",
    "XRPUSDT": "XRP",
    "TRXUSDT": "TRX",
    "DOGEUSDT": "DOGE",
    "ADAUSDT": "ADA",
    "BCHUSDT": "BCH",
    "LINKUSDT": "LINK",
    "XMRUSDT": "XMR",
    "ASTERUSDT": "ASTER",
    "HYPEUSDT": "HYPE",
    "SUIUSDT": "SUI",
    "PUMPUSDT": "PUMP",
    # Tier 1 - High Liquidity, Major Coins
    "BTCUSDT": "BTC",
    "MATICUSDT": "MATIC",
    "AVAXUSDT": "AVAX",
    # Tier 2 - Strong Additions
    "ATOMUSDT": "ATOM",
    "DOTUSDT": "DOT",
    "UNIUSDT": "UNI",
    "LTCUSDT": "LTC",
    # Tier 3 - L2s
    "ARBUSDT": "ARB",
    "OPUSDT": "OP",
    # Tier 4 - Emerging L1s
    "APTUSDT": "APT",
    "INJUSDT": "INJ",
    "TIAUSDT": "TIA",
    # Tier 5 - High-Volume Memes (BONK/FLOKI/SHIB removed for API speed)
    "PEPEUSDT": "PEPE",
    "WIFUSDT": "WIF",
    # Batch 2 - DeFi/L2 (COMP, SNX, SUPER, TNSR, Batch 3 removed for speed)
    "ETCUSDT": "ETC",
    "ALGOUSDT": "ALGO",
    "NEARUSDT": "NEAR",
    "ICPUSDT": "ICP",
    "FILUSDT": "FIL",
    "JTOUSDT": "JTO",
    "RUNEUSDT": "RUNE",
    "AAVEUSDT": "AAVE",
    "CRVUSDT": "CRV",
    "GMXUSDT": "GMX",
    "DYDXUSDT": "DYDX",
    "STRKUSDT": "STRK",
    "ZROUSDT": "ZRO",
    "METISUSDT": "METIS",
    "SEIUSDT": "SEI",
}
SUPPORTED_SYMBOLS_HL = list(SYMBOL_TO_COIN.keys())


def _pct_dist(price: float, mid: float) -> float:
    if not mid or mid <= 0:
        return 0.0
    return abs(price - mid) / mid * 100.0


def _smooth_funding_rate(symbol: str, funding_rate: Optional[float]) -> Optional[float]:
    """EMA smoothing for funding rate to reduce noise and flicker."""
    if funding_rate is None:
        return None
    try:
        current = float(funding_rate)
    except (TypeError, ValueError):
        return None
    prev = _FUNDING_SMOOTH_CACHE.get(symbol)
    if prev is None:
        _FUNDING_SMOOTH_CACHE[symbol] = current
        return current
    smoothed = (FUNDING_SMOOTH_ALPHA * current) + ((1.0 - FUNDING_SMOOTH_ALPHA) * prev)
    _FUNDING_SMOOTH_CACHE[symbol] = smoothed
    return smoothed


def _update_funding_trend(symbol: str, funding_rate: Optional[float]) -> tuple:
    """Track funding trend using a short rolling window of smoothed values."""
    if funding_rate is None:
        return ("FLAT", 0.0, 0.0)
    try:
        current = float(funding_rate)
    except (TypeError, ValueError):
        return ("FLAT", 0.0, 0.0)
    history = _FUNDING_TREND_HISTORY.setdefault(symbol, [])
    history.append(current)
    if len(history) > FUNDING_TREND_WINDOW:
        history.pop(0)
    if len(history) < 2:
        return ("FLAT", 0.0, 0.0)
    delta = history[-1] - history[0]
    if abs(delta) < FUNDING_TREND_EPS:
        trend = "FLAT"
    else:
        trend = "UP" if delta > 0 else "DOWN"
    strength = min(1.0, abs(delta) / FUNDING_EXTREME_THRESHOLD) if FUNDING_EXTREME_THRESHOLD > 0 else 0.0
    return (trend, delta, strength)


def fetch_hyperliquid_meta_and_ctx() -> Optional[tuple]:
    """
    POST metaAndAssetCtxs. Returns (universe: list, asset_ctxs: list) or None.
    universe[i].name = coin name; asset_ctxs[i] = {markPx, openInterest, impactPxs?, ...}
    """
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                HYPERLIQUID_INFO_URL,
                json={"type": "metaAndAssetCtxs"},
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            if not data or len(data) < 2:
                return None
            # First perp dex: [meta, asset_ctxs]
            meta, asset_ctxs = data[0], data[1]
            universe = meta.get("universe") or []
            return (universe, asset_ctxs)
    except Exception as e:
        return None


def _strength_from_oi_share(oi_usd: float, total_oi_usd: float) -> float:
    """Base strength from OI share across all HL symbols (market share component)."""
    if not total_oi_usd or total_oi_usd <= 0 or oi_usd <= 0:
        return 0.0
    return min(1.0, sqrt((oi_usd / total_oi_usd) * 3.0))


def _relative_strength_from_oi_concentration(oi_usd: float, mark_px: float = 0.0) -> float:
    """
    Relative strength based on coin-specific metrics (allows smaller coins to qualify).
    
    This measures OI concentration relative to price - higher OI/price ratio indicates
    more leverage and stronger liquidation potential. Allows smaller coins to achieve
    high strength if they have concentrated OI (high leverage).
    
    Args:
        oi_usd: Total OI in USD for this coin
        mark_px: Mark price of the coin
    
    Returns:
        Relative strength (0-1), where 1.0 = very high leverage/concentration
    """
    if not oi_usd or oi_usd <= 0:
        return 0.0
    
    import math
    
    # Use absolute OI size as the primary indicator
    # Higher OI = more liquidity = stronger signal potential
    # Normalize using log scale to compress the range
    
    # Typical OI ranges (USD):
    # - Very low: < $50k
    # - Low: $50k - $1M
    # - Medium: $1M - $10M
    # - High: $10M - $100M
    # - Very high: > $100M
    #
    # Use a smooth curve (no hard cutoff) so smaller tokens
    # can still score when their setups are strong.
    low_oi = 50_000
    high_oi = 10_000_000
    log_low = math.log10(low_oi)
    log_high = math.log10(high_oi)
    log_oi = math.log10(max(oi_usd, low_oi))
    
    # Normalize: log10(50k) -> 0.0, log10(10M) -> 1.0
    normalized = (log_oi - log_low) / (log_high - log_low)
    normalized = min(1.0, max(0.0, normalized))
    
    # Apply square root to compress high values (makes it more selective)
    # This ensures coins with substantial OI get high scores
    normalized = math.sqrt(normalized)
    
    return normalized


def _hybrid_strength(base_strength: float, relative_strength: float, 
                     base_weight: float = 0.2, relative_weight: float = 0.8) -> float:
    """
    Hybrid strength combining market share (base) and coin-specific (relative) metrics.
    
    This allows:
    - Major coins to still be favored (liquidity advantage)
    - Smaller coins to qualify if they have good setups (high leverage/concentration)
    
    Args:
        base_strength: Market share strength (0-1)
        relative_strength: Coin-specific strength (0-1)
        base_weight: Weight for base strength (default 0.2 = 20%)
        relative_weight: Weight for relative strength (default 0.8 = 80%)
    
    Returns:
        Final strength (0-1)
    """
    return min(1.0, (base_strength * base_weight) + (relative_strength * relative_weight))


def _enhanced_confidence_score(
    base_strength: float,
    distance_pct: float,
    direction: str,
    funding_rate: Optional[float] = None,
    max_distance: float = 3.0
) -> float:
    """
    Enhanced confidence scoring with multi-factor approach.
    
    Factors:
    1. Base strength (OI share) - 60% weight
    2. Distance factor (closer = higher) - 25% weight
    3. Funding alignment (extreme funding aligned with direction) - 15% weight
    
    Args:
        base_strength: OI-based strength (0-1)
        distance_pct: Distance from current price (%)
        direction: "LONG" or "SHORT"
        funding_rate: Hyperliquid funding rate (optional)
        max_distance: Maximum distance threshold (%)
    
    Returns:
        Enhanced confidence score (0-1)
    """
    if base_strength <= 0:
        return 0.0
    
    # Factor 1: Base strength (60% weight)
    strength_score = base_strength * 0.60
    
    # Factor 2: Distance factor (25% weight)
    # Closer clusters = higher confidence (inverse relationship)
    # Normalize: 0% distance = 1.0, max_distance = 0.0
    if distance_pct <= 0:
        distance_score = 1.0
    elif distance_pct >= max_distance:
        distance_score = 0.0
    else:
        # Linear decay: closer = higher score
        distance_score = 1.0 - (distance_pct / max_distance)
    distance_score *= 0.25
    
    # Factor 3: Funding alignment (15% weight)
    funding_score = 0.0
    if funding_rate is not None:
        try:
            funding = float(funding_rate)
            abs_funding = abs(funding)
            
            # Extreme funding threshold (shared constant for consistency)
            extreme_threshold = FUNDING_EXTREME_THRESHOLD
            
            if abs_funding >= extreme_threshold:
                # Check alignment
                if direction == "LONG":
                    # LONG targets short liquidations
                    # Negative funding = shorts pay longs = short-heavy = GOOD for LONG
                    if funding < 0:  # Short-heavy, good for LONG
                        alignment = min(1.0, abs_funding / extreme_threshold)
                        funding_score = alignment * 0.15
                elif direction == "SHORT":
                    # SHORT targets long liquidations
                    # Positive funding = longs pay shorts = long-heavy = GOOD for SHORT
                    if funding > 0:  # Long-heavy, good for SHORT
                        alignment = min(1.0, abs_funding / extreme_threshold)
                        funding_score = alignment * 0.15
        except (TypeError, ValueError):
            pass  # Keep funding_score = 0.0 if invalid
    
    # Combine factors (capped at 1.0)
    enhanced_conf = min(1.0, strength_score + distance_score + funding_score)
    
    # Ensure we don't go below base_strength (only boost, never reduce)
    return max(base_strength, enhanced_conf)


def _strength_from_oi_usd_fallback(oi_usd: float) -> float:
    """Fallback strength from absolute OI (keeps values in 0.3–1.0)."""
    if oi_usd <= 0:
        return 0.3
    ratio = min(1.0, oi_usd / 5_000_000)
    return 0.3 + 0.7 * sqrt(ratio)


def _funding_to_long_short_ratio(funding_rate: float, multiplier: float = FUNDING_RATIO_MULTIPLIER) -> float:
    """
    Convert Hyperliquid funding rate to long/short ratio.
    
    Formula: ratio = 1.0 + (funding_rate * multiplier)
    - Positive funding → longs pay shorts → long-heavy → ratio > 1.0
    - Negative funding → shorts pay longs → short-heavy → ratio < 1.0
    - Bounded between 0.5 and 2.0 for safety
    
    Args:
        funding_rate: Funding rate from Hyperliquid (e.g., -0.00001533)
        multiplier: Sensitivity multiplier (default 1000)
    
    Returns:
        long_short_ratio: Ratio of long OI to short OI (e.g., 0.985)
    """
    if funding_rate is None:
        return 1.0  # Fallback to balanced if missing
    
    try:
        funding = float(funding_rate)
        ratio = 1.0 + (funding * multiplier)
        # Cap between 0.5 (2:1 short/long) and 2.0 (2:1 long/short)
        return max(0.5, min(2.0, ratio))
    except (TypeError, ValueError):
        return 1.0  # Fallback to balanced on error


def build_levels_from_hl(
    symbol: str,
    mark_px: float,
    oi_usd: float,
    impact_pxs: Optional[List[str]],
    strength: float,
    now: datetime,
    funding_rate: Optional[float] = None,
) -> List[LiquidationLevel]:
    """
    Build LiquidationLevel list for one symbol from HL context.
    impactPxs = [low, high] → support (long) at low, resistance (short) at high.
    """
    levels: List[LiquidationLevel] = []
    if not mark_px or mark_px <= 0:
        return levels

    # Strength is computed from real OI distribution (passed in).

    if impact_pxs and len(impact_pxs) >= 2:
        try:
            low_px = float(impact_pxs[0])
            high_px = float(impact_pxs[1])
        except (TypeError, ValueError):
            low_px = high_px = None
    else:
        low_px = high_px = None

    if low_px is not None and low_px > 0 and low_px < mark_px:
        dist = _pct_dist(low_px, mark_px)
        # Store funding_rate in a custom attribute (we'll use it for enhanced confidence)
        # Note: LiquidationLevel doesn't have funding_rate field, so we'll pass it separately
        levels.append(
            LiquidationLevel(
                price_level=low_px,
                side="long",
                leverage_tier=10.0,
                open_interest=oi_usd * 0.5,
                liquidation_count=0,
                strength=strength,
                distance_from_price=dist,
                cluster_id=0,
                last_updated=now,
            )
        )
    if high_px is not None and high_px > 0 and high_px > mark_px:
        dist = _pct_dist(high_px, mark_px)
        levels.append(
            LiquidationLevel(
                price_level=high_px,
                side="short",
                leverage_tier=10.0,
                open_interest=oi_usd * 0.5,
                liquidation_count=0,
                strength=strength,
                distance_from_price=dist,
                cluster_id=1,
                last_updated=now,
            )
        )

    # If no impact prices, create synthetic levels ±0.5% so we still return support/resistance
    if not levels:
        low_px = mark_px * 0.995
        high_px = mark_px * 1.005
        levels.append(
            LiquidationLevel(
                price_level=low_px,
                side="long",
                leverage_tier=10.0,
                open_interest=oi_usd * 0.5,
                liquidation_count=0,
                strength=strength,
                distance_from_price=0.5,
                cluster_id=0,
                last_updated=now,
            )
        )
        levels.append(
            LiquidationLevel(
                price_level=high_px,
                side="short",
                leverage_tier=10.0,
                open_interest=oi_usd * 0.5,
                liquidation_count=0,
                strength=strength,
                distance_from_price=0.5,
                cluster_id=1,
                last_updated=now,
            )
        )

    return levels


def fetch_hyperliquid_batch_data() -> Dict[str, Any]:
    """
    Fetch from Hyperliquid and return structures compatible with the existing
    _build_compact_signal, _build_compact_levels, _build_compact_sentiment, _build_compact_clusters:
    - current_prices: Dict[symbol, float]
    - open_interest_data: Dict[symbol, {long_short_ratio, total_oi_usd, ...}]
    - liquidation_levels: Dict[symbol, List[LiquidationLevel]]
    """
    result = {
        "current_prices": {},
        "open_interest_data": {},
        "liquidation_levels": {},
    }
    raw = fetch_hyperliquid_meta_and_ctx()
    if not raw:
        return result

    universe, asset_ctxs = raw
    coin_to_index: Dict[str, int] = {u["name"]: i for i, u in enumerate(universe) if isinstance(u, dict) and u.get("name")}
    now = datetime.utcnow()

    def _coin_index(coin: str) -> Optional[int]:
        if coin in coin_to_index:
            return coin_to_index[coin]
        if f"{coin}USD" in coin_to_index:
            return coin_to_index[f"{coin}USD"]
        return None

    symbol_ctx: Dict[str, Dict[str, Any]] = {}
    total_oi_usd_all = 0.0
    for symbol in SUPPORTED_SYMBOLS_HL:
        coin = SYMBOL_TO_COIN.get(symbol)
        if not coin:
            continue
        idx = _coin_index(coin)
        if idx is None:
            continue
        if idx >= len(asset_ctxs):
            continue
        ctx = asset_ctxs[idx]
        if not isinstance(ctx, dict):
            continue

        mark_str = ctx.get("markPx") or ctx.get("midPx")
        if mark_str is None:
            continue
        try:
            mark_px = float(mark_str)
        except (TypeError, ValueError):
            continue
        oi_str = ctx.get("openInterest", "0")
        try:
            oi_sz = float(oi_str)
        except (TypeError, ValueError):
            oi_sz = 0.0
        impact_pxs = ctx.get("impactPxs")  # [low, high] or null
        funding_rate = ctx.get("funding")  # Funding rate (positive = longs pay shorts)
        funding_rate_smooth = _smooth_funding_rate(symbol, funding_rate)
        trend_source = funding_rate_smooth if funding_rate_smooth is not None else funding_rate
        funding_trend, funding_trend_delta, funding_trend_strength = _update_funding_trend(symbol, trend_source)

        oi_usd = oi_sz * mark_px
        symbol_ctx[symbol] = {
            "mark_px": mark_px,
            "oi_usd": oi_usd,
            "impact_pxs": impact_pxs,
            "funding_rate": funding_rate,
            "funding_rate_smooth": funding_rate_smooth,
            "funding_trend": funding_trend,
            "funding_trend_delta": funding_trend_delta,
            "funding_trend_strength": funding_trend_strength,
        }
        total_oi_usd_all += max(oi_usd, 0.0)

    for symbol, ctx in symbol_ctx.items():
        mark_px = ctx["mark_px"]
        oi_usd = ctx["oi_usd"]
        impact_pxs = ctx["impact_pxs"]
        funding_rate = ctx.get("funding_rate")
        funding_rate_smooth = ctx.get("funding_rate_smooth")
        funding_trend = ctx.get("funding_trend", "FLAT")
        funding_trend_delta = ctx.get("funding_trend_delta", 0.0)
        funding_trend_strength = ctx.get("funding_trend_strength", 0.0)
        
        # Calculate hybrid strength: combines market share + coin-specific metrics
        base_strength = _strength_from_oi_share(oi_usd, total_oi_usd_all)
        if base_strength <= 0:
            base_strength = _strength_from_oi_usd_fallback(oi_usd)
        
        # Calculate relative strength (coin-specific, allows smaller coins to qualify)
        # Uses absolute OI size, not price-dependent ratio
        relative_strength = _relative_strength_from_oi_concentration(oi_usd)
        
        # Combine: 20% base (market share) + 80% relative (coin-specific)
        # This allows smaller coins with good setups to achieve high strength
        strength = _hybrid_strength(base_strength, relative_strength, 
                                   base_weight=0.2, relative_weight=0.8)
        
        # Calculate long/short ratio from funding rate
        ratio_source = funding_rate_smooth if funding_rate_smooth is not None else funding_rate
        long_short_ratio = _funding_to_long_short_ratio(ratio_source, multiplier=FUNDING_RATIO_MULTIPLIER)
        
        # Calculate long and short OI from ratio
        # If ratio = long_oi / short_oi, and total_oi = long_oi + short_oi:
        # long_oi = total_oi * (ratio / (1 + ratio))
        # short_oi = total_oi * (1 / (1 + ratio))
        if long_short_ratio > 0:
            long_oi_usd = oi_usd * (long_short_ratio / (1.0 + long_short_ratio))
            short_oi_usd = oi_usd * (1.0 / (1.0 + long_short_ratio))
        else:
            # Fallback to 50/50 if ratio is invalid
            long_oi_usd = oi_usd * 0.5
            short_oi_usd = oi_usd * 0.5
            long_short_ratio = 1.0

        result["current_prices"][symbol] = mark_px
        result["open_interest_data"][symbol] = {
            "total_oi_usd": oi_usd,
            "long_oi_usd": long_oi_usd,
            "short_oi_usd": short_oi_usd,
            "long_short_ratio": long_short_ratio,
            "funding_rate": funding_rate,
            "funding_rate_smooth": funding_rate_smooth,
            "funding_trend": funding_trend,
            "funding_trend_delta": funding_trend_delta,
            "funding_trend_strength": funding_trend_strength,
        }
        result["liquidation_levels"][symbol] = build_levels_from_hl(
            symbol, mark_px, oi_usd, impact_pxs, strength, now, funding_rate
        )
        
        # Funding rates already stored in open_interest_data for signal building

    return result
