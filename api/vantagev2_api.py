#!/usr/bin/env python3
"""
Vantage2 API - Modular Trading Data Endpoints
Endpoint: /arthurvega/fundingOI
Returns Open Interest and Funding Rate for all symbols
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import ccxt
from datetime import datetime, timedelta
import asyncio
from collections import deque
import time
import json
import os
from pathlib import Path

# Load .env file if it exists (for HL_ACCOUNT_ADDRESS, ASTER_API_KEY, etc.)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()
# Also try loading from clawd/.env.portfolio
_clawd_env = Path("/home/botadmin/clawd/.env.portfolio")
if _clawd_env.exists():
    with open(_clawd_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

app = FastAPI(title="Vantage2 API - Modular Trading Data")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_load_oi_history():
    """Load persisted OI history so oi_1h is available after restarts."""
    _load_oi_history_from_disk()


# Allowed symbols
SYMBOLS = [
    'ETH/USDT:USDT', 'SOL/USDT:USDT', 'BNB/USDT:USDT', 'XRP/USDT:USDT',
    'TRX/USDT:USDT', 'DOGE/USDT:USDT', 'ADA/USDT:USDT', 'BCH/USDT:USDT',
    'LINK/USDT:USDT', 'XMR/USDT:USDT', 'XLM/USDT:USDT', 'ZEC/USDT:USDT',
    'HYPE/USDT:USDT', 'LTC/USDT:USDT', 'SUI/USDT:USDT', 'AVAX/USDT:USDT',
]

# Compact response model - OI, Funding, and OI change
class VantageSignal(BaseModel):
    s: str  # symbol
    oi: Optional[float] = None  # open_interest (current)
    oi_1h: Optional[float] = None  # open_interest 1 hour ago
    oi_change_pct: Optional[float] = None  # OI change percentage: ((oi - oi_1h) / oi_1h) * 100
    fr: Optional[float] = None  # funding_rate (8h)

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

# Historical OI data storage - keep at least 1 hour of history
# Structure: {symbol: [(timestamp, oi_value), ...]}
# Persisted to disk so oi_1h survives API restarts and accumulates over time
oi_history: Dict[str, List[tuple]] = {}
HISTORY_RETENTION_HOURS = 2  # Keep 2 hours of history (safety margin)
OI_HISTORY_PATH = Path(__file__).resolve().parent / "oi_history.json"
_oi_history_last_save = 0.0
OI_SAVE_DEBOUNCE_SEC = 60.0  # Persist at most every 60 seconds

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


# Portfolio dashboard data (Aster + Hyperliquid)
CLAWD_MEMORY_DIR = Path("/home/botadmin/clawd/memory")
HL_PERF_PATH = CLAWD_MEMORY_DIR / "hyperliquid-trading-performance.json"
HL_POS_PATH = CLAWD_MEMORY_DIR / "hyperliquid-trading-positions.json"
HL_EQUITY_SNAPSHOTS_PATH = CLAWD_MEMORY_DIR / "hl_equity_snapshots.json"
HL_EQUITY_SNAPSHOTS_MAX = 48  # ~30min interval over 24h

# Optional live fetch for positions/equity (set env for HL to enable)
try:
    from api.portfolio_live import fetch_live_hyperliquid
except ImportError:
    try:
        from portfolio_live import fetch_live_hyperliquid
    except ImportError:
        fetch_live_hyperliquid = None


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text())
    except Exception:
        return {}


def _is_open_position(pos: Dict[str, Any]) -> bool:
    if not isinstance(pos, dict):
        return False
    if pos.get("exited") is True:
        return False
    if pos.get("closed_at"):
        return False
    return True


def _extract_open_positions(positions: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    if not isinstance(positions, dict):
        return results
    for symbol, pos in positions.items():
        if not _is_open_position(pos):
            continue
        entry_price = pos.get("entry_price")
        entry_qty = pos.get("entry_qty")
        pnl_pct = pos.get("pnl_pct")
        position_size_usd = None
        pnl_usd = None
        if entry_price is not None and entry_qty is not None:
            try:
                notional = abs(float(entry_qty)) * float(entry_price)
                position_size_usd = round(notional, 2)
                if pnl_pct is not None and notional:
                    pnl_usd = round(notional * float(pnl_pct) / 100.0, 2)
            except (TypeError, ValueError):
                pass
        results.append({
            "symbol": symbol,
            "side": pos.get("entry_side"),
            "entry_price": entry_price,
            "entry_qty": entry_qty,
            "leverage": pos.get("entry_leverage"),
            "tp_price": pos.get("tp_price"),
            "sl_price": pos.get("sl_price"),
            "opened_at": pos.get("opened_at"),
            "pnl_pct": pnl_pct,
            "position_size_usd": position_size_usd,
            "pnl_usd": pnl_usd,
        })
    return results


def _bucket_stats(trade_list: list, include_pnl_pct: bool = True) -> Dict[str, Any]:
    """Compute overview metrics for a list of trade dicts (all, longs, or shorts)."""
    pnls = []
    win_trades = []
    loss_trades = []
    volume_usd = 0.0
    for t in trade_list or []:
        if not isinstance(t, dict):
            continue
        try:
            p = float(t.get("pnl_usd", 0) or 0)
        except (TypeError, ValueError):
            continue
        pnls.append(p)
        if p > 0:
            win_trades.append(t)
        elif p < 0:
            loss_trades.append(t)
        try:
            vol = t.get("notional_usd")
            if vol is not None:
                volume_usd += float(vol)
        except (TypeError, ValueError):
            pass
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    winners = len(wins)
    losers = len(losses)
    win_rate_pct = round((winners / n) * 100, 2) if n else None
    total_pnl_usd = round(sum(pnls), 2) if n else None
    avg_pnl_usd = round(sum(pnls) / n, 2) if n else None
    avg_profit_usd = round(sum(wins) / len(wins), 2) if wins else None
    avg_loss_usd = round(sum(losses) / len(losses), 2) if losses else None
    pl_ratio = round(avg_profit_usd / abs(avg_loss_usd), 2) if (avg_profit_usd is not None and avg_loss_usd is not None and avg_loss_usd != 0) else None
    volume_usd = round(volume_usd, 2) if volume_usd else None
    pnl_pct = round((sum(pnls) / volume_usd) * 100, 2) if (include_pnl_pct and volume_usd and volume_usd > 0) else None
    win_pcts = []
    for t in win_trades:
        try:
            pc = t.get("pnl_pct")
            if pc is not None and str(pc).strip() != "":
                win_pcts.append(float(pc))
        except (TypeError, ValueError):
            pass
    loss_pcts = []
    for t in loss_trades:
        try:
            pc = t.get("pnl_pct")
            if pc is not None and str(pc).strip() != "":
                loss_pcts.append(float(pc))
        except (TypeError, ValueError):
            pass
    avg_profit_pct = round(sum(win_pcts) / len(win_pcts), 2) if win_pcts else None
    avg_loss_pct = round(sum(loss_pcts) / len(loss_pcts), 2) if loss_pcts else None
    return {
        "trades": n,
        "volume_usd": volume_usd,
        "winners": winners,
        "losers": losers,
        "win_rate_pct": win_rate_pct,
        "avg_pnl_usd": avg_pnl_usd,
        "avg_profit_usd": avg_profit_usd,
        "avg_loss_usd": avg_loss_usd,
        "avg_profit_pct": avg_profit_pct,
        "avg_loss_pct": avg_loss_pct,
        "pl_ratio": pl_ratio,
        "total_pnl_usd": total_pnl_usd,
        "pnl_pct": pnl_pct,
    }


def _parse_trade_time(t: dict) -> Optional[datetime]:
    """Parse trade time from 'time' or 'closed_at' (ISO string). Returns naive datetime or None."""
    raw = t.get("time") or t.get("closed_at")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw))
        s = str(raw).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _equity_snapshot_update_and_get_24h(current_equity: Optional[float]) -> Optional[float]:
    """Append current equity to snapshots, trim to last 48, return equity closest to now-24h."""
    if current_equity is None:
        current_equity = 0.0
    try:
        eq = float(current_equity)
    except (TypeError, ValueError):
        return None
    now = datetime.now()
    cutoff_48h = now - timedelta(hours=48)
    target_24h = now - timedelta(hours=24)
    snapshots = []
    if HL_EQUITY_SNAPSHOTS_PATH.exists():
        try:
            data = json.loads(HL_EQUITY_SNAPSHOTS_PATH.read_text())
            snapshots = (data.get("snapshots") or []) if isinstance(data, dict) else []
        except Exception:
            snapshots = []
    snapshots.append({"equity": round(eq, 2), "ts": now.isoformat()})
    # Keep only last 48 and from last 48h
    parsed = []
    for s in snapshots:
        if not isinstance(s, dict):
            continue
        ts_str = s.get("ts")
        if not ts_str:
            continue
        try:
            t = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if t.tzinfo:
                t = t.replace(tzinfo=None)
            if t >= cutoff_48h:
                parsed.append((t, float(s.get("equity", 0))))
        except (ValueError, TypeError):
            continue
    parsed.sort(key=lambda x: x[0])
    if len(parsed) > HL_EQUITY_SNAPSHOTS_MAX:
        parsed = parsed[-HL_EQUITY_SNAPSHOTS_MAX:]
    try:
        CLAWD_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        HL_EQUITY_SNAPSHOTS_PATH.write_text(
            json.dumps({"snapshots": [{"equity": e, "ts": t.isoformat()} for t, e in parsed]}, separators=(",", ":"))
        )
    except Exception:
        pass
    # Value closest to target_24h (before or at 24h ago)
    candidates = [(t, e) for t, e in parsed if t <= target_24h]
    if not candidates:
        return None
    best = min(candidates, key=lambda x: abs((x[0] - target_24h).total_seconds()))
    return round(best[1], 2)


def _trade_stats(trades: list) -> Dict[str, Any]:
    """From a list of trades with pnl_usd (and optional side, pnl_pct, notional_usd), compute flat metrics and overview_breakdown (total/longs/shorts)."""
    valid = []
    long_trades = []
    short_trades = []
    for t in trades or []:
        if not isinstance(t, dict):
            continue
        try:
            p = float(t.get("pnl_usd", 0) or 0)
        except (TypeError, ValueError):
            continue
        valid.append(t)
        side = (t.get("side") or "").strip().upper()
        if "LONG" in side or side == "L":
            long_trades.append(t)
        elif "SHORT" in side or side == "S":
            short_trades.append(t)
    pnls = [float(t.get("pnl_usd", 0) or 0) for t in valid]
    win_trades = [t for t in valid if (float(t.get("pnl_usd", 0) or 0) > 0)]
    loss_trades = [t for t in valid if (float(t.get("pnl_usd", 0) or 0) < 0)]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls)
    avg_profit = round(sum(wins) / len(wins), 2) if wins else None
    avg_loss = round(sum(losses) / len(losses), 2) if losses else None
    largest_win = round(max(wins), 2) if wins else None
    largest_loss = round(min(losses), 2) if losses else None
    win_pcts = []
    for t in win_trades:
        try:
            pc = t.get("pnl_pct")
            if pc is not None and str(pc).strip() != "":
                win_pcts.append(float(pc))
        except (TypeError, ValueError):
            pass
    loss_pcts = []
    for t in loss_trades:
        try:
            pc = t.get("pnl_pct")
            if pc is not None and str(pc).strip() != "":
                loss_pcts.append(float(pc))
        except (TypeError, ValueError):
            pass
    largest_win_pct = round(max(win_pcts), 2) if win_pcts else None
    largest_loss_pct = round(min(loss_pcts), 2) if loss_pcts else None
    avg_profit_pct = round(sum(win_pcts) / len(win_pcts), 2) if win_pcts else None
    avg_loss_pct = round(sum(loss_pcts) / len(loss_pcts), 2) if loss_pcts else None
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (float(gross_profit) if gross_profit else None)
    mean_pnl = sum(pnls) / n if n else 0
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / n if n else 0
    std_pnl = (variance ** 0.5) if variance > 0 else 0
    sharpe = round(mean_pnl / std_pnl, 2) if n >= 2 and std_pnl > 0 else None
    pl_ratio = round(avg_profit / abs(avg_loss), 2) if (avg_profit is not None and avg_loss is not None and avg_loss != 0) else None
    avg_total_pnl_usd = round(mean_pnl, 2) if n else None
    avg_pnl_longs_usd = round(sum(float(t.get("pnl_usd", 0) or 0) for t in long_trades) / len(long_trades), 2) if long_trades else None
    avg_pnl_shorts_usd = round(sum(float(t.get("pnl_usd", 0) or 0) for t in short_trades) / len(short_trades), 2) if short_trades else None
    # Overview breakdown: total, longs, shorts (PnL% only for total)
    total_bucket = _bucket_stats(valid, include_pnl_pct=True)
    longs_bucket = _bucket_stats(long_trades, include_pnl_pct=False)
    shorts_bucket = _bucket_stats(short_trades, include_pnl_pct=False)
    overview_breakdown = {
        "total": total_bucket,
        "longs": longs_bucket,
        "shorts": shorts_bucket,
    }
    return {
        "avg_profit_usd": avg_profit,
        "avg_loss_usd": avg_loss,
        "avg_profit_pct": avg_profit_pct,
        "avg_loss_pct": avg_loss_pct,
        "pl_ratio": pl_ratio,
        "avg_total_pnl_usd": avg_total_pnl_usd,
        "avg_pnl_longs_usd": avg_pnl_longs_usd,
        "avg_pnl_shorts_usd": avg_pnl_shorts_usd,
        "sharpe_ratio": sharpe,
        "profit_factor": profit_factor,
        "largest_win_usd": largest_win,
        "largest_loss_usd": largest_loss,
        "largest_win_pct": largest_win_pct,
        "largest_loss_pct": largest_loss_pct,
        "overview_breakdown": overview_breakdown,
    }


def _compute_summary(perf: Dict[str, Any], positions: Dict[str, Any]) -> Dict[str, Any]:
    last_10 = perf.get("last_10", []) if isinstance(perf, dict) else []
    last_trades = perf.get("last_trades", []) if isinstance(perf, dict) else []
    # Prefer win rate from actual closed-trade PnL (fixes wrong 100% when signals aggregates are off)
    total = won = lost = 0
    if last_trades:
        for t in last_trades:
            if not isinstance(t, dict):
                continue
            pnl = t.get("pnl_usd")
            if pnl is None:
                continue
            try:
                p = float(pnl)
            except (TypeError, ValueError):
                continue
            total += 1
            if p > 0:
                won += 1
            elif p < 0:
                lost += 1
    if total == 0:
        signals = perf.get("signals", {}) if isinstance(perf, dict) else {}
        total = sum((s or {}).get("total", 0) for s in signals.values())
        won = sum((s or {}).get("won", 0) for s in signals.values())
        lost = sum((s or {}).get("lost", 0) for s in signals.values())
    win_rate = round((won / total) * 100, 2) if total > 0 else 0.0
    last_10_pnl = round(sum(t.get("pnl_usd", 0) for t in last_10 if isinstance(t, dict)), 2)
    last_trade_time = last_trades[-1].get("time") if last_trades else None
    meta = perf.get("meta", {}) if isinstance(perf, dict) else {}
    equity = meta.get("last_equity")
    equity_time = meta.get("last_equity_time")

    open_positions = _extract_open_positions(positions)
    stats = _trade_stats(last_trades)
    # 24h-ago stats: stats from trades closed before (now - 24h)
    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)
    trades_24h = [t for t in (last_trades or []) if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) < cutoff_24h]
    stats_24h = _trade_stats(trades_24h) if trades_24h else {}
    ob_24h = (stats_24h.get("overview_breakdown") or {}).get("total") or {}
    win_rate_pct_24h_ago = ob_24h.get("win_rate_pct")
    sharpe_ratio_24h_ago = stats_24h.get("sharpe_ratio")
    profit_factor_24h_ago = stats_24h.get("profit_factor")
    # When trade pnl_pct is missing, approximate largest win/loss % from equity
    try:
        eq = float(equity) if equity is not None else None
    except (TypeError, ValueError):
        eq = None
    if eq and eq > 0:
        if stats.get("largest_win_pct") is None and stats.get("largest_win_usd") is not None:
            stats["largest_win_pct"] = round((stats["largest_win_usd"] / eq) * 100, 2)
        if stats.get("largest_loss_pct") is None and stats.get("largest_loss_usd") is not None:
            stats["largest_loss_pct"] = round((stats["largest_loss_usd"] / eq) * 100, 2)

    return {
        "equity": equity,
        "equity_time": equity_time,
        "total_trades": total,
        "won": won,
        "lost": lost,
        "win_rate_pct": win_rate,
        "win_rate_pct_24h_ago": win_rate_pct_24h_ago,
        "sharpe_ratio_24h_ago": sharpe_ratio_24h_ago,
        "profit_factor_24h_ago": profit_factor_24h_ago,
        "last_10_pnl_usd": last_10_pnl,
        "last_trade_time": last_trade_time,
        "open_positions": open_positions,
        "open_positions_count": len(open_positions),
        "last_10_trades": last_10,
        "all_trades": last_trades,
        **stats,
    }


def _load_oi_history_from_disk() -> None:
    """Load OI history from disk so oi_1h works after restarts and accumulates over time."""
    global oi_history
    if not OI_HISTORY_PATH.exists():
        return
    try:
        data = json.loads(OI_HISTORY_PATH.read_text())
        if not isinstance(data, dict):
            return
        now = datetime.now()
        cutoff = now - timedelta(hours=HISTORY_RETENTION_HOURS)
        for symbol, points in data.items():
            if symbol.startswith("_") or not isinstance(points, list):
                continue
            parsed = []
            for item in points:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                try:
                    ts_str, val = item[0], float(item[1])
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts.tzinfo:
                        ts = ts.replace(tzinfo=None)
                    if ts > cutoff:
                        parsed.append((ts, val))
                except (ValueError, TypeError):
                    continue
            if parsed:
                parsed.sort(key=lambda x: x[0])
                oi_history[symbol] = parsed
    except Exception:
        pass


def _save_oi_history_to_disk() -> None:
    """Persist OI history to disk (debounced)."""
    global _oi_history_last_save
    now = time.time()
    if now - _oi_history_last_save < OI_SAVE_DEBOUNCE_SEC:
        return
    _oi_history_last_save = now
    try:
        out = {}
        for symbol, points in oi_history.items():
            out[symbol] = [(ts.isoformat(), val) for ts, val in points]
        OI_HISTORY_PATH.write_text(json.dumps(out, separators=(",", ":")))
    except Exception:
        pass


def store_oi_history(symbol: str, oi: float, timestamp: datetime):
    """Store OI value with timestamp, clean up old data, persist to disk (debounced)."""
    global oi_history
    if symbol not in oi_history:
        oi_history[symbol] = []
    
    # Add new data point
    oi_history[symbol].append((timestamp, oi))
    
    # Clean up data older than retention period
    cutoff_time = timestamp - timedelta(hours=HISTORY_RETENTION_HOURS)
    oi_history[symbol] = [(ts, val) for ts, val in oi_history[symbol] if ts > cutoff_time]
    
    # Sort by timestamp (oldest first)
    oi_history[symbol].sort(key=lambda x: x[0])
    _save_oi_history_to_disk()


def get_oi_1h_ago(symbol: str, current_time: datetime) -> Optional[float]:
    """Get OI value from approximately 1 hour ago"""
    if symbol not in oi_history or not oi_history[symbol]:
        return None
    
    target_time = current_time - timedelta(hours=1)
    
    # Find closest data point to 1 hour ago (within ±5 minutes tolerance)
    tolerance = timedelta(minutes=5)
    best_match = None
    best_diff = None
    
    for ts, oi_val in oi_history[symbol]:
        diff = abs((ts - target_time).total_seconds())
        if diff <= tolerance.total_seconds():
            if best_diff is None or diff < best_diff:
                best_match = oi_val
                best_diff = diff
    
    # If no match within tolerance, use oldest available data if it's older than 1 hour
    if best_match is None:
        oldest_ts, oldest_oi = oi_history[symbol][0]
        if oldest_ts <= target_time:
            best_match = oldest_oi
    
    return best_match


def calculate_oi_change_pct(current_oi: Optional[float], oi_1h_ago: Optional[float]) -> Optional[float]:
    """Calculate OI change percentage: ((current - 1h_ago) / 1h_ago) * 100"""
    if current_oi is None or oi_1h_ago is None or oi_1h_ago == 0:
        return None
    
    change_pct = ((current_oi - oi_1h_ago) / oi_1h_ago) * 100
    return round(change_pct, 2)


async def fetch_oi_funding(symbol: str) -> tuple:
    """Fetch Open Interest and Funding Rate with aggressive refresh"""
    cache_key = symbol
    if cache_key in oi_funding_cache:
        cached_data, cached_time = oi_funding_cache[cache_key]
        age_seconds = (datetime.now() - cached_time).total_seconds()
        if age_seconds < cache_ttl:  # Use cache_ttl (15 seconds)
            return cached_data
    
    try:
        exchange = get_exchange()
        current_time = datetime.now()
        
        # Fetch OI (rate limited)
        await rate_limiter.acquire()
        oi_data = await asyncio.to_thread(exchange.fetch_open_interest, symbol)
        oi = oi_data.get('openInterestAmount', None) if oi_data else None
        
        # Store OI in history if we got a valid value
        if oi is not None:
            store_oi_history(symbol, oi, current_time)
        
        # Fetch funding rate (rate limited)
        await rate_limiter.acquire()
        funding_data = await asyncio.to_thread(exchange.fetch_funding_rate, symbol)
        funding_rate = funding_data.get('fundingRate', None) if funding_data else None
        
        result = (oi, funding_rate)
        oi_funding_cache[cache_key] = (result, current_time)
        return result
    except Exception as e:
        print(f"OI/Funding error {symbol}: {e}")
        # Return cached data if available, even if expired
        if cache_key in oi_funding_cache:
            cached_data, _ = oi_funding_cache[cache_key]
            return cached_data
        return None, None

@app.get("/arthurvega/fundingOI", response_model=VantageResponse)
async def get_funding_oi():
    """Funding & Open Interest endpoint
    Refreshes every 15 seconds, fetches all symbols in parallel (~3 seconds)
    Rate limit: 248 req/min (well within Binance's 1200 req/min limit)
    """
    results = []
    
    # Fetch all OI/Funding data in parallel with staggered rate limiting
    # This ensures we stay within Binance's 20 req/sec limit
    tasks = []
    for symbol in SYMBOLS:
        tasks.append((symbol, asyncio.create_task(fetch_oi_funding(symbol))))
    
    # Process results as they complete
    current_time = datetime.now()
    for symbol, oi_funding_task in tasks:
        try:
            oi_funding_result = await oi_funding_task
            if isinstance(oi_funding_result, tuple) and len(oi_funding_result) == 2:
                oi, funding_rate = oi_funding_result
            else:
                oi, funding_rate = None, None
            
            # Get OI from 1 hour ago
            oi_1h_ago = get_oi_1h_ago(symbol, current_time)
            
            # Calculate OI change percentage
            oi_change_pct = calculate_oi_change_pct(oi, oi_1h_ago)
            
            results.append(VantageSignal(
                s=symbol,
                oi=round(oi, 2) if oi else None,
                oi_1h=round(oi_1h_ago, 2) if oi_1h_ago else None,
                oi_change_pct=oi_change_pct,
                fr=round(funding_rate, 6) if funding_rate else None,
            ))
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            # Return cached data if available, otherwise None
            cache_key = symbol
            if cache_key in oi_funding_cache:
                cached_data, _ = oi_funding_cache[cache_key]
                if isinstance(cached_data, tuple) and len(cached_data) == 2:
                    oi, funding_rate = cached_data
                    # Try to get historical OI even for cached data
                    oi_1h_ago = get_oi_1h_ago(symbol, current_time)
                    oi_change_pct = calculate_oi_change_pct(oi, oi_1h_ago)
                    results.append(VantageSignal(
                        s=symbol,
                        oi=round(oi, 2) if oi else None,
                        oi_1h=round(oi_1h_ago, 2) if oi_1h_ago else None,
                        oi_change_pct=oi_change_pct,
                        fr=round(funding_rate, 6) if funding_rate else None,
                    ))
                    continue
            results.append(VantageSignal(s=symbol))
    
    return VantageResponse(
        ok=True,
        d=results,
        t=datetime.now().isoformat(),
    )


def _merge_live_into_summary(summary: Dict[str, Any], live: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Overwrite equity, open_positions, and when available win rate from live exchange data."""
    if not live or not isinstance(live, dict):
        return summary
    out = dict(summary)
    if "equity" in live and live["equity"] is not None:
        out["equity"] = live["equity"]
    if "open_positions" in live and isinstance(live["open_positions"], list):
        out["open_positions"] = live["open_positions"]
        out["open_positions_count"] = len(live["open_positions"])
    # Live win rate from exchange (e.g. HL user fills)
    if "win_rate_pct" in live and live.get("win_rate_pct") is not None:
        out["win_rate_pct"] = live["win_rate_pct"]
    if "total_trades" in live and live.get("total_trades") is not None:
        out["total_trades"] = live["total_trades"]
    if "won" in live and live.get("won") is not None:
        out["won"] = live["won"]
    if "lost" in live and live.get("lost") is not None:
        out["lost"] = live["lost"]
    # Live last 10 trades from exchange (includes losing trades)
    if "last_10_trades" in live and isinstance(live.get("last_10_trades"), list):
        out["last_10_trades"] = live["last_10_trades"]
    if "last_10_pnl_usd" in live and live.get("last_10_pnl_usd") is not None:
        out["last_10_pnl_usd"] = live["last_10_pnl_usd"]
    if "all_trades" in live and isinstance(live.get("all_trades"), list):
        out["all_trades"] = live["all_trades"]
        live_stats = _trade_stats(live["all_trades"])
        for k, v in live_stats.items():
            out[k] = v
        # When pnl_pct missing, approximate largest win/loss % from equity
        try:
            eq = float(out.get("equity")) if out.get("equity") is not None else None
        except (TypeError, ValueError):
            eq = None
        if eq and eq > 0:
            if out.get("largest_win_pct") is None and out.get("largest_win_usd") is not None:
                out["largest_win_pct"] = round((out["largest_win_usd"] / eq) * 100, 2)
            if out.get("largest_loss_pct") is None and out.get("largest_loss_usd") is not None:
                out["largest_loss_pct"] = round((out["largest_loss_usd"] / eq) * 100, 2)
    return out


@app.get("/portfolio")
async def get_portfolio_dashboard():
    """Hyperliquid portfolio summary for dashboard. Uses live positions/equity when env is set."""
    try:
        hl_perf = _load_json(HL_PERF_PATH)
        hl_pos = _load_json(HL_POS_PATH)
        hl_summary = _compute_summary(hl_perf, hl_pos)
        if fetch_live_hyperliquid:
            try:
                live_hl = await asyncio.to_thread(fetch_live_hyperliquid)
                if live_hl:
                    hl_summary = _merge_live_into_summary(hl_summary, live_hl)
            except Exception as e:
                # Log error but don't fail - use cached data
                import traceback
                print(f"⚠️  Live Hyperliquid fetch failed: {e}", flush=True)
                traceback.print_exc()
        # 24h-ago equity from snapshots (append current, return value closest to 24h ago)
        equity_now = hl_summary.get("equity")
        hl_summary["equity_24h_ago"] = _equity_snapshot_update_and_get_24h(equity_now)
        return {
            "ok": True,
            "t": datetime.now().isoformat(),
            "hyperliquid": hl_summary,
        }
    except Exception as e:
        import traceback
        print(f"❌ Portfolio dashboard error: {e}", flush=True)
        traceback.print_exc()
        return {
            "ok": False,
            "t": datetime.now().isoformat(),
            "error": str(e),
            "hyperliquid": {
                "equity": None,
                "open_positions": [],
                "open_positions_count": 0,
                "last_10_trades": [],
                "all_trades": [],
                "win_rate_pct": None,
                "total_trades": 0,
                "last_10_pnl_usd": None,
                "avg_profit_usd": None,
                "avg_loss_usd": None,
                "avg_profit_pct": None,
                "avg_loss_pct": None,
                "pl_ratio": None,
                "avg_total_pnl_usd": None,
                "avg_pnl_longs_usd": None,
                "avg_pnl_shorts_usd": None,
                "sharpe_ratio": None,
                "profit_factor": None,
                "equity_24h_ago": None,
                "win_rate_pct_24h_ago": None,
                "sharpe_ratio_24h_ago": None,
                "profit_factor_24h_ago": None,
                "largest_win_usd": None,
                "largest_loss_usd": None,
                "largest_win_pct": None,
                "largest_loss_pct": None,
                "overview_breakdown": None,
            },
        }


@app.get("/portfolio-dashboard", response_class=HTMLResponse)
async def portfolio_dashboard():
    """Simple HTML dashboard for Hyperliquid performance."""
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portfolio Dashboard - Hyperliquid</title>
  <style>
    :root {
      --bg: #0b1220;
      --panel: #121a2b;
      --muted: #8aa0b5;
      --text: #e7eef6;
      --accent: #40c3ff;
      --success: #38d39f;
      --danger: #ff7a7a;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: var(--bg); color: var(--text); }
    header { padding: 20px 28px; border-bottom: 1px solid #1f2a3c; display: flex; align-items: baseline; gap: 12px; }
    header h1 { margin: 0; font-size: 20px; }
    header .time { color: var(--muted); font-size: 12px; }
    .container { padding: 20px 28px 40px; display: grid; gap: 20px; }
    .grid { display: grid; gap: 14px; }
    .grid.cards { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    .panel { background: var(--panel); border: 1px solid #1f2a3c; border-radius: 10px; padding: 14px; }
    .panel h2 { margin: 0 0 10px; font-size: 15px; }
    .card .label { color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    .card .value { font-size: 18px; font-weight: 600; }
    .card .diff-24h { font-size: 11px; margin-top: 4px; }
    .value.success { color: var(--success); }
    .value.danger { color: var(--danger); }
    .diff-24h.success { color: var(--success); }
    .diff-24h.danger { color: var(--danger); }
    .diff-24h.muted { color: var(--muted); }
    .section-title { font-size: 16px; margin: 4px 0 0; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 8px; border-bottom: 1px solid #1f2a3c; text-align: left; }
    th { color: var(--muted); font-weight: 600; }
    .pill { padding: 2px 8px; border-radius: 999px; font-size: 11px; display: inline-block; }
    .pill.long { background: rgba(56, 211, 159, 0.12); color: var(--success); }
    .pill.short { background: rgba(255, 122, 122, 0.12); color: var(--danger); }
    .muted { color: var(--muted); }
    tr.totals-row { border-top: 2px solid #1f2a3c; font-weight: 600; }
    tr.totals-row td { padding-top: 10px; }
    .chart-panel { margin-left: -28px; margin-right: -28px; width: calc(100% + 56px); }
    .chart-panel h2 { padding-left: 28px; padding-right: 28px; margin-bottom: 12px; }
    .chart-panel .chart-wrapper { width: 100%; min-width: 100%; }
    .chart-container { width: 100%; height: 260px; overflow: hidden; position: relative; flex-shrink: 0; }
    .chart-container svg { display: block; width: 100%; height: 100%; overflow: hidden; }
    .chart-overview-wrap { width: 100%; height: 52px; margin-top: 6px; position: relative; overflow: hidden; }
    .chart-overview-svg { width: 100%; height: 100%; display: block; cursor: crosshair; }
    .chart-overview-svg svg { display: block; width: 100%; height: 100%; overflow: visible; }
    .chart-brush { fill: rgba(64, 195, 255, 0.2); stroke: var(--accent); stroke-width: 1; cursor: move; }
    .chart-brush-handle { cursor: ew-resize; }
    .chart-label { font-size: 11px; fill: var(--muted); }
    .chart-value { font-size: 10px; font-weight: 600; }
    .chart-tick { font-size: 10px; fill: var(--muted); }
    .chart-grid { stroke: var(--muted); stroke-width: 0.5; stroke-dasharray: 2; opacity: 0.5; }
    .chart-line { fill: none; stroke-width: 2; }
    .chart-line.positive { stroke: var(--success); }
    .chart-line.negative { stroke: var(--danger); }
    .chart-area { opacity: 0.15; }
    .chart-area.positive { fill: var(--success); }
    .chart-area.negative { fill: var(--danger); }
    .flash-up { animation: glow-green 1.4s ease-out; }
    .flash-down { animation: glow-red 1.4s ease-out; }
    @keyframes glow-green {
      0% { box-shadow: 0 0 14px var(--success), 0 0 20px rgba(56, 211, 159, 0.4); }
      60% { box-shadow: 0 0 10px var(--success), 0 0 14px rgba(56, 211, 159, 0.3); }
      100% { box-shadow: none; }
    }
    @keyframes glow-red {
      0% { box-shadow: 0 0 14px var(--danger), 0 0 20px rgba(255, 122, 122, 0.4); }
      60% { box-shadow: 0 0 10px var(--danger), 0 0 14px rgba(255, 122, 122, 0.3); }
      100% { box-shadow: none; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Portfolio Dashboard</h1>
    <div class="time" id="updated">Loading…</div>
  </header>
  <div class="container">
    <div class="panel chart-panel">
      <h2>Portfolio performance</h2>
      <div class="chart-wrapper">
        <div class="chart-container" id="pnl-chart-container"></div>
        <div class="chart-overview-wrap" id="pnl-chart-overview-wrap" style="display:none;">
          <div class="chart-overview-svg" id="pnl-chart-overview"></div>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>Hyperliquid</h2>
      <div class="grid cards" id="hl-cards"></div>
      <div class="section-title">Overview</div>
      <div class="panel" style="margin-top:10px; overflow-x:auto;">
        <table class="overview-table">
          <thead>
            <tr><th>Type</th><th>Total</th><th>Longs</th><th>Shorts</th></tr>
          </thead>
          <tbody id="hl-overview"></tbody>
        </table>
      </div>
      <div class="section-title">Open Positions (Live)</div>
      <div class="panel" style="margin-top:10px;">
        <table>
          <thead>
            <tr>
              <th>Symbol</th><th>Side</th><th>Entry</th><th>Size ($)</th><th>PnL ($)</th><th>PnL %</th><th>Qty</th><th>Lev</th><th>Opened</th>
            </tr>
          </thead>
          <tbody id="hl-positions"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const fmt = (v, digits=2) => (v === null || v === undefined) ? "—" : Number(v).toFixed(digits);
    const fmtPct = (v) => (v === null || v === undefined) ? "—" : `${Number(v).toFixed(2)}%`;
    const fmtTime = (t) => t ? new Date(t).toLocaleString() : "—";
    const fmtMoney = (v, digits=2) => (v === null || v === undefined) ? "—" : "$" + Number(v).toFixed(digits);
    const numFrom = (v) => { if (v == null || v === "" || v === "—") return null; const n = Number(v); return isNaN(n) ? null : n; };

    let _prevCards = null;
    const renderCards = (root, data, labelPrefix="") => {
      const cardKeys = ["equity", "win_rate_pct", "total_trades", "open_positions_count", "sharpe_ratio", "profit_factor", "largest_win_pct", "largest_loss_pct"];
      const rawValues = [data.equity, data.win_rate_pct, data.total_trades, data.open_positions_count, data.sharpe_ratio, data.profit_factor, data.largest_win_pct, data.largest_loss_pct];
      const cards = [
        { key: "equity", label: `${labelPrefix}Equity`, value: data.equity ?? "—", money: true, show24h: true, prevKey: "equity_24h_ago" },
        { key: "win_rate_pct", label: `${labelPrefix}Win Rate`, value: fmtPct(data.win_rate_pct), show24h: true, prevKey: "win_rate_pct_24h_ago" },
        { key: "total_trades", label: `${labelPrefix}Trades`, value: data.total_trades ?? 0 },
        { key: "open_positions_count", label: `${labelPrefix}Open Positions`, value: data.open_positions_count ?? 0 },
        { key: "sharpe_ratio", label: `${labelPrefix}Sharpe Ratio`, value: data.sharpe_ratio ?? "—", number: true, show24h: true, prevKey: "sharpe_ratio_24h_ago" },
        { key: "profit_factor", label: `${labelPrefix}Profit Factor`, value: data.profit_factor ?? "—", number: true, show24h: true, prevKey: "profit_factor_24h_ago" },
        { key: "largest_win_pct", label: `${labelPrefix}Largest Win`, value: data.largest_win_pct ?? "—", pct: true, pnlPositive: true },
        { key: "largest_loss_pct", label: `${labelPrefix}Largest Loss`, value: data.largest_loss_pct ?? "—", pct: true, pnlNegative: true },
      ];
      const diff24h = (cur, prev, key) => {
        if (cur == null || prev == null || prev === "" || prev === "—") return null;
        const c = Number(cur), p = Number(prev);
        if (isNaN(c) || isNaN(p)) return null;
        if (p === 0 && c !== 0) return { pct: 100, positive: true };
        if (p === 0) return null;
        const denom = (key === "sharpe_ratio") ? Math.abs(p) : p;
        if (denom === 0) return null;
        const pct = ((c - p) / denom) * 100;
        return { pct, positive: pct >= 0 };
      };
      root.innerHTML = cards.map((c, i) => {
        const numVal = (c.pnl || c.money || c.number || c.pct) && c.value !== "—" && c.value != null ? Number(c.value) : null;
        let cls = "";
        if (c.pnl) cls = numVal != null && numVal >= 0 ? "success" : "danger";
        else if (c.pnlPositive && numVal != null) cls = "success";
        else if (c.pnlNegative && numVal != null) cls = "danger";
        let display = c.value;
        if (c.pct) {
          if (numVal != null) display = (numVal >= 0 ? "+" : "") + Number(numVal).toFixed(2) + "%";
          else display = c.value;
        } else if (c.pnl || c.money) {
          if (numVal != null) display = (numVal >= 0 ? "+$" : "-$") + Math.abs(numVal).toFixed(2);
          else if (c.money && typeof c.value === "string" && c.value.includes("$")) display = c.value;
          else if (c.value !== "—" && c.value != null) display = fmtMoney(Number(c.value));
        } else if (c.number && numVal != null) display = String(numVal);
        let flash = "";
        if (_prevCards && rawValues[i] != null) {
          const prev = numFrom(_prevCards[c.key]);
          const cur = numFrom(rawValues[i]);
          if (prev != null && cur != null && prev !== cur) { flash = cur > prev ? " flash-up" : " flash-down"; }
        }
        let diffLine = "";
        if (c.show24h && c.prevKey) {
          const curRaw = c.key === "equity" ? data.equity : c.key === "win_rate_pct" ? data.win_rate_pct : c.key === "sharpe_ratio" ? data.sharpe_ratio : data.profit_factor;
          const prevRaw = data[c.prevKey];
          const d = diff24h(curRaw, prevRaw, c.key);
          if (d != null) {
            const sign = d.positive ? "+" : "";
            const diffCls = d.positive ? "success" : "danger";
            diffLine = `<div class="diff-24h ${diffCls}">${sign}${d.pct.toFixed(2)}% (24h)</div>`;
          } else {
            diffLine = `<div class="diff-24h muted">— (24h)</div>`;
          }
        }
        return `<div class="panel card${flash}"><div class="label">${c.label}</div><div class="value ${cls}">${display}</div>${diffLine}</div>`;
      }).join("");
      _prevCards = { equity: data.equity, win_rate_pct: data.win_rate_pct, total_trades: data.total_trades, open_positions_count: data.open_positions_count, sharpe_ratio: data.sharpe_ratio, profit_factor: data.profit_factor, largest_win_pct: data.largest_win_pct, largest_loss_pct: data.largest_loss_pct };
      setTimeout(() => { root.querySelectorAll(".flash-up, .flash-down").forEach(el => el.classList.remove("flash-up", "flash-down")); }, 1400);
    };

    const cellVal = (v, kind) => {
      if (v === null || v === undefined) return "—";
      const n = Number(v);
      if (kind === "money") return (n >= 0 ? "+$" : "-$") + Math.abs(n).toFixed(2);
      if (kind === "pct") return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
      if (kind === "pct_plain") return n.toFixed(2) + "%";
      if (kind === "pl_ratio") return n.toFixed(2) + ":1";
      return String(v);
    };
    const cellClass = (v, kind) => {
      if (v === null || v === undefined) return "";
      const n = Number(v);
      if (kind === "money" || kind === "pct") return n >= 0 ? "success" : "danger";
      return "";
    };

    let _prevBreakdown = null;
    const renderOverviewTable = (root, breakdown) => {
      if (!root) return;
      if (!breakdown || !breakdown.total) {
        root.innerHTML = "<tr><td class=\\"muted\\" colspan=\\"4\\">No trade data</td></tr>";
        _prevBreakdown = null;
        return;
      }
      const T = breakdown.total;
      const L = breakdown.longs || {};
      const S = breakdown.shorts || {};
      const rows = [
        { type: "Trades", total: T.trades, longs: L.trades, shorts: S.trades, kind: "int" },
        { type: "Volume", total: T.volume_usd, longs: L.volume_usd, shorts: S.volume_usd, kind: "money" },
        { type: "Winners", total: T.winners, longs: L.winners, shorts: S.winners, kind: "int" },
        { type: "Losers", total: T.losers, longs: L.losers, shorts: S.losers, kind: "int" },
        { type: "Win Rate", total: T.win_rate_pct, longs: L.win_rate_pct, shorts: S.win_rate_pct, kind: "pct_plain" },
        { type: "Avg PnL", total: T.avg_pnl_usd, longs: L.avg_pnl_usd, shorts: S.avg_pnl_usd, kind: "money" },
        { type: "Avg Profit", total: T.avg_profit_usd, longs: L.avg_profit_usd, shorts: S.avg_profit_usd, kind: "money" },
        { type: "Avg Loss", total: T.avg_loss_usd, longs: L.avg_loss_usd, shorts: S.avg_loss_usd, kind: "money" },
        { type: "Avg Profit %", total: T.avg_profit_pct, longs: L.avg_profit_pct, shorts: S.avg_profit_pct, kind: "pct" },
        { type: "Avg Loss %", total: T.avg_loss_pct, longs: L.avg_loss_pct, shorts: S.avg_loss_pct, kind: "pct" },
        { type: "P/L Ratio", total: T.pl_ratio, longs: L.pl_ratio, shorts: S.pl_ratio, kind: "pl_ratio" },
        { type: "Total PnL", total: T.total_pnl_usd, longs: L.total_pnl_usd, shorts: S.total_pnl_usd, kind: "money" },
        { type: "PnL%", total: T.pnl_pct, longs: null, shorts: null, kind: "pct" },
      ];
      const prev = _prevBreakdown;
      root.innerHTML = rows.map(r => {
        const fmt = (v) => r.kind === "int" ? (v != null ? String(v) : "—") : cellVal(v, r.kind);
        const cellCls = (v, k) => {
          if (k !== "money" && k !== "pct") return "";
          if (v === null || v === undefined) return "";
          const n = Number(v);
          const color = n >= 0 ? "success" : "danger";
          return "value " + color;
        };
        const flash = (cur, col) => {
          if (!prev || !prev.rowsByType) return "";
          const prevRow = prev.rowsByType[r.type];
          const prevVal = prevRow ? (col === "total" ? prevRow.total : col === "longs" ? prevRow.longs : prevRow.shorts) : null;
          const p = numFrom(prevVal);
          const c = numFrom(cur);
          if (p != null && c != null && p !== c) return c > p ? " flash-up" : " flash-down";
          return "";
        };
        const tdCls = (v, k, col) => (cellCls(v, k) + flash(v, col)).trim();
        return "<tr>" +
          "<td class=\\"muted\\">" + r.type + "</td>" +
          "<td class='" + tdCls(r.total, r.kind, "total") + "'>" + fmt(r.total) + "</td>" +
          "<td class='" + tdCls(r.longs, r.kind, "longs") + "'>" + fmt(r.longs) + "</td>" +
          "<td class='" + tdCls(r.shorts, r.kind, "shorts") + "'>" + fmt(r.shorts) + "</td>" +
          "</tr>";
      }).join("");
      _prevBreakdown = { total: T, longs: L, shorts: S, rowsByType: rows.reduce((acc, r) => { acc[r.type] = { total: r.total, longs: r.longs, shorts: r.shorts }; return acc; }, {}) };
      setTimeout(() => { root.querySelectorAll(".flash-up, .flash-down").forEach(el => el.classList.remove("flash-up", "flash-down")); }, 1400);
    };

    const renderPositions = (root, positions) => {
      if (!root) return;
      if (!positions || positions.length === 0) {
        root.innerHTML = `<tr><td class="muted" colspan="9">No open positions</td></tr>`;
        return;
      }
      let totalSize = 0;
      let totalPnlUsd = 0;
      const rows = positions.map(p => {
        const sizeUsdVal = p.position_size_usd != null ? Number(p.position_size_usd) : 0;
        const pnlUsdVal = p.pnl_usd != null ? Number(p.pnl_usd) : 0;
        totalSize += sizeUsdVal;
        totalPnlUsd += pnlUsdVal;
        const pnlPct = p.pnl_pct != null ? Number(p.pnl_pct) : null;
        const pnlUsd = p.pnl_usd != null ? Number(p.pnl_usd) : null;
        const pnlClass = (pnlPct != null || pnlUsd != null) ? (Math.max(pnlPct || 0, pnlUsd || 0) >= 0 ? "value success" : "value danger") : "";
        const pnlPctDisplay = pnlPct != null ? (pnlPct >= 0 ? "+" : "") + fmt(pnlPct, 2) + "%" : "—";
        const pnlUsdDisplay = pnlUsd != null ? (pnlUsd >= 0 ? "+" : "") + "$" + fmt(Math.abs(pnlUsd), 2) : "—";
        const sizeUsd = p.position_size_usd != null ? "$" + fmt(p.position_size_usd, 2) : "—";
        const opened = p.opened_at != null && p.opened_at !== "" ? fmtTime(p.opened_at) : "—";
        return `
        <tr>
          <td>${p.symbol}</td>
          <td><span class="pill ${String(p.side).toLowerCase().includes('short') ? 'short' : 'long'}">${p.side ?? "—"}</span></td>
          <td>${p.entry_price != null ? "$" + fmt(p.entry_price, 4) : "—"}</td>
          <td>${sizeUsd}</td>
          <td class="${pnlClass}">${pnlUsdDisplay}</td>
          <td class="${pnlClass}">${pnlPctDisplay}</td>
          <td>${fmt(p.entry_qty, 4)}</td>
          <td>${fmt(p.leverage, 1)}x</td>
          <td>${opened}</td>
        </tr>
      `;
      }).join("");
      const totalPnlPct = totalSize > 0 ? (totalPnlUsd / totalSize) * 100 : null;
      const totalPnlClass = totalPnlUsd >= 0 ? "value success" : "value danger";
      const totalPnlUsdDisplay = totalPnlUsd >= 0 ? "+$" + fmt(totalPnlUsd, 2) : "-$" + fmt(Math.abs(totalPnlUsd), 2);
      const totalPnlPctDisplay = totalPnlPct != null ? (totalPnlPct >= 0 ? "+" : "") + fmt(totalPnlPct, 2) + "%" : "—";
      const totalsRow = `
        <tr class="totals-row">
          <td>Total</td>
          <td></td>
          <td></td>
          <td>$${fmt(totalSize, 2)}</td>
          <td class="${totalPnlClass}">${totalPnlUsdDisplay}</td>
          <td class="${totalPnlClass}">${totalPnlPctDisplay}</td>
          <td></td>
          <td></td>
          <td></td>
        </tr>`;
      root.innerHTML = rows + totalsRow;
    };

    function renderPnlChart(mainContainer, overviewWrap, trades) {
      if (!mainContainer) return;
      const fmtChart = (v) => (v >= 0 ? "+" : "") + "$" + Number(v).toFixed(2);
      const fmtTooltipTime = (t) => t ? new Date(t).toLocaleString() : "—";
      const escapeTitle = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (!trades || trades.length === 0) {
        mainContainer.innerHTML = "<svg viewBox=\\"0 0 520 220\\" preserveAspectRatio=\\"xMidYMid meet\\" overflow=\\"hidden\\"><text x=\\"260\\" y=\\"110\\" class=\\"chart-label\\" text-anchor=\\"middle\\">No trade data</text></svg>";
        if (overviewWrap) overviewWrap.style.display = "none";
        return;
      }
      const chronological = trades.slice().reverse();
      const cumulative = [];
      let sum = 0;
      for (const t of chronological) {
        sum += Number(t.pnl_usd) || 0;
        cumulative.push(sum);
      }
      const n = cumulative.length;
      const timestamps = chronological.map(t => (t && t.time) ? new Date(t.time).getTime() : null);
      const validTs = timestamps.filter(x => x != null);
      const useTimeAxis = validTs.length >= 2;
      const minT = useTimeAxis ? Math.min(...validTs) : 0;
      const maxT = useTimeAxis ? Math.max(...validTs) : 1;
      if (window.__pnlChartDataLen !== n) window.__pnlChartRange = [0, 1];
      window.__pnlChartDataLen = n;
      let range = window.__pnlChartRange || [0, 1];
      range = [Math.max(0, range[0]), Math.min(1, range[1])];
      if (range[1] <= range[0]) range = [0, 1];
      const ow = 520, oh = 48;

      function getStartEnd() {
        const startIdx = Math.floor(range[0] * (n - 1));
        const endIdx = Math.min(n - 1, Math.ceil(range[1] * (n - 1)));
        return [Math.max(0, startIdx), Math.max(startIdx, endIdx)];
      }

      function renderMain() {
        const [startIdx, endIdx] = getStartEnd();
        const count = endIdx - startIdx + 1;
        const minT_win = useTimeAxis ? (timestamps[startIdx] ?? minT) : startIdx;
        const maxT_win = useTimeAxis ? (timestamps[endIdx] ?? maxT) : endIdx;
        const padding = { top: 28, right: 24, bottom: 44, left: 58 };
        const w = 520, h = 220;
        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;
        const minY = Math.min(0, ...cumulative);
        const maxY = Math.max(0, ...cumulative);
        const rangeY = maxY - minY || 1;
        const scaleY = (v) => padding.top + chartH - ((v - minY) / rangeY) * chartH;
        const scaleX_win = useTimeAxis
          ? (ts) => padding.left + ((ts - minT_win) / (maxT_win - minT_win || 1)) * chartW
          : (i) => padding.left + ((i - startIdx) / Math.max(1, count - 1)) * chartW;
        const xAt = (i) => useTimeAxis ? scaleX_win(timestamps[i] ?? minT_win) : scaleX_win(i);
        const zeroY = scaleY(0);
        const yTicks = [];
        const step = rangeY / 4;
        for (let i = 0; i <= 4; i++) yTicks.push(minY + step * i);
        const gridLines = yTicks.map((val) => "<line x1=\\"" + padding.left + "\\" y1=\\"" + scaleY(val) + "\\" x2=\\"" + (w - padding.right) + "\\" y2=\\"" + scaleY(val) + "\\" class=\\"chart-grid\\"/>").join("");
        const yLabels = yTicks.map((val) => "<text x=\\"" + (padding.left - 6) + "\\" y=\\"" + (scaleY(val) + 3) + "\\" class=\\"chart-tick\\" text-anchor=\\"end\\">" + fmtChart(val) + "</text>").join("");
        let segmentPaths = "", segmentAreas = "";
        for (let i = startIdx; i < endIdx; i++) {
          const trade = chronological[i + 1];
          const pnl = Number(trade && trade.pnl_usd) || 0;
          const legPositive = pnl >= 0;
          const lineClass = "chart-line " + (legPositive ? "positive" : "negative");
          const areaClass = "chart-area " + (legPositive ? "positive" : "negative");
          const x0 = xAt(i), y0 = scaleY(cumulative[i]);
          const x1 = xAt(i + 1), y1 = scaleY(cumulative[i + 1]);
          segmentPaths += "<path d=\\"M " + x0 + "," + y0 + " L " + x1 + "," + y1 + "\\" class=\\"" + lineClass + "\\"/>";
          segmentAreas += "<path d=\\"M " + x0 + "," + zeroY + " L " + x0 + "," + y0 + " L " + x1 + "," + y1 + " L " + x1 + "," + zeroY + " Z\\" class=\\"" + areaClass + "\\"/>";
        }
        const showValueLabels = count <= 25;
        const xStep = count > 20 ? Math.max(1, Math.floor(count / 14)) : 1;
        const dayKey = (t) => t && t.time ? (d => d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate())(new Date(t.time)) : "";
        const fmtXLabel = (trade) => !trade || !trade.time ? "" : (d => d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: d.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined }))(new Date(trade.time));
        let circles = "", valueLabels = "", xLabels = "", lastDayKey = "";
        for (let i = startIdx; i <= endIdx; i++) {
          const trade = chronological[i];
          const pnl = Number(trade && trade.pnl_usd) || 0;
          const y = cumulative[i];
          const cx = xAt(i), cy = scaleY(y);
          const col = pnl >= 0 ? "var(--success)" : "var(--danger)";
          const r = count > 40 ? 2 : 3;
          const pnlPct = trade && trade.pnl_pct != null ? Number(trade.pnl_pct) : null;
          const pnlPctStr = pnlPct != null ? (pnlPct >= 0 ? "+" : "") + pnlPct.toFixed(2) + "%" : "—";
          const tooltipLines = escapeTitle((trade && trade.symbol) || "—") + "\\nPnL: " + (pnl >= 0 ? "+" : "") + "$" + pnl.toFixed(2) + "\\nPnL %: " + pnlPctStr + "\\nTime: " + escapeTitle(fmtTooltipTime(trade && trade.time));
          circles += "<circle cx=\\"" + cx + "\\" cy=\\"" + cy + "\\" r=\\"" + r + "\\" fill=\\"" + col + "\\" stroke=\\"var(--panel)\\" stroke-width=\\"1.2\\"><title>" + tooltipLines + "</title></circle>";
          if (showValueLabels) valueLabels += "<text x=\\"" + cx + "\\" y=\\"" + (cy + (y >= 0 ? -8 : 14)) + "\\" class=\\"chart-value\\" fill=\\"" + col + "\\" text-anchor=\\"middle\\">" + fmtChart(y) + "</text>";
          const dk = dayKey(trade);
          const isFirstOfDay = useTimeAxis && dk && dk !== lastDayKey;
          if (isFirstOfDay) lastDayKey = dk;
          const showXLabel = isFirstOfDay || (!useTimeAxis && ((i - startIdx) % xStep === 0 || i === endIdx));
          if (showXLabel) {
            const label = useTimeAxis ? fmtXLabel(trade) : ((count <= 20 && trade && trade.symbol) ? String(trade.symbol).replace(/^(.{0,8}).*/, "$1") : (i - startIdx + 1));
            if (label) xLabels += "<text x=\\"" + cx + "\\" y=\\"" + (h - 10) + "\\" class=\\"chart-tick\\" text-anchor=\\"middle\\">" + escapeTitle(String(label)) + "</text>";
          }
        }
        const zeroLine = "<line x1=\\"" + padding.left + "\\" y1=\\"" + zeroY + "\\" x2=\\"" + (w - padding.right) + "\\" y2=\\"" + zeroY + "\\" stroke=\\"var(--muted)\\" stroke-width=\\"0.8\\" stroke-dasharray=\\"4\\"/>";
        const lastVal = cumulative[endIdx];
        const summary = "<text x=\\"" + (w - padding.right) + "\\" y=\\"" + (padding.top - 6) + "\\" class=\\"chart-tick\\" text-anchor=\\"end\\">Total: " + fmtChart(lastVal) + " (" + count + " trade" + (count !== 1 ? "s" : "") + ")</text>";
        const title = "<text x=\\"" + padding.left + "\\" y=\\"" + (padding.top - 6) + "\\" class=\\"chart-label\\">Cumulative PnL ($)</text>";
        mainContainer.innerHTML = "<svg viewBox=\\"0 0 " + w + " " + h + "\\" preserveAspectRatio=\\"xMidYMid meet\\" overflow=\\"hidden\\">" + title + summary + gridLines + yLabels + segmentAreas + zeroLine + segmentPaths + circles + valueLabels + xLabels + "</svg>";
      }

      const scaleXFull = (i) => (i / Math.max(1, n - 1)) * (ow - 4) + 2;
      const scaleYOv = (v) => {
        const minY = Math.min(0, ...cumulative), maxY = Math.max(0, ...cumulative), r = maxY - minY || 1;
        return oh - 6 - ((v - minY) / r) * (oh - 12);
      };
      let ovPath = "M " + scaleXFull(0) + "," + scaleYOv(cumulative[0]);
      for (let i = 1; i < n; i++) ovPath += " L " + scaleXFull(i) + "," + scaleYOv(cumulative[i]);
      const brushX = range[0] * ow;
      const brushW = (range[1] - range[0]) * ow;

      function updateBrush() {
        const r = document.getElementById("pnl-brush-rect");
        if (r) { r.setAttribute("x", brushX); r.setAttribute("width", brushW); }
      }

      function buildOverviewSvg() {
        return "<svg viewBox=\\"0 0 " + ow + " " + oh + "\\" preserveAspectRatio=\\"none\\" style=\\"display:block;width:100%;height:100%\\"><path d=\\"" + ovPath + "\\" fill=\\"none\\" stroke=\\"var(--accent)\\" stroke-width=\\"1.5\\"/><rect id=\\"pnl-brush-rect\\" class=\\"chart-brush\\" x=\\"" + brushX + "\\" y=\\"0\\" width=\\"" + brushW + "\\" height=\\"" + oh + "\\"/></svg>";
      }

      if (overviewWrap) {
        overviewWrap.style.display = "block";
        overviewWrap.innerHTML = "<div class=\\"chart-overview-svg\\" id=\\"pnl-overview-svg\\">" + buildOverviewSvg() + "</div>";
        const svgEl = document.getElementById("pnl-overview-svg");
        if (svgEl) {
          const getFrac = (e) => {
            const rect = svgEl.getBoundingClientRect();
            return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
          };
          svgEl.addEventListener("mousedown", function(e) {
            const frac = getFrac(e);
            const rx = range[0] * ow, rw = (range[1] - range[0]) * ow;
            const xInRect = (frac * ow - rx) / rw;
            let mode = "pan";
            if (rw > 20) { if (xInRect < 0.15) mode = "resizeLeft"; else if (xInRect > 0.85) mode = "resizeRight"; }
            const startX = frac;
            const startRange = [range[0], range[1]];
            const onMove = (e2) => {
              const f = getFrac(e2);
              if (mode === "pan") {
                const delta = f - startX;
                let r0 = startRange[0] + delta, r1 = startRange[1] + delta;
                if (r0 < 0) { r1 -= r0; r0 = 0; }
                if (r1 > 1) { r0 -= (r1 - 1); r1 = 1; }
                range = [Math.max(0, r0), Math.min(1, r1)];
              } else if (mode === "resizeLeft") {
                range = [Math.max(0, Math.min(f, startRange[1] - 0.02)), startRange[1]];
              } else if (mode === "resizeRight") {
                range = [startRange[0], Math.min(1, Math.max(f, startRange[0] + 0.02))];
              }
              window.__pnlChartRange = range;
              const bx = range[0] * ow, bw = (range[1] - range[0]) * ow;
              const r = document.getElementById("pnl-brush-rect");
              if (r) { r.setAttribute("x", bx); r.setAttribute("width", bw); }
              renderMain();
            };
            const onUp = () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
          });
        }
      }

      renderMain();
    }

    async function load() {
      const updatedEl = document.getElementById("updated");
      try {
        const res = await fetch("/portfolio");
        if (!res.ok) {
          updatedEl.textContent = "Error: HTTP " + res.status + " — check server";
          renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), []);
          renderCards(document.getElementById("hl-cards"), {});
          renderOverviewTable(document.getElementById("hl-overview"), null);
          renderPositions(document.getElementById("hl-positions"), []);
          return;
        }
        let data;
        try {
          data = await res.json();
        } catch (e) {
          updatedEl.textContent = "Error: invalid response (not JSON)";
          renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), []);
          renderCards(document.getElementById("hl-cards"), {});
          renderOverviewTable(document.getElementById("hl-overview"), null);
          renderPositions(document.getElementById("hl-positions"), []);
          return;
        }
        if (!data || !data.ok) {
          updatedEl.textContent = data && data.error ? ("Error: " + data.error) : "Error: no data (ok=false or empty)";
          const hl = (data && data.hyperliquid) || {};
          const chartTrades = (hl.all_trades && hl.all_trades.length) ? hl.all_trades : (hl.last_10_trades || []);
          renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), chartTrades);
          renderCards(document.getElementById("hl-cards"), hl);
          renderOverviewTable(document.getElementById("hl-overview"), hl.overview_breakdown || null);
          renderPositions(document.getElementById("hl-positions"), hl.open_positions || []);
          return;
        }
        updatedEl.textContent = "Updated: " + new Date(data.t).toLocaleString();
        const hl = data.hyperliquid || {};
        const chartTrades = (hl.all_trades && hl.all_trades.length) ? hl.all_trades : (hl.last_10_trades || []);
        renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), chartTrades);
        renderCards(document.getElementById("hl-cards"), hl);
        renderOverviewTable(document.getElementById("hl-overview"), hl.overview_breakdown || null);
        renderPositions(document.getElementById("hl-positions"), hl.open_positions || []);
      } catch (err) {
        updatedEl.textContent = "Error: " + (err.message || "failed to load");
        renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), []);
        renderCards(document.getElementById("hl-cards"), {});
        renderOverviewTable(document.getElementById("hl-overview"), null);
        renderPositions(document.getElementById("hl-positions"), []);
      }
    }

    load();
    setInterval(load, 15000);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.get("/")
async def root():
    return {
        "name": "Vantage2 API",
        "endpoints": {
            "/arthurvega/fundingOI": "Open Interest & Funding Rate data",
            "/portfolio": "Hyperliquid portfolio summary (JSON)",
            "/portfolio-dashboard": "Portfolio dashboard (HTML)"
        },
        "description": "Modular API for trading data"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
