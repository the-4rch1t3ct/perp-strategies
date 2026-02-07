#!/usr/bin/env python3
"""
Vantage2 API - Modular Trading Data Endpoints
Endpoint: /arthurvega/fundingOI
Returns Open Interest and Funding Rate for all symbols
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import ccxt
from datetime import datetime, timedelta, timezone
import asyncio
from collections import deque
import time
import json
import os
from pathlib import Path

# Load .env file if it exists (for HL_ACCOUNT_ADDRESS, etc.)
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
    try:
        _load_oi_history_from_disk()
    except Exception as e:
        print(f"⚠️  OI history load failed (non-fatal): {e}", flush=True)


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


# Portfolio dashboard data (Hyperliquid)
CLAWD_MEMORY_DIR = Path("/home/botadmin/clawd/memory")
HL_PERF_PATH = CLAWD_MEMORY_DIR / "hyperliquid-trading-performance.json"
HL_POS_PATH = CLAWD_MEMORY_DIR / "hyperliquid-trading-positions.json"
# Rolling 24h: one snapshot file for all metrics (equity, win_rate_pct, sharpe_ratio, profit_factor). Persisted; survives restarts.
DASHBOARD_SNAPSHOTS_PATH = CLAWD_MEMORY_DIR / "dashboard_24h_snapshots.json"
DASHBOARD_SNAPSHOTS_MAX = 48  # keep last 48 entries (~30min interval over 24h)
# Daily equity snapshots (UTC midnight-based). Used for daily PnL calendar.
DASHBOARD_DAILY_EQUITY_PATH = CLAWD_MEMORY_DIR / "dashboard_daily_equity.json"
DASHBOARD_DAILY_EQUITY_MAX = 370  # ~1 year of daily snapshots
# After reset: only show trades that closed on or after this time (ISO ts). Set by reset_dashboard_data.sh.
DASHBOARD_PERFORMANCE_SINCE_PATH = CLAWD_MEMORY_DIR / "dashboard_performance_since.json"
TRADER_SETTINGS_PATH = CLAWD_MEMORY_DIR / "trader_settings.json"
BATCH_SETTINGS_PATH = CLAWD_MEMORY_DIR / "batch_api_settings.json"

# Optional live fetch for positions/equity (set env for HL to enable)
try:
    from api.portfolio_live import fetch_live_hyperliquid
except ImportError:
    try:
        from portfolio_live import fetch_live_hyperliquid
    except ImportError:
        fetch_live_hyperliquid = None

# Cache live HL data to avoid 429 and dashboard "flip" (alternating file vs API dataset)
_live_hl_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
LIVE_HL_CACHE_TTL = 60.0  # seconds — refresh at most once per minute; metrics/chart stay file-based
DASHBOARD_TRADES_SOURCE = os.getenv("DASHBOARD_TRADES_SOURCE", "live").strip().lower()  # "live" or "file"


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
    """Compute overview metrics. PnL% = ROE (total PnL / total margin) when leverage is present."""
    pnls = []
    win_trades = []
    loss_trades = []
    volume_usd = 0.0
    total_margin_usd = 0.0
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
            # Volume = open + close notional per position (when volume_usd present); else close notional only
            vol = t.get("volume_usd") if t.get("volume_usd") is not None else t.get("notional_usd")
            if vol is not None:
                volume_usd += float(vol)
            # Margin for ROE = position notional at entry / leverage (use close notional, not open+close)
            notional = t.get("notional_usd")
            lev = t.get("leverage")
            if notional is not None and lev is not None:
                try:
                    lv = float(lev)
                    if lv > 0:
                        total_margin_usd += float(notional) / lv
                    else:
                        total_margin_usd += float(notional)
                except (TypeError, ValueError):
                    total_margin_usd += float(notional)
            elif notional is not None:
                total_margin_usd += float(notional)
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
    total_margin_usd = round(total_margin_usd, 2) if total_margin_usd else None
    # ROE-style: PnL% = total PnL / total margin (with leverage); fallback to PnL/volume if no margin
    if include_pnl_pct and n:
        if total_margin_usd and total_margin_usd > 0:
            pnl_pct = round((sum(pnls) / total_margin_usd) * 100, 2)
        elif volume_usd and volume_usd > 0:
            pnl_pct = round((sum(pnls) / volume_usd) * 100, 2)
        else:
            pnl_pct = None
    else:
        pnl_pct = None
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


def _trading_pnl_since(trades: List[Dict[str, Any]], since_dt: datetime) -> float:
    """Sum of closed PnL (pnl_usd) for trades closed at or after since_dt. Excludes deposits/withdrawals."""
    # Normalize to naive UTC so we can compare with _parse_trade_time (always returns naive)
    if since_dt.tzinfo is not None:
        since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
    total = 0.0
    for t in trades or []:
        if not isinstance(t, dict):
            continue
        close_dt = _parse_trade_time(t)
        if close_dt is None or close_dt < since_dt:
            continue
        try:
            total += float(t.get("pnl_usd", 0) or 0)
        except (TypeError, ValueError):
            pass
    return round(total, 2)


def _max_drawdown_pct_since(
    trades: List[Dict[str, Any]],
    since_dt: datetime,
    start_equity: Optional[float],
) -> Optional[float]:
    """Max drawdown % since a start time, relative to full portfolio value (start_equity)."""
    if start_equity is None:
        return None
    try:
        eq0 = float(start_equity)
    except (TypeError, ValueError):
        return None
    if eq0 <= 0:
        return None
    # Normalize since_dt to naive UTC (same as _parse_trade_time)
    if since_dt.tzinfo is not None:
        since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
    pts = []
    for t in trades or []:
        if not isinstance(t, dict):
            continue
        close_dt = _parse_trade_time(t)
        if close_dt is None or close_dt < since_dt:
            continue
        try:
            pnl = float(t.get("pnl_usd", 0) or 0)
        except (TypeError, ValueError):
            continue
        pts.append((close_dt, pnl))
    if not pts:
        return 0.0
    pts.sort(key=lambda x: x[0])
    equity = eq0
    peak = equity
    max_dd_usd = 0.0
    for _, pnl in pts:
        equity += pnl
        if equity > peak:
            peak = equity
        dd_usd = peak - equity
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
    return round((max_dd_usd / eq0) * 100, 2)


def _load_daily_equity_by_day() -> Dict[str, float]:
    """Load persisted daily equity snapshots as day_iso -> equity (for PnL %)."""
    out: Dict[str, float] = {}
    if not DASHBOARD_DAILY_EQUITY_PATH.exists():
        return out
    try:
        data = json.loads(DASHBOARD_DAILY_EQUITY_PATH.read_text())
        snapshots = (data.get("snapshots") or []) if isinstance(data, dict) else []
    except Exception:
        return out
    for s in snapshots:
        if not isinstance(s, dict) or not s.get("day"):
            continue
        try:
            eq = float(s.get("equity", 0))
            if eq > 0:
                out[str(s["day"]).strip()] = eq
        except (TypeError, ValueError):
            continue
    return out


def _trading_pnl_by_day(
    trades: List[Dict[str, Any]],
    equity_by_day: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Daily closed PnL from trade history (UTC day). Only includes closed days (excludes today until after midnight UTC). Returns list of {day, pnl_usd, pnl_pct}. Deposit-neutral."""
    today_utc = datetime.now(timezone.utc).date()
    today_iso = today_utc.isoformat()
    by_day: Dict[str, float] = {}
    for t in trades or []:
        if not isinstance(t, dict):
            continue
        close_dt = _parse_trade_time(t)
        if close_dt is None:
            continue
        day_str = close_dt.date().isoformat()
        if day_str == today_iso:
            continue
        try:
            pnl = float(t.get("pnl_usd", 0) or 0)
        except (TypeError, ValueError):
            continue
        by_day[day_str] = by_day.get(day_str, 0.0) + pnl
    equity_by_day = equity_by_day or {}
    out = []
    for day_str in sorted(by_day.keys()):
        pnl_usd = round(by_day[day_str], 2)
        pnl_pct = None
        try:
            day_dt = datetime.fromisoformat(day_str).date()
            prev_day = (day_dt - timedelta(days=1)).isoformat()
            prev_equity = equity_by_day.get(prev_day)
            if prev_equity is not None and float(prev_equity) > 0:
                pnl_pct = round((pnl_usd / float(prev_equity)) * 100, 2)
        except (ValueError, TypeError):
            pass
        out.append({"day": day_str, "pnl_usd": pnl_usd, "pnl_pct": pnl_pct})
    return out


def _dashboard_snapshots_update_and_get_24h(
    current_equity: Optional[float],
    win_rate_pct: Optional[float],
    sharpe_ratio: Optional[float],
    sortino_ratio: Optional[float],
    profit_factor: Optional[float],
) -> Dict[str, Optional[float]]:
    """Append current metrics to rolling snapshots, trim to last 48, return values closest to now-24h for each. Persisted; survives restarts."""
    now = datetime.now()
    cutoff_48h = now - timedelta(hours=48)
    target_24h = now - timedelta(hours=24)
    try:
        eq = float(current_equity) if current_equity is not None else None
    except (TypeError, ValueError):
        eq = None
    wr = None
    if win_rate_pct is not None:
        try:
            wr = float(win_rate_pct)
        except (TypeError, ValueError):
            pass
    sh = None
    if sharpe_ratio is not None:
        try:
            sh = float(sharpe_ratio)
        except (TypeError, ValueError):
            pass
    so = None
    if sortino_ratio is not None:
        try:
            so = float(sortino_ratio)
        except (TypeError, ValueError):
            pass
    pf = None
    if profit_factor is not None:
        try:
            pf = float(profit_factor)
        except (TypeError, ValueError):
            pass

    snapshots = []
    if DASHBOARD_SNAPSHOTS_PATH.exists():
        try:
            data = json.loads(DASHBOARD_SNAPSHOTS_PATH.read_text())
            snapshots = (data.get("snapshots") or []) if isinstance(data, dict) else []
        except Exception:
            snapshots = []
    snapshots.append({
        "ts": now.isoformat(),
        "equity": round(eq, 2) if eq is not None else None,
        "win_rate_pct": round(wr, 2) if wr is not None else None,
        "sharpe_ratio": round(sh, 2) if sh is not None else None,
        "sortino_ratio": round(so, 2) if so is not None else None,
        "profit_factor": round(pf, 2) if pf is not None else None,
    })
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
                parsed.append((t, s))
        except (ValueError, TypeError):
            continue
    parsed.sort(key=lambda x: x[0])
    if len(parsed) > DASHBOARD_SNAPSHOTS_MAX:
        parsed = parsed[-DASHBOARD_SNAPSHOTS_MAX:]
    try:
        CLAWD_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        out_snapshots = [{"ts": t.isoformat(), "equity": s.get("equity"), "win_rate_pct": s.get("win_rate_pct"), "sharpe_ratio": s.get("sharpe_ratio"), "sortino_ratio": s.get("sortino_ratio"), "profit_factor": s.get("profit_factor")} for t, s in parsed]
        DASHBOARD_SNAPSHOTS_PATH.write_text(json.dumps({"snapshots": out_snapshots}, separators=(",", ":")))
    except Exception:
        pass

    def _get_24h_value(key: str) -> Optional[float]:
        candidates = [(t, s.get(key)) for t, s in parsed if t <= target_24h and s.get(key) is not None]
        if candidates:
            best = min(candidates, key=lambda x: abs((x[0] - target_24h).total_seconds()))
            try:
                return round(float(best[1]), 2)
            except (TypeError, ValueError):
                return None
        if len(parsed) >= 2:
            first_val = parsed[0][1].get(key)
            if first_val is not None:
                try:
                    return round(float(first_val), 2)
                except (TypeError, ValueError):
                    pass
        return None

    return {
        "equity_24h_ago": _get_24h_value("equity"),
        "win_rate_pct_24h_ago": _get_24h_value("win_rate_pct"),
        "sharpe_ratio_24h_ago": _get_24h_value("sharpe_ratio"),
        "sortino_ratio_24h_ago": _get_24h_value("sortino_ratio"),
        "profit_factor_24h_ago": _get_24h_value("profit_factor"),
    }


def _load_dashboard_snapshots() -> List[Dict[str, Any]]:
    """Load rolling dashboard snapshots (equity + ratios)."""
    if not DASHBOARD_SNAPSHOTS_PATH.exists():
        return []
    try:
        data = json.loads(DASHBOARD_SNAPSHOTS_PATH.read_text())
        return (data.get("snapshots") or []) if isinstance(data, dict) else []
    except Exception:
        return []


def _max_drawdown_pct_from_snapshots_since(since_dt: datetime) -> Optional[float]:
    """Max drawdown % from equity snapshots since a given time (relative to peak equity)."""
    if since_dt.tzinfo is not None:
        since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
    snaps = _load_dashboard_snapshots()
    series = []
    for s in snaps:
        if not isinstance(s, dict):
            continue
        ts = s.get("ts")
        eq = s.get("equity")
        if ts is None or eq is None:
            continue
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if t.tzinfo:
                t = t.replace(tzinfo=None)
            if t < since_dt:
                continue
            eq_val = float(eq)
        except (TypeError, ValueError):
            continue
        series.append((t, eq_val))
    if len(series) < 2:
        return None
    series.sort(key=lambda x: x[0])
    peak = series[0][1]
    max_dd = 0.0
    for _, eq in series:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return round(max_dd * 100, 2)


def _dashboard_daily_equity_update_and_get(current_equity: Optional[float]) -> List[Dict[str, Any]]:
    """Update daily equity snapshots at UTC day boundaries and return daily PnL deltas."""
    snapshots = []
    if DASHBOARD_DAILY_EQUITY_PATH.exists():
        try:
            data = json.loads(DASHBOARD_DAILY_EQUITY_PATH.read_text())
            snapshots = (data.get("snapshots") or []) if isinstance(data, dict) else []
        except Exception:
            snapshots = []

    parsed = []
    for s in snapshots:
        if not isinstance(s, dict):
            continue
        day_str = s.get("day")
        eq_raw = s.get("equity")
        if not day_str:
            continue
        try:
            day_dt = datetime.fromisoformat(day_str).date()
        except (ValueError, TypeError):
            continue
        try:
            eq_val = float(eq_raw)
        except (TypeError, ValueError):
            continue
        parsed.append({"day": day_dt, "equity": round(eq_val, 2)})

    parsed.sort(key=lambda x: x["day"])

    eq_now = None
    if current_equity is not None:
        try:
            eq_now = float(current_equity)
        except (TypeError, ValueError):
            eq_now = None

    updated = False
    if eq_now is not None:
        today_utc = datetime.now(timezone.utc).date()
        last_day = parsed[-1]["day"] if parsed else None
        if last_day is None or last_day < today_utc:
            parsed.append({"day": today_utc, "equity": round(eq_now, 2)})
            updated = True

    if updated:
        if len(parsed) > DASHBOARD_DAILY_EQUITY_MAX:
            parsed = parsed[-DASHBOARD_DAILY_EQUITY_MAX:]
        try:
            CLAWD_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            out = [{"day": s["day"].isoformat(), "equity": s["equity"]} for s in parsed]
            DASHBOARD_DAILY_EQUITY_PATH.write_text(json.dumps({"snapshots": out}, separators=(",", ":")))
        except Exception:
            pass

    # Daily PnL: diff between consecutive UTC-midnight equity snapshots.
    daily = []
    for i in range(1, len(parsed)):
        prev = parsed[i - 1]
        cur = parsed[i]
        pnl = round(cur["equity"] - prev["equity"], 2)
        pnl_pct = None
        if prev["equity"] and prev["equity"] > 0:
            pnl_pct = round((pnl / prev["equity"]) * 100, 2)
        daily.append({
            "day": prev["day"].isoformat(),
            "pnl_usd": pnl,
            "pnl_pct": pnl_pct,
        })
    return daily


def _dashboard_apr_apy(
    current_equity: Optional[float],
    all_trades: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Optional[float]]:
    """Compute 1d/7d/30d APR and 30d APY from past equity + trading PnL (deposit-neutral). Returns pct values."""
    out = {"apr_1d_pct": None, "apr_7d_pct": None, "apr_30d_pct": None, "apy_30d_pct": None}
    try:
        eq_now = float(current_equity) if current_equity is not None else None
    except (TypeError, ValueError):
        eq_now = None
    if eq_now is None or eq_now <= 0:
        return out
    snapshots = []
    if DASHBOARD_DAILY_EQUITY_PATH.exists():
        try:
            data = json.loads(DASHBOARD_DAILY_EQUITY_PATH.read_text())
            snapshots = (data.get("snapshots") or []) if isinstance(data, dict) else []
        except Exception:
            snapshots = []
    by_day = {}
    for s in snapshots:
        if not isinstance(s, dict) or not s.get("day"):
            continue
        try:
            day = datetime.fromisoformat(str(s["day"]).strip()).date()
            eq = float(s.get("equity", 0))
        except (ValueError, TypeError):
            continue
        if eq > 0:
            by_day[day] = eq
    today_utc = datetime.now(timezone.utc).date()

    def equity_on_or_before(d):
        if d in by_day:
            return by_day[d]
        for past in sorted(by_day.keys(), reverse=True):
            if past <= d:
                return by_day[past]
        return None

    eq_1d = equity_on_or_before(today_utc - timedelta(days=1))
    eq_7d = equity_on_or_before(today_utc - timedelta(days=7))
    eq_30d = equity_on_or_before(today_utc - timedelta(days=30))

    # Use trading PnL over each period so deposits/withdrawals don't inflate APR/APY
    now_utc = datetime.now(timezone.utc)
    pnl_1d = _trading_pnl_since(all_trades or [], now_utc - timedelta(days=1))
    pnl_7d = _trading_pnl_since(all_trades or [], now_utc - timedelta(days=7))
    pnl_30d = _trading_pnl_since(all_trades or [], now_utc - timedelta(days=30))

    if eq_1d and eq_1d > 0:
        eq_effective_1d = eq_1d + pnl_1d
        if eq_effective_1d > 0:
            out["apr_1d_pct"] = round((eq_effective_1d / eq_1d - 1) * 365 * 100, 2)
    if eq_7d and eq_7d > 0:
        eq_effective_7d = eq_7d + pnl_7d
        if eq_effective_7d > 0:
            out["apr_7d_pct"] = round((eq_effective_7d / eq_7d - 1) * (365 / 7) * 100, 2)
    if eq_30d and eq_30d > 0:
        eq_effective_30d = eq_30d + pnl_30d
        if eq_effective_30d > 0:
            out["apr_30d_pct"] = round((eq_effective_30d / eq_30d - 1) * (365 / 30) * 100, 2)
            out["apy_30d_pct"] = round((pow(eq_effective_30d / eq_30d, 365 / 30) - 1) * 100, 2)
    return out


def _per_symbol_pnl(trades: List[Dict[str, Any]], equity: Optional[float] = None) -> List[Dict[str, Any]]:
    """Aggregate PnL by symbol. Returns list sorted by total_pnl_usd ascending (worst first)."""
    by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades or []:
        if not isinstance(t, dict):
            continue
        try:
            float(t.get("pnl_usd", 0) or 0)
        except (TypeError, ValueError):
            continue
        sym = (t.get("symbol") or t.get("coin") or "").strip()
        if not sym:
            continue
        if not sym.endswith("USDT") and not sym.endswith("usdt"):
            sym_display = sym + "USDT"
        else:
            sym_display = sym
        if sym_display not in by_symbol:
            by_symbol[sym_display] = []
        by_symbol[sym_display].append(t)
    out = []
    try:
        eq_val = float(equity) if equity is not None else None
    except (TypeError, ValueError):
        eq_val = None
    for symbol, sym_trades in by_symbol.items():
        pnls = [float(t.get("pnl_usd", 0) or 0) for t in sym_trades]
        total_pnl = round(sum(pnls), 2)
        avg_pnl = round(total_pnl / len(pnls), 2) if pnls else None
        pnl_pct_of_equity = round((total_pnl / eq_val) * 100, 2) if (eq_val and eq_val > 0) else None
        out.append({
            "symbol": symbol,
            "trades": len(sym_trades),
            "total_pnl_usd": total_pnl,
            "avg_pnl_usd": avg_pnl,
            "pnl_pct_of_equity": pnl_pct_of_equity,
        })
    out.sort(key=lambda x: x["total_pnl_usd"], reverse=False)  # worst first
    return out


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
    # Sortino: use downside deviation (only negative pnl)
    downside = [p for p in pnls if p < 0]
    if downside:
        downside_mean = sum(downside) / len(downside)
        downside_var = sum((p - downside_mean) ** 2 for p in downside) / len(downside)
        downside_std = (downside_var ** 0.5) if downside_var > 0 else 0
        sortino = round(mean_pnl / downside_std, 2) if downside_std > 0 else None
    else:
        sortino = None
    pl_ratio = round(avg_profit / abs(avg_loss), 2) if (avg_profit is not None and avg_loss is not None and avg_loss != 0) else None
    avg_total_pnl_usd = round(mean_pnl, 2) if n else None
    avg_pnl_longs_usd = round(sum(float(t.get("pnl_usd", 0) or 0) for t in long_trades) / len(long_trades), 2) if long_trades else None
    avg_pnl_shorts_usd = round(sum(float(t.get("pnl_usd", 0) or 0) for t in short_trades) / len(short_trades), 2) if short_trades else None
    # Overview breakdown: total, longs, shorts (PnL% only for total)
    total_bucket = _bucket_stats(valid, include_pnl_pct=True)
    total_bucket["largest_win_usd"] = largest_win
    total_bucket["largest_loss_usd"] = largest_loss
    total_bucket["largest_win_pct"] = largest_win_pct
    total_bucket["largest_loss_pct"] = largest_loss_pct
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
        "sortino_ratio": sortino,
        "profit_factor": profit_factor,
        "largest_win_usd": largest_win,
        "largest_loss_usd": largest_loss,
        "largest_win_pct": largest_win_pct,
        "largest_loss_pct": largest_loss_pct,
        "overview_breakdown": overview_breakdown,
    }


def _enrich_last_trades_with_volume(perf: Dict[str, Any], last_trades: list) -> list:
    """Add volume_usd (open+close) and notional_usd to file-based trades when missing, using signals[symbol].last_trades."""
    if not last_trades or not isinstance(perf, dict):
        return last_trades
    signals = perf.get("signals") or {}
    # Build key -> (volume_usd, notional_usd) from per-symbol last_trades (have entry, exit, qty)
    by_key = {}
    for sym, data in signals.items():
        if not isinstance(data, dict):
            continue
        for t in (data.get("last_trades") or []):
            if not isinstance(t, dict):
                continue
            try:
                entry = float(t.get("entry") or 0)
                exit_px = float(t.get("exit") or 0)
                eq = float(t.get("entry_qty") or t.get("exit_qty") or 0)
            except (TypeError, ValueError):
                continue
            if entry <= 0 or exit_px <= 0 or eq <= 0:
                continue
            vol = round(entry * eq + exit_px * eq, 2)
            notional = round(exit_px * eq, 2)
            time_str = (t.get("time") or "").strip()[:19]
            pnl_str = str(t.get("pnl_usd", "")) if t.get("pnl_usd") is not None else ""
            by_key[(sym, time_str, pnl_str)] = (vol, notional)
    # Enrich global last_trades (copy so we don't mutate persisted data)
    out = []
    for t in last_trades:
        if not isinstance(t, dict):
            out.append(t)
            continue
        row = dict(t)
        if row.get("volume_usd") is not None and row.get("notional_usd") is not None:
            out.append(row)
            continue
        sym = (row.get("symbol") or "").strip()
        time_str = (row.get("time") or "")[:19]
        pnl_str = str(row.get("pnl_usd", "")) if row.get("pnl_usd") is not None else ""
        for k in [(sym, time_str, pnl_str), (sym, time_str, "")]:
            if k in by_key:
                vol, notional = by_key[k]
                row["volume_usd"] = vol
                row["notional_usd"] = notional
                break
        out.append(row)
    return out


def _compute_summary(perf: Dict[str, Any], positions: Dict[str, Any]) -> Dict[str, Any]:
    last_10 = perf.get("last_10", []) if isinstance(perf, dict) else []
    last_trades_raw = perf.get("last_trades", []) if isinstance(perf, dict) else []
    last_trades = _enrich_last_trades_with_volume(perf, last_trades_raw)
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
    last_10_pnl = round(sum(float(t.get("pnl_usd", 0) or 0) for t in last_10 if isinstance(t, dict)), 2)
    last_trade_time = (last_trades[-1].get("time") if isinstance(last_trades[-1], dict) else None) if last_trades else None
    meta = perf.get("meta", {}) if isinstance(perf, dict) else {}
    equity = meta.get("last_equity")
    equity_time = meta.get("last_equity_time")

    open_positions = _extract_open_positions(positions)
    stats = _trade_stats(last_trades)
    # 24h-ago values come from rolling dashboard snapshots in get_portfolio_dashboard (persisted, survives restarts)
    win_rate_pct_24h_ago = None
    sharpe_ratio_24h_ago = None
    profit_factor_24h_ago = None
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


def _get_performance_since() -> Optional[datetime]:
    """Return the 'performance since' cutoff (only show trades closed on or after this time). Set by reset script."""
    if not DASHBOARD_PERFORMANCE_SINCE_PATH.exists():
        return None
    try:
        data = json.loads(DASHBOARD_PERFORMANCE_SINCE_PATH.read_text())
        ts_str = (data or {}).get("ts")
        if not ts_str:
            return None
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _merge_live_into_summary(
    summary: Dict[str, Any],
    live: Optional[Dict[str, Any]],
    merge_trades_and_stats: bool = False,
    filter_since: bool = True,
) -> Dict[str, Any]:
    """Merge live data into summary. Always merges equity and open_positions. Trades/chart/stats only merged when merge_trades_and_stats=True."""
    if not live or not isinstance(live, dict):
        return summary
    out = dict(summary)
    if "equity" in live and live["equity"] is not None:
        out["equity"] = live["equity"]
    if "open_positions" in live and isinstance(live["open_positions"], list):
        out["open_positions"] = live["open_positions"]
        out["open_positions_count"] = len(live["open_positions"])
    # Only overwrite chart/stats from live when requested (no file-based trades). Otherwise keep file-based so dashboard stays stable.
    if not merge_trades_and_stats:
        return out
    if "all_trades" in live and isinstance(live.get("all_trades"), list):
        since_dt = _get_performance_since() if filter_since else None
        all_trades = list(live["all_trades"])
        last_10_trades = list(live.get("last_10_trades") or [])
        if since_dt:
            all_trades = [t for t in all_trades if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) >= since_dt]
            last_10_trades = [t for t in last_10_trades if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) >= since_dt]
            last_10_trades = sorted(last_10_trades, key=lambda x: (_parse_trade_time(x) or datetime.min), reverse=True)[:10]
        out["all_trades"] = all_trades
        live_stats = _trade_stats(all_trades)
        for k, v in live_stats.items():
            out[k] = v
        total_bucket = (live_stats.get("overview_breakdown") or {}).get("total") or {}
        trades_count = total_bucket.get("trades")
        if trades_count is not None:
            out["total_trades"] = trades_count
        win_rate_live = total_bucket.get("win_rate_pct")
        if win_rate_live is not None:
            out["win_rate_pct"] = win_rate_live
        out["last_10_trades"] = last_10_trades
        out["last_10_pnl_usd"] = round(sum(float(t.get("pnl_usd", 0) or 0) for t in last_10_trades if isinstance(t, dict)), 2)
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


def _filter_perf_by_since(perf: Dict[str, Any], since_dt: datetime) -> Dict[str, Any]:
    """Return a copy of perf with last_trades and last_10 only including trades on or after since_dt."""
    if not perf or not since_dt:
        return perf
    out = dict(perf)
    for key in ("last_trades", "last_10"):
        if key not in out or not isinstance(out[key], list):
            continue
        filtered = [t for t in out[key] if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) >= since_dt]
        if key == "last_10":
            filtered = sorted(filtered, key=lambda x: (_parse_trade_time(x) or datetime.min), reverse=True)[:10]
        out[key] = filtered
    return out


def _apply_equity_based_pnl_pct(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Override total PnL% to be equity-based so it matches user expectations."""
    try:
        eq = summary.get("equity")
        total = (summary.get("overview_breakdown") or {}).get("total") or {}
        total_pnl = total.get("total_pnl_usd")
        if eq is None or total_pnl is None:
            return summary
        eq_val = float(eq)
        pnl_val = float(total_pnl)
        if eq_val <= 0:
            return summary
        total["pnl_pct"] = round((pnl_val / eq_val) * 100, 2)
    except (TypeError, ValueError):
        return summary
    return summary


@app.get("/portfolio")
async def get_portfolio_dashboard(range_filter: Optional[str] = Query(None, alias="range")):
    """Hyperliquid portfolio summary for dashboard. Uses live positions/equity when env is set. Query param range=24h|7d|30d|all filters overview and per-symbol PnL to that window."""
    try:
        hl_perf = _load_json(HL_PERF_PATH)
        hl_pos = _load_json(HL_POS_PATH)
        since_dt = _get_performance_since()
        if since_dt and hl_perf:
            hl_perf = _filter_perf_by_since(hl_perf, since_dt)
        hl_summary = _compute_summary(hl_perf, hl_pos)
        # Default: prefer live trades for accuracy; only fall back to file trades if live is unavailable.
        use_live_trades = (DASHBOARD_TRADES_SOURCE != "file")
        if fetch_live_hyperliquid:
            now_ts = time.time()
            if now_ts - _live_hl_cache["ts"] < LIVE_HL_CACHE_TTL and _live_hl_cache["data"] is not None:
                live_hl = _live_hl_cache["data"]
            else:
                try:
                    live_hl = await asyncio.wait_for(
                        asyncio.to_thread(fetch_live_hyperliquid),
                        timeout=25.0,
                    )
                    if live_hl is not None:
                        _live_hl_cache["data"] = live_hl
                        _live_hl_cache["ts"] = time.time()
                except asyncio.TimeoutError:
                    live_hl = _live_hl_cache["data"]
                    if live_hl is None:
                        print("⚠️  Live Hyperliquid fetch timed out (25s), using cached data", flush=True)
                except Exception as e:
                    live_hl = _live_hl_cache["data"]
                    if live_hl is None:
                        import traceback
                        print(f"⚠️  Live Hyperliquid fetch failed: {e}", flush=True)
                        traceback.print_exc()
            if live_hl:
                # If using live trades, do NOT apply performance-since filter; show full account history
                hl_summary = _merge_live_into_summary(
                    hl_summary,
                    live_hl,
                    merge_trades_and_stats=use_live_trades,
                    filter_since=False,
                )
        # Align total PnL% to equity (clearer than ROE on margin)
        hl_summary = _apply_equity_based_pnl_pct(hl_summary)

        # Rolling 24h: append current metrics to persisted snapshots, get values closest to 24h ago (or oldest)
        values_24h = _dashboard_snapshots_update_and_get_24h(
            hl_summary.get("equity"),
            hl_summary.get("win_rate_pct"),
            hl_summary.get("sharpe_ratio"),
            hl_summary.get("sortino_ratio"),
            hl_summary.get("profit_factor"),
        )
        # 24h equity change: use trading-only PnL so deposits/withdrawals don't inflate the diff
        all_trades = hl_summary.get("all_trades") or []
        now_utc = datetime.now(timezone.utc)
        trading_pnl_24h = _trading_pnl_since(all_trades, now_utc - timedelta(hours=24))
        eq_now = hl_summary.get("equity")
        try:
            eq_now_f = float(eq_now) if eq_now is not None else None
        except (TypeError, ValueError):
            eq_now_f = None
        if eq_now_f is not None:
            hl_summary["equity_24h_ago"] = round(eq_now_f - trading_pnl_24h, 2)
        else:
            hl_summary["equity_24h_ago"] = values_24h.get("equity_24h_ago")
        hl_summary["win_rate_pct_24h_ago"] = values_24h.get("win_rate_pct_24h_ago")
        hl_summary["sharpe_ratio_24h_ago"] = values_24h.get("sharpe_ratio_24h_ago")
        hl_summary["sortino_ratio_24h_ago"] = values_24h.get("sortino_ratio_24h_ago")
        hl_summary["profit_factor_24h_ago"] = values_24h.get("profit_factor_24h_ago")
        # Persist daily equity snapshot (for APR baseline); daily PnL from trades when available (deposit-neutral)
        daily_from_equity = _dashboard_daily_equity_update_and_get(hl_summary.get("equity"))
        equity_by_day = _load_daily_equity_by_day()
        if all_trades:
            hl_summary["daily_pnl"] = _trading_pnl_by_day(all_trades, equity_by_day=equity_by_day)
        else:
            hl_summary["daily_pnl"] = daily_from_equity

        # Max drawdown % since yesterday (UTC midnight) using equity snapshots (peak-to-trough)
        today_utc = datetime.now(timezone.utc).date()
        yesterday_utc = today_utc - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday_utc, datetime.min.time(), tzinfo=timezone.utc)
        max_dd_pct = _max_drawdown_pct_from_snapshots_since(yesterday_start)
        if max_dd_pct is None:
            # Fallback to trade-based curve if snapshots are missing
            start_equity = equity_by_day.get(yesterday_utc.isoformat())
            if start_equity is None and eq_now_f is not None:
                pnl_since_yesterday = _trading_pnl_since(all_trades, yesterday_start)
                start_equity = round(eq_now_f - pnl_since_yesterday, 2)
            max_dd_pct = _max_drawdown_pct_since(all_trades, yesterday_start, start_equity)
        if isinstance(hl_summary.get("overview_breakdown"), dict):
            total_bucket = hl_summary["overview_breakdown"].get("total")
            if isinstance(total_bucket, dict):
                total_bucket["max_drawdown_pct"] = max_dd_pct
        hl_summary["max_drawdown_pct"] = max_dd_pct
        apr_apy = _dashboard_apr_apy(hl_summary.get("equity"), all_trades=all_trades)
        hl_summary["apr_1d_pct"] = apr_apy.get("apr_1d_pct")
        hl_summary["apr_7d_pct"] = apr_apy.get("apr_7d_pct")
        hl_summary["apr_30d_pct"] = apr_apy.get("apr_30d_pct")
        hl_summary["apy_30d_pct"] = apr_apy.get("apy_30d_pct")

        # Time range filter for overview and per-symbol PnL
        now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        range_val = (range_filter or "all").strip().lower() if range_filter else "all"
        trades_for_range = all_trades
        if range_val == "24h":
            since_dt = now_naive_utc - timedelta(hours=24)
            trades_for_range = [t for t in all_trades if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) >= since_dt]
        elif range_val == "7d":
            since_dt = now_naive_utc - timedelta(days=7)
            trades_for_range = [t for t in all_trades if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) >= since_dt]
        elif range_val == "30d":
            since_dt = now_naive_utc - timedelta(days=30)
            trades_for_range = [t for t in all_trades if isinstance(t, dict) and _parse_trade_time(t) and _parse_trade_time(t) >= since_dt]
        else:
            range_val = "all"
        hl_summary["range"] = range_val
        hl_summary["per_symbol_pnl"] = _per_symbol_pnl(trades_for_range, eq_now_f)
        if range_val != "all":
            range_stats = _trade_stats(trades_for_range)
            hl_summary["overview_breakdown"] = range_stats.get("overview_breakdown") or hl_summary.get("overview_breakdown")
            total_bucket = (hl_summary.get("overview_breakdown") or {}).get("total")
            if isinstance(total_bucket, dict):
                total_bucket["max_drawdown_pct"] = None  # range-specific drawdown not computed
            hl_summary = _apply_equity_based_pnl_pct(hl_summary)

        return JSONResponse(
            {
                "ok": True,
                "t": datetime.now().isoformat(),
                "hyperliquid": hl_summary,
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    except Exception as e:
        import traceback
        print(f"❌ Portfolio dashboard error: {e}", flush=True)
        traceback.print_exc()
        return JSONResponse(
            {
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
                    "daily_pnl": [],
                    "apr_1d_pct": None,
                    "apr_7d_pct": None,
                    "apr_30d_pct": None,
                    "apy_30d_pct": None,
                    "range": "all",
                    "per_symbol_pnl": [],
                },
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        )


@app.get("/portfolio-settings")
async def get_portfolio_settings():
    """Load trader + batch API settings snapshots for dashboard."""
    return {
        "trader": _load_json(TRADER_SETTINGS_PATH),
        "batch_api": _load_json(BATCH_SETTINGS_PATH),
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
    .value.volume { color: #fff; }
    .diff-24h.success { color: var(--success); }
    .diff-24h.danger { color: var(--danger); }
    .diff-24h.muted { color: var(--muted); }
    .section-title { font-size: 16px; margin: 4px 0 0; }
    .overview-grid { display: grid; gap: 14px; margin-top: 10px; grid-template-columns: minmax(240px, 0.8fr) minmax(320px, 1.2fr); align-items: start; }
    @media (max-width: 900px) { .overview-grid { grid-template-columns: 1fr; } }
    .calendar-panel { display: flex; flex-direction: column; gap: 8px; min-height: 260px; }
    .calendar-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .calendar-title { font-size: 14px; font-weight: 600; }
    .calendar-controls { display: flex; align-items: center; gap: 8px; }
    .calendar-btn { background: #0f1726; border: 1px solid #1f2a3c; color: var(--text); border-radius: 6px; padding: 2px 8px; font-size: 12px; cursor: pointer; }
    .calendar-btn:disabled { opacity: 0.45; cursor: default; }
    .range-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    .sortable { cursor: pointer; user-select: none; }
    .sortable:hover { color: var(--accent); }
    .calendar-month { font-size: 12px; color: var(--muted); }
    .calendar-weekdays, .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
    .calendar-weekday { font-size: 10px; text-transform: uppercase; color: var(--muted); text-align: center; }
    .calendar-cell { border: 1px solid #1f2a3c; border-radius: 8px; padding: 6px; min-height: 62px; background: #0f1726; display: flex; flex-direction: column; gap: 2px; }
    .calendar-cell.empty { background: transparent; border: 1px dashed #1f2a3c; }
    .calendar-day { font-size: 11px; color: var(--muted); }
    .calendar-value { font-size: 12px; font-weight: 600; }
    .calendar-pct { font-size: 10px; color: var(--muted); }
    .calendar-cell.positive { background: rgba(56, 211, 159, 0.12); border-color: rgba(56, 211, 159, 0.35); }
    .calendar-cell.negative { background: rgba(255, 122, 122, 0.12); border-color: rgba(255, 122, 122, 0.35); }
    .calendar-cell.neutral { background: rgba(138, 160, 181, 0.08); }
    .settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
    .settings-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
    .settings-body { max-height: 420px; overflow-y: auto; border-radius: 12px; }
    .settings-subtitle { margin: 10px 0 6px; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .settings-table { font-size: 11px; }
    .settings-table td { vertical-align: top; }
    .settings-name { width: 42%; color: var(--muted); }
    .settings-value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; white-space: pre-wrap; word-break: break-word; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 8px; border-bottom: 1px solid #1f2a3c; text-align: left; }
    th { color: var(--muted); font-weight: 600; }
    .panel table thead th { position: sticky; top: 0; background: var(--panel); z-index: 1; }
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
      <div class="overview-grid">
        <div class="panel" style="overflow-x:auto;">
          <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; flex-wrap:wrap;">
            <span class="muted" style="font-size:12px;">Overview</span>
            <div class="range-selector" style="display:flex; gap:4px;">
              <button type="button" class="calendar-btn range-btn" data-range="24h" aria-label="Last 24 hours">24h</button>
              <button type="button" class="calendar-btn range-btn" data-range="7d" aria-label="Last 7 days">7d</button>
              <button type="button" class="calendar-btn range-btn" data-range="30d" aria-label="Last 30 days">30d</button>
              <button type="button" class="calendar-btn range-btn" data-range="all" aria-label="All time">All</button>
            </div>
          </div>
          <table class="overview-table">
            <thead>
              <tr><th>Type</th><th>Total</th></tr>
            </thead>
            <tbody id="hl-overview"></tbody>
          </table>
        </div>
        <div class="panel calendar-panel">
          <div class="calendar-header">
            <div class="calendar-title">PnL Calendar</div>
            <div class="calendar-controls">
              <button class="calendar-btn" id="pnl-calendar-prev" aria-label="Previous month">‹</button>
              <div class="calendar-month" id="pnl-calendar-label">—</div>
              <button class="calendar-btn" id="pnl-calendar-next" aria-label="Next month">›</button>
            </div>
          </div>
          <div class="calendar-weekdays" id="pnl-calendar-weekdays"></div>
          <div class="calendar-grid" id="pnl-calendar-grid"></div>
        </div>
      </div>
      <div class="section-title" id="per-symbol-pnl-title">Per symbol PnL</div>
      <div class="panel" style="margin-top:10px; max-height:320px; overflow-y:auto;">
        <p class="muted" style="margin:0 0 10px 0; font-size:12px;">Worst performers at the bottom — consider cutting low or negative symbols.</p>
        <table id="per-symbol-pnl-table">
          <thead>
            <tr>
              <th class="sortable" data-sort="symbol" title="Sort by asset">Asset</th>
              <th class="sortable" data-sort="trades" title="Sort by trades">Trades</th>
              <th class="sortable" data-sort="total_pnl_usd" title="Sort by PnL">PnL ($)</th>
              <th class="sortable" data-sort="avg_pnl_usd" title="Sort by avg PnL">Avg PnL</th>
              <th class="sortable" data-sort="pnl_pct_of_equity" title="Sort by PnL %">PnL % (of equity)</th>
            </tr>
          </thead>
          <tbody id="per-symbol-pnl-body"></tbody>
        </table>
      </div>
      <div class="section-title">Open Positions (Live)</div>
      <div class="panel" style="margin-top:10px; max-height:320px; overflow-y:auto;">
        <table>
          <thead>
            <tr>
              <th>Symbol</th><th>Side</th><th>Entry</th><th>Size ($)</th><th>PnL ($)</th><th>PnL %</th><th>Qty</th><th>Lev</th><th>Opened</th>
            </tr>
          </thead>
          <tbody id="hl-positions"></tbody>
        </table>
      </div>
      <div class="section-title">Deposit / Withdrawal</div>
      <div class="panel" style="margin-top:10px;">
        <p class="muted" style="margin:0 0 12px 0;">Move USDC to and from your Hyperliquid perpetuals account. PnL and APR on this dashboard are trading-only (deposits and withdrawals do not affect them).</p>
        <div style="margin-top:8px; display:flex; gap:12px; flex-wrap:wrap;">
          <a href="https://app.hyperliquid.xyz/withdraw" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:8px; padding:12px 16px; text-decoration:none; color:var(--accent); border:1px solid rgba(255,255,255,0.14); border-radius:12px; font-weight:600; background:var(--panel);">Deposit →</a>
          <a href="https://app.hyperliquid.xyz/withdraw" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:8px; padding:12px 16px; text-decoration:none; color:var(--accent); border:1px solid rgba(255,255,255,0.14); border-radius:12px; font-weight:600; background:var(--panel);">Withdraw →</a>
        </div>
      </div>
      <div class="section-title">Settings</div>
      <div class="settings-grid">
        <div class="panel">
          <div class="settings-header">
            <span>Trader</span>
            <span class="muted" id="trader-settings-meta">—</span>
          </div>
          <div class="settings-body">
            <table class="settings-table">
              <thead>
                <tr><th>Setting</th><th>Value</th></tr>
              </thead>
              <tbody id="trader-settings-body"></tbody>
            </table>
          </div>
        </div>
        <div class="panel">
          <div class="settings-header">
            <span>Batch API</span>
            <span class="muted" id="batch-settings-meta">—</span>
          </div>
          <div class="settings-body">
            <div class="settings-subtitle">Liquidation Heatmap API</div>
            <table class="settings-table">
              <thead>
                <tr><th>Setting</th><th>Value</th></tr>
              </thead>
              <tbody id="batch-settings-heatmap"></tbody>
            </table>
            <div class="settings-subtitle">Hyperliquid Batch</div>
            <table class="settings-table">
              <thead>
                <tr><th>Setting</th><th>Value</th></tr>
              </thead>
              <tbody id="batch-settings-hyperliquid"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const fmt = (v, digits=2) => (v === null || v === undefined) ? "—" : Number(v).toFixed(digits);
    const fmtPct = (v) => (v === null || v === undefined) ? "—" : `${Number(v).toFixed(2)}%`;
    const fmtTime = (t) => t ? new Date(t).toLocaleString() : "—";
    const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const fmtMoney = (v, digits=2) => (v === null || v === undefined) ? "—" : "$" + Number(v).toFixed(digits);
    const numFrom = (v) => { if (v == null || v === "" || v === "—") return null; const n = Number(v); return isNaN(n) ? null : n; };

    let _prevCards = null;
    const renderCards = (root, data, labelPrefix="") => {
      const cardKeys = ["equity", "win_rate_pct", "apr_1d_pct", "apr_7d_pct", "apr_30d_pct", "apy_30d_pct", "sharpe_ratio", "sortino_ratio", "profit_factor", "max_drawdown_pct"];
      const rawValues = [data.equity, data.win_rate_pct, data.apr_1d_pct, data.apr_7d_pct, data.apr_30d_pct, data.apy_30d_pct, data.sharpe_ratio, data.sortino_ratio, data.profit_factor, data.max_drawdown_pct];
      const cards = [
        { key: "equity", label: `${labelPrefix}Equity`, value: data.equity ?? "—", money: true, show24h: true, prevKey: "equity_24h_ago" },
        { key: "win_rate_pct", label: `${labelPrefix}Win Rate`, value: fmtPct(data.win_rate_pct), show24h: true, prevKey: "win_rate_pct_24h_ago", tooltip: "Percentage of closed trades that were profitable (winners ÷ total trades)." },
        { key: "apr_1d_pct", label: `${labelPrefix}1d APR`, value: data.apr_1d_pct, pctSigned: true, tooltip: "Annualized return from 1-day equity change." },
        { key: "apr_7d_pct", label: `${labelPrefix}7d APR`, value: data.apr_7d_pct, pctSigned: true, tooltip: "Annualized return from 7-day equity change." },
        { key: "apr_30d_pct", label: `${labelPrefix}30d APR`, value: data.apr_30d_pct, pctSigned: true, tooltip: "Annualized return from 30-day equity change." },
        { key: "apy_30d_pct", label: `${labelPrefix}30d APY`, value: data.apy_30d_pct, pctSigned: true, tooltip: "Annualized compounded return (30-day period)." },
        { key: "sharpe_ratio", label: `${labelPrefix}Sharpe Ratio`, value: data.sharpe_ratio ?? "—", number: true, show24h: true, prevKey: "sharpe_ratio_24h_ago", tooltip: "Risk-adjusted return: average PnL per trade ÷ standard deviation of PnL. Higher is better; above 1 is often considered good." },
        { key: "sortino_ratio", label: `${labelPrefix}Sortino Ratio`, value: data.sortino_ratio ?? "—", number: true, show24h: true, prevKey: "sortino_ratio_24h_ago", tooltip: "Risk-adjusted return using downside deviation only (penalizes losses more than gains)." },
        { key: "profit_factor", label: `${labelPrefix}Profit Factor`, value: data.profit_factor ?? "—", number: true, show24h: true, prevKey: "profit_factor_24h_ago", tooltip: "Gross profit ÷ gross loss from closed trades. Above 1 means total profits exceed total losses." },
        { key: "max_drawdown_pct", label: `${labelPrefix}Max Drawdown %`, value: data.max_drawdown_pct ?? "—", pctMinus: true, pnlNegative: true, tooltip: "Maximum peak-to-trough equity drop since yesterday, expressed as % of equity." },
      ];
      const diff24h = (cur, prev, key) => {
        if (cur == null || prev == null || prev === "" || prev === "—") return null;
        const c = Number(cur), p = Number(prev);
        if (isNaN(c) || isNaN(p)) return null;
        if (p === 0 && c !== 0) return { pct: 100, positive: true };
        if (p === 0) return null;
        const denom = (key === "sharpe_ratio" || key === "sortino_ratio") ? Math.abs(p) : p;
        if (denom === 0) return null;
        const pct = ((c - p) / denom) * 100;
        return { pct, positive: pct >= 0 };
      };
      root.innerHTML = cards.map((c, i) => {
        const numVal = (c.pnl || c.money || c.number || c.pct || c.pctSigned || c.pctMinus || c.pctPlain) && c.value !== "—" && c.value != null ? Number(c.value) : null;
        let cls = "";
        if (c.pnl) cls = numVal != null && numVal >= 0 ? "success" : "danger";
        else if (c.pnlPositive && numVal != null) cls = "success";
        else if (c.pnlNegative && numVal != null) cls = "danger";
        else if (c.pctSigned && numVal != null) cls = numVal >= 0 ? "success" : "danger";
        let display = c.value;
        if (c.pctMinus) {
          if (numVal != null) display = "-" + Number(numVal).toFixed(2) + "%";
          else display = c.value;
        } else if (c.pctPlain) {
          if (numVal != null) display = Number(numVal).toFixed(2) + "%";
          else display = c.value;
        } else if (c.pct) {
          if (numVal != null) display = (numVal >= 0 ? "+" : "") + Number(numVal).toFixed(2) + "%";
          else display = c.value;
        } else if (c.pctSigned) {
          if (numVal != null) display = (numVal >= 0 ? "+" : "") + Number(numVal).toFixed(2) + "%";
          else display = "—";
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
            let text = `${sign}${d.pct.toFixed(2)}% (24h)`;
            if (c.key === "equity" && curRaw != null && prevRaw != null) {
              const curN = Number(curRaw), prevN = Number(prevRaw);
              if (!isNaN(curN) && !isNaN(prevN)) {
                const delta = curN - prevN;
                const deltaStr = (delta >= 0 ? "+$" : "-$") + Math.abs(delta).toFixed(2);
                text = `${sign}${d.pct.toFixed(2)}% (${deltaStr}) (24h)`;
              }
            }
            diffLine = `<div class="diff-24h ${diffCls}">${text}</div>`;
          } else {
            diffLine = `<div class="diff-24h muted">— (24h)</div>`;
          }
        }
        const labelTitle = c.tooltip ? ` title="${c.tooltip.replace(/"/g, '&quot;')}"` : "";
        return `<div class="panel card${flash}"><div class="label"${labelTitle}>${c.label}</div><div class="value ${cls}">${display}</div>${diffLine}</div>`;
      }).join("");
      _prevCards = { equity: data.equity, win_rate_pct: data.win_rate_pct, apr_1d_pct: data.apr_1d_pct, apr_7d_pct: data.apr_7d_pct, apr_30d_pct: data.apr_30d_pct, apy_30d_pct: data.apy_30d_pct, sharpe_ratio: data.sharpe_ratio, sortino_ratio: data.sortino_ratio, profit_factor: data.profit_factor, max_drawdown_pct: data.max_drawdown_pct };
      setTimeout(() => { root.querySelectorAll(".flash-up, .flash-down").forEach(el => el.classList.remove("flash-up", "flash-down")); }, 1400);
    };

    const cellVal = (v, kind) => {
      if (v === null || v === undefined) return "—";
      const n = Number(v);
      if (kind === "volume") return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      if (kind === "money") return (n >= 0 ? "+$" : "-$") + Math.abs(n).toFixed(2);
      if (kind === "pct") return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
      if (kind === "pct_plain") return n.toFixed(2) + "%";
      if (kind === "pct_minus") return "-" + n.toFixed(2) + "%";
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
        root.innerHTML = "<tr><td class=\\"muted\\" colspan=\\"2\\">No trade data</td></tr>";
        _prevBreakdown = null;
        return;
      }
      const T = breakdown.total;
      const rows = [
        { type: "Trades", total: T.trades, kind: "int" },
        { type: "Volume", total: T.volume_usd, kind: "volume" },
        { type: "Winners", total: T.winners, kind: "int" },
        { type: "Losers", total: T.losers, kind: "int" },
        { type: "Win Rate", total: T.win_rate_pct, kind: "pct_plain" },
        { type: "Avg PnL", total: T.avg_pnl_usd, kind: "money" },
        { type: "Avg Profit", total: T.avg_profit_usd, kind: "money" },
        { type: "Avg Loss", total: T.avg_loss_usd, kind: "money" },
        { type: "Avg Profit %", total: T.avg_profit_pct, kind: "pct" },
        { type: "Avg Loss %", total: T.avg_loss_pct, kind: "pct" },
        { type: "P/L Ratio", total: T.pl_ratio, kind: "pl_ratio" },
        { type: "Total PnL", total: T.total_pnl_usd, kind: "money" },
        { type: "PnL%", total: T.pnl_pct, kind: "pct" },
        { type: "Largest Win", total: T.largest_win_usd, kind: "money" },
        { type: "Largest Loss", total: T.largest_loss_usd, kind: "money" },
        { type: "Max Drawdown %", total: T.max_drawdown_pct, kind: "pct_minus" },
      ];
      const prev = _prevBreakdown;
      root.innerHTML = rows.map(r => {
        const fmt = (v) => r.kind === "int" ? (v != null ? String(v) : "—") : cellVal(v, r.kind);
        const cellCls = (v, k) => {
          if (k === "pct_minus") return "value danger";
          if (k === "volume") return "value volume";
          if (k !== "money" && k !== "pct") return "";
          if (v === null || v === undefined) return "";
          const n = Number(v);
          const color = n >= 0 ? "success" : "danger";
          return "value " + color;
        };
        const flash = (cur, col) => {
          if (!prev || !prev.rowsByType) return "";
          const prevRow = prev.rowsByType[r.type];
          const prevVal = prevRow ? prevRow.total : null;
          const p = numFrom(prevVal);
          const c = numFrom(cur);
          if (p != null && c != null && p !== c) return c > p ? " flash-up" : " flash-down";
          return "";
        };
        const tdCls = (v, k) => (cellCls(v, k) + flash(v, "total")).trim();
        return "<tr>" +
          "<td class=\\"muted\\">" + r.type + "</td>" +
          "<td class='" + tdCls(r.total, r.kind) + "'>" + fmt(r.total) + "</td>" +
          "</tr>";
      }).join("");
      _prevBreakdown = { total: T, rowsByType: rows.reduce((acc, r) => { acc[r.type] = { total: r.total }; return acc; }, {}) };
      setTimeout(() => { root.querySelectorAll(".flash-up, .flash-down").forEach(el => el.classList.remove("flash-up", "flash-down")); }, 1400);
    };

    let _perSymbolPnlList = [];
    let _perSymbolPnlSort = { col: "total_pnl_usd", dir: 1 };
    const assetDisplay = (sym) => (sym || "").replace(/USDT$/i, "") || "—";
    const sortPerSymbolList = (list) => {
      const col = _perSymbolPnlSort.col;
      const dir = _perSymbolPnlSort.dir;
      return list.slice().sort((a, b) => {
        let va = a[col], vb = b[col];
        if (col === "symbol") {
          va = (va || "").toLowerCase();
          vb = (vb || "").toLowerCase();
          return dir * (va < vb ? -1 : va > vb ? 1 : 0);
        }
        const na = va != null ? Number(va) : NaN;
        const nb = vb != null ? Number(vb) : NaN;
        if (isNaN(na) && isNaN(nb)) return 0;
        if (isNaN(na)) return dir;
        if (isNaN(nb)) return -dir;
        return dir * (na - nb);
      });
    };
    const renderPerSymbolPnl = (root, list, rangeLabel) => {
      if (!root) return;
      if (list != null) {
        _perSymbolPnlList = Array.isArray(list) ? list : [];
      }
      const listToRender = sortPerSymbolList(_perSymbolPnlList);
      if (listToRender.length === 0) {
        root.innerHTML = "<tr><td class=\\"muted\\" colspan=\\"5\\">No trade data for this range</td></tr>";
        return;
      }
      root.innerHTML = listToRender.map(row => {
        const pnl = row.total_pnl_usd != null ? Number(row.total_pnl_usd) : null;
        const pnlCls = pnl != null ? (pnl >= 0 ? "success" : "danger") : "";
        const pnlStr = pnl != null ? (pnl >= 0 ? "+$" : "-$") + Math.abs(pnl).toFixed(2) : "—";
        const avg = row.avg_pnl_usd != null ? Number(row.avg_pnl_usd) : null;
        const avgCls = avg != null ? (avg >= 0 ? "success" : "danger") : "";
        const avgStr = avg != null ? (avg >= 0 ? "+$" : "-$") + Math.abs(avg).toFixed(2) : "—";
        const pct = row.pnl_pct_of_equity != null ? Number(row.pnl_pct_of_equity).toFixed(2) + "%" : "—";
        const pctCls = row.pnl_pct_of_equity != null ? (row.pnl_pct_of_equity >= 0 ? "success" : "danger") : "";
        return "<tr>" +
          "<td class=\\"muted\\">" + assetDisplay(row.symbol) + "</td>" +
          "<td>" + (row.trades != null ? row.trades : "—") + "</td>" +
          "<td class=\\"value " + pnlCls + "\\">" + pnlStr + "</td>" +
          "<td class=\\"value " + avgCls + "\\">" + avgStr + "</td>" +
          "<td class=\\"value " + pctCls + "\\">" + pct + "</td>" +
          "</tr>";
      }).join("");
    };
    const setupPerSymbolSort = () => {
      const table = document.getElementById("per-symbol-pnl-table");
      if (!table || table.dataset.sortSetup) return;
      table.dataset.sortSetup = "1";
      table.querySelectorAll("thead th.sortable").forEach(th => {
        th.addEventListener("click", () => {
          const col = th.getAttribute("data-sort");
          if (!col) return;
          if (_perSymbolPnlSort.col === col) _perSymbolPnlSort.dir *= -1;
          else _perSymbolPnlSort = { col, dir: 1 };
          renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), null);
        });
      });
    };

    const renderPnlCalendar = (dailyPnl) => {
      const grid = document.getElementById("pnl-calendar-grid");
      const weekdays = document.getElementById("pnl-calendar-weekdays");
      const label = document.getElementById("pnl-calendar-label");
      const prevBtn = document.getElementById("pnl-calendar-prev");
      const nextBtn = document.getElementById("pnl-calendar-next");
      if (!grid || !weekdays || !label || !prevBtn || !nextBtn) return;
      if (!weekdays.dataset.init) {
        const names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        weekdays.innerHTML = names.map(n => `<div class="calendar-weekday">${n}</div>`).join("");
        weekdays.dataset.init = "1";
      }
      const pad = (n) => String(n).padStart(2, "0");
      const toKeyUTC = (d) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
      const stats = { byDay: {}, latestDate: null };
      const entries = Array.isArray(dailyPnl) ? dailyPnl : [];
      for (const e of entries) {
        if (!e || !e.day) continue;
        const dayStr = String(e.day);
        const dt = new Date(dayStr + "T00:00:00Z");
        if (isNaN(dt.getTime())) continue;
        if (!stats.latestDate || dt > stats.latestDate) stats.latestDate = dt;
        const pnl = e.pnl_usd != null ? Number(e.pnl_usd) : null;
        const pct = e.pnl_pct != null ? Number(e.pnl_pct) : null;
        stats.byDay[dayStr] = { pnl, pct };
      }
      if (!window.__pnlCalendarMonth) {
        const base = stats.latestDate || new Date();
        window.__pnlCalendarMonth = { y: base.getUTCFullYear(), m: base.getUTCMonth() };
      }
      const year = window.__pnlCalendarMonth.y;
      const month = window.__pnlCalendarMonth.m;
      const monthLabel = new Date(Date.UTC(year, month, 1)).toLocaleString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
      label.textContent = monthLabel;
      const shiftMonth = (delta) => {
        const d = new Date(Date.UTC(window.__pnlCalendarMonth.y, window.__pnlCalendarMonth.m + delta, 1));
        window.__pnlCalendarMonth = { y: d.getUTCFullYear(), m: d.getUTCMonth() };
      };
      prevBtn.onclick = () => { shiftMonth(-1); renderPnlCalendar(dailyPnl); };
      nextBtn.onclick = () => { shiftMonth(1); renderPnlCalendar(dailyPnl); };
      const first = new Date(Date.UTC(year, month, 1));
      const startDow = first.getUTCDay();
      const daysInMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
      const cells = [];
      for (let i = 0; i < startDow; i++) {
        cells.push(`<div class="calendar-cell empty"></div>`);
      }
      const fmtSignedMoney = (v) => (v >= 0 ? "+$" : "-$") + Math.abs(v).toFixed(2);
      for (let day = 1; day <= daysInMonth; day++) {
        const key = `${year}-${pad(month + 1)}-${pad(day)}`;
        const entry = stats.byDay[key];
        const pnl = entry && entry.pnl != null ? entry.pnl : null;
        const pct = entry && entry.pct != null ? entry.pct : null;
        const hasData = pnl != null && !isNaN(pnl);
        const cls = hasData ? (pnl > 0 ? "positive" : pnl < 0 ? "negative" : "neutral") : "neutral";
        const pnlText = hasData ? fmtSignedMoney(pnl) : "—";
        const pctText = (pct != null && !isNaN(pct)) ? ((pct >= 0 ? "+" : "") + pct.toFixed(2) + "%") : "—";
        cells.push(
          `<div class="calendar-cell ${cls}">` +
          `<div class="calendar-day">${day}</div>` +
          `<div class="calendar-value">${pnlText}</div>` +
          `<div class="calendar-pct">${pctText}</div>` +
          `</div>`
        );
      }
      const remainder = cells.length % 7;
      if (remainder !== 0) {
        for (let i = remainder; i < 7; i++) {
          cells.push(`<div class="calendar-cell empty"></div>`);
        }
      }
      grid.innerHTML = cells.join("");
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

    const formatSettingValue = (v) => {
      if (v === null || v === undefined) return "—";
      if (typeof v === "string") return v;
      try {
        return JSON.stringify(v);
      } catch (e) {
        return String(v);
      }
    };

    const renderSettingsTable = (root, settings) => {
      if (!root) return;
      const entries = settings && typeof settings === "object" ? Object.entries(settings) : [];
      if (entries.length === 0) {
        root.innerHTML = `<tr><td class="muted" colspan="2">No settings found</td></tr>`;
        return;
      }
      entries.sort((a, b) => a[0].localeCompare(b[0]));
      root.innerHTML = entries.map(([key, value]) => {
        const val = escapeHtml(formatSettingValue(value));
        return `<tr><td class="settings-name">${escapeHtml(key)}</td><td class="settings-value">${val}</td></tr>`;
      }).join("");
    };

    const renderSettingsMeta = (root, data) => {
      if (!root) return;
      const ts = data && data.generated_at ? data.generated_at : null;
      const pid = data && data.pid ? data.pid : null;
      root.textContent = ts ? ("Updated " + fmtTime(ts) + (pid ? " · PID " + pid : "")) : "No snapshot";
    };

    const fetchSettings = async () => {
      try {
        const res = await fetch("/portfolio-settings?_t=" + Date.now());
        if (!res.ok) throw new Error("settings fetch failed");
        const data = await res.json();
        const trader = data && data.trader ? data.trader : {};
        const batch = data && data.batch_api ? data.batch_api : {};
        renderSettingsMeta(document.getElementById("trader-settings-meta"), trader);
        renderSettingsMeta(document.getElementById("batch-settings-meta"), batch);
        renderSettingsTable(document.getElementById("trader-settings-body"), trader.settings || {});
        const batchSettings = batch.settings || {};
        renderSettingsTable(document.getElementById("batch-settings-heatmap"), batchSettings.liquidation_heatmap_api || {});
        renderSettingsTable(document.getElementById("batch-settings-hyperliquid"), batchSettings.hyperliquid_batch || {});
      } catch (err) {
        const errRow = `<tr><td class="muted" colspan="2">Error loading settings</td></tr>`;
        renderSettingsMeta(document.getElementById("trader-settings-meta"), {});
        renderSettingsMeta(document.getElementById("batch-settings-meta"), {});
        const traderRoot = document.getElementById("trader-settings-body");
        const batchHeatmapRoot = document.getElementById("batch-settings-heatmap");
        const batchHlRoot = document.getElementById("batch-settings-hyperliquid");
        if (traderRoot) traderRoot.innerHTML = errRow;
        if (batchHeatmapRoot) batchHeatmapRoot.innerHTML = errRow;
        if (batchHlRoot) batchHlRoot.innerHTML = errRow;
      }
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
        // Value labels on each point clutter the chart; rely on hover tooltips instead.
        const showValueLabels = false;
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

    let _dashboardRange = "all";
    function setRangeButtons(activeRange) {
      document.querySelectorAll(".range-btn").forEach(btn => {
        btn.classList.toggle("active", (btn.getAttribute("data-range") || "") === activeRange);
      });
    }
    async function load() {
      const updatedEl = document.getElementById("updated");
      const settingsPromise = fetchSettings();
      try {
        const rangeParam = _dashboardRange === "all" ? "" : "&range=" + encodeURIComponent(_dashboardRange);
        const res = await fetch("/portfolio?_t=" + Date.now() + rangeParam);
        if (!res.ok) {
          updatedEl.textContent = "Error: HTTP " + res.status + " — check server";
          renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), []);
          renderCards(document.getElementById("hl-cards"), {});
          renderOverviewTable(document.getElementById("hl-overview"), null);
          renderPnlCalendar([]);
          renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), [], null);
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
          renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), [], null);
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
          renderPnlCalendar(hl.daily_pnl || []);
          if (hl.per_symbol_pnl && Array.isArray(hl.per_symbol_pnl)) {
            renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), hl.per_symbol_pnl, hl.range);
            const t = document.getElementById("per-symbol-pnl-title"); if (t) t.textContent = hl.range && hl.range !== "all" ? "Per symbol PnL (" + hl.range + ")" : "Per symbol PnL";
          } else renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), [], null);
          renderPositions(document.getElementById("hl-positions"), hl.open_positions || []);
          return;
        }
        updatedEl.textContent = "Updated: " + new Date(data.t).toLocaleString();
        const hl = data.hyperliquid || {};
        const chartTrades = (hl.all_trades && hl.all_trades.length) ? hl.all_trades : (hl.last_10_trades || []);
        renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), chartTrades);
        renderCards(document.getElementById("hl-cards"), hl);
        renderOverviewTable(document.getElementById("hl-overview"), hl.overview_breakdown || null);
        renderPnlCalendar(hl.daily_pnl || []);
        renderPositions(document.getElementById("hl-positions"), hl.open_positions || []);
        if (hl.per_symbol_pnl && Array.isArray(hl.per_symbol_pnl)) {
          renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), hl.per_symbol_pnl, hl.range);
          const perSymbolTitle = document.getElementById("per-symbol-pnl-title");
          if (perSymbolTitle) perSymbolTitle.textContent = hl.range && hl.range !== "all" ? "Per symbol PnL (" + hl.range + ")" : "Per symbol PnL";
        } else {
          renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), [], null);
        }
        setRangeButtons(hl.range || "all");
        _dashboardRange = hl.range || "all";
      } catch (err) {
        updatedEl.textContent = "Error: " + (err.message || "failed to load");
        renderPnlChart(document.getElementById("pnl-chart-container"), document.getElementById("pnl-chart-overview-wrap"), []);
        renderCards(document.getElementById("hl-cards"), {});
        renderOverviewTable(document.getElementById("hl-overview"), null);
        renderPerSymbolPnl(document.getElementById("per-symbol-pnl-body"), [], null);
        renderPnlCalendar([]);
        renderPositions(document.getElementById("hl-positions"), []);
      } finally {
        try { await settingsPromise; } catch (e) {}
      }
    }

    setRangeButtons("all");
    setupPerSymbolSort();
    document.querySelectorAll(".range-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        _dashboardRange = btn.getAttribute("data-range") || "all";
        load();
      });
    });
    load();
    setInterval(load, 60000);  // 60s — throttle to avoid flip; chart/metrics from file, only equity/positions refresh
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store, max-age=0"})

@app.get("/")
async def root():
    return {
        "name": "Vantage2 API",
        "endpoints": {
            "/arthurvega/fundingOI": "Open Interest & Funding Rate data",
            "/portfolio": "Hyperliquid portfolio summary (JSON)",
            "/portfolio-settings": "Dashboard settings snapshots (JSON)",
            "/portfolio-dashboard": "Portfolio dashboard (HTML)"
        },
        "description": "Modular API for trading data"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
