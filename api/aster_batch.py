"""
Aster DEX batch data fetcher.
Returns the same shape as the Wagmi batch API (results.{SYMBOL}.price, signal, levels, sentiment, clusters)
using data from Aster's public API (fapi.asterdex.com: ticker/price, premiumIndex).
Prices and mark are from Aster so TP/SL/entry are accurate when trading on Aster.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from predictive_liquidation_heatmap import LiquidationLevel

ASTER_BASE = "https://fapi.asterdex.com"

# Aster symbols (no XAG/XAU). ASTER, HYPE, SUI, PUMP use Binance/HL clusters.
SUPPORTED_SYMBOLS_ASTER = [
    "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "BCHUSDT", "LINKUSDT", "XMRUSDT",
    "ASTERUSDT", "HYPEUSDT", "SUIUSDT", "PUMPUSDT",
]


def _pct_dist(price: float, mid: float) -> float:
    if not mid or mid <= 0:
        return 0.0
    return abs(price - mid) / mid * 100.0


def fetch_aster_prices() -> Dict[str, float]:
    """GET /fapi/v1/ticker/price (no symbol) → { SYMBOL: price }."""
    out: Dict[str, float] = {}
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(f"{ASTER_BASE}/fapi/v1/ticker/price")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                for item in data:
                    s = item.get("symbol")
                    p = item.get("price")
                    if s and p is not None:
                        try:
                            out[s] = float(p)
                        except (TypeError, ValueError):
                            pass
            elif isinstance(data, dict) and data.get("symbol") and data.get("price") is not None:
                try:
                    out[data["symbol"]] = float(data["price"])
                except (TypeError, ValueError):
                    pass
    except Exception:
        pass
    return out


def fetch_aster_premium_index() -> Dict[str, Dict]:
    """GET /fapi/v1/premiumIndex (no symbol) → { symbol: { markPrice, lastFundingRate, ... } }."""
    out: Dict[str, Dict] = {}
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(f"{ASTER_BASE}/fapi/v1/premiumIndex")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                for item in data:
                    s = item.get("symbol")
                    if s:
                        out[s] = item
            elif isinstance(data, dict) and data.get("symbol"):
                out[data["symbol"]] = data
    except Exception:
        pass
    return out


def build_levels_aster(mark_px: float, now: datetime) -> List[LiquidationLevel]:
    """
    Build synthetic support/resistance from mark (Aster public API has no OI/clusters).
    Same shape so _build_compact_signal/levels/clusters work.
    """
    if not mark_px or mark_px <= 0:
        return []
    strength = 0.6
    low_px = mark_px * 0.995
    high_px = mark_px * 1.005
    return [
        LiquidationLevel(
            price_level=low_px,
            side="long",
            leverage_tier=10.0,
            open_interest=0.0,
            liquidation_count=0,
            strength=strength,
            distance_from_price=0.5,
            cluster_id=0,
            last_updated=now,
        ),
        LiquidationLevel(
            price_level=high_px,
            side="short",
            leverage_tier=10.0,
            open_interest=0.0,
            liquidation_count=0,
            strength=strength,
            distance_from_price=0.5,
            cluster_id=1,
            last_updated=now,
        ),
    ]


def fetch_aster_batch_data() -> Dict[str, Any]:
    """
    Fetch from Aster and return structures compatible with _build_compact_*:
    current_prices, open_interest_data (minimal), liquidation_levels (synthetic from mark).
    """
    result = {
        "current_prices": {},
        "open_interest_data": {},
        "liquidation_levels": {},
    }
    prices = fetch_aster_prices()
    premium = fetch_aster_premium_index()
    now = datetime.utcnow()

    for symbol in SUPPORTED_SYMBOLS_ASTER:
        # Prefer mark from premiumIndex, fallback to ticker price
        mark = None
        if symbol in premium and premium[symbol].get("markPrice") is not None:
            try:
                mark = float(premium[symbol]["markPrice"])
            except (TypeError, ValueError):
                pass
        if mark is None and symbol in prices:
            mark = prices[symbol]
        if mark is None or mark <= 0:
            continue

        result["current_prices"][symbol] = mark
        result["open_interest_data"][symbol] = {
            "total_oi_usd": 0.0,
            "long_oi_usd": 0.0,
            "short_oi_usd": 0.0,
            "long_short_ratio": 1.0,
        }
        result["liquidation_levels"][symbol] = build_levels_aster(mark, now)

    return result
