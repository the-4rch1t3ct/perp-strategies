"""
Live portfolio fetch for Hyperliquid (positions + equity).
Used by vantagev2_api for open position counts, equity, and closed trades.
Hyperliquid: public POST info endpoint (no auth; requires HL_ACCOUNT_ADDRESS).
"""
import os
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

# Hyperliquid (read-only; no private key needed)
HL_INFO_URL = os.getenv("HL_BASE_URL", "https://api.hyperliquid.xyz").strip().rstrip("/") + "/info"
HL_ACCOUNT_ADDRESS = os.getenv("HL_ACCOUNT_ADDRESS")
HL_DEX = os.getenv("HL_DEX", "")

# Timeouts and retries for resilience (HL can return 429 under load)
HL_REQUEST_TIMEOUT = 10
HL_RATE_LIMIT_CODES = (429, 500, 502, 503)


def _hl_post(payload: Dict[str, Any], timeout: int = HL_REQUEST_TIMEOUT) -> Optional[Any]:
    """POST to HL info endpoint. Returns parsed JSON or None on error/429/5xx/timeout. Never raises."""
    try:
        r = requests.post(HL_INFO_URL, json=payload, timeout=timeout)
        if r.status_code in HL_RATE_LIMIT_CODES:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _hl_get_mark_prices() -> Dict[str, float]:
    """Fetch current mark prices from Hyperliquid metaAndAssetCtxs.
    Response is a list: [meta, asset_ctxs] where meta has universe and asset_ctxs has markPx.
    Returns {} on 429/5xx/timeout so dashboard keeps working with cached data.
    """
    marks = {}
    try:
        data = _hl_post({"type": "metaAndAssetCtxs"}, timeout=5)
        if data is None:
            return marks
        if isinstance(data, list) and len(data) >= 2:
            # Response structure: [meta, asset_ctxs]
            meta = data[0] if isinstance(data[0], dict) else {}
            asset_ctxs = data[1] if isinstance(data[1], list) else []
            universe = meta.get("universe") or []
            # Build mapping from asset index to mark price
            for i, ctx in enumerate(asset_ctxs):
                if isinstance(ctx, dict):
                    mark_str = ctx.get("markPx") or ctx.get("midPx")
                    if mark_str:
                        try:
                            mark_price = float(mark_str)
                            # Get coin name from universe
                            if i < len(universe) and isinstance(universe[i], dict):
                                coin = universe[i].get("name", "")
                                if coin:
                                    marks[coin] = mark_price
                        except (TypeError, ValueError):
                            pass
    except Exception as e:
        print(f"⚠️  Mark price fetch failed: {e}", flush=True)
    return marks


def _hl_normalize_positions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize Hyperliquid clearinghouseState to dashboard open_positions format. Calculates PnL from mark prices if missing."""
    out = []
    positions = state.get("assetPositions", []) or []
    # Fetch mark prices once for all positions
    mark_prices = _hl_get_mark_prices()
    for p in positions:
        item = (p.get("position") or p) if isinstance(p, dict) else {}
        if not isinstance(item, dict):
            continue
        try:
            szi = float(item.get("szi", 0) or 0)
        except (TypeError, ValueError):
            szi = 0
        if szi == 0:
            continue
        try:
            entry = float(item.get("entryPx", 0) or 0)
        except (TypeError, ValueError):
            entry = 0
        lev_val = item.get("leverage")
        leverage = 1
        if isinstance(lev_val, dict):
            try:
                leverage = float(lev_val.get("value", 1) or 1)
            except (TypeError, ValueError):
                pass
        elif isinstance(lev_val, (int, float)):
            leverage = float(lev_val)
        side = "LONG" if szi > 0 else "SHORT"
        coin = item.get("coin", "")
        qty = abs(szi)
        # Use Hyperliquid's returnOnEquity (ROE = PnL / margin) to match their UI; fallback to unrealizedPnl/marginUsed
        pnl_pct = None
        pnl_usd = None
        roe = item.get("returnOnEquity")
        if roe is not None and str(roe).strip() != "":
            try:
                pnl_pct = round(float(roe) * 100, 2)  # HL returns decimal e.g. 0.043 = 4.3%
            except (TypeError, ValueError):
                pass
        if pnl_pct is None:
            try:
                upnl = float(item.get("unrealizedPnl", 0) or 0)
                margin_used = float(item.get("marginUsed", 0) or 0)
                if margin_used and margin_used > 0:
                    pnl_pct = round((upnl / margin_used) * 100, 2)  # ROE = PnL / margin
                    pnl_usd = round(upnl, 2)
            except (TypeError, ValueError):
                pass
        # Fallback: calculate PnL from mark price if missing
        if pnl_usd is None and entry > 0 and qty > 0:
            mark_price = mark_prices.get(coin)
            if mark_price and mark_price > 0:
                if side == "LONG":
                    pnl_usd = round((mark_price - entry) * qty, 2)
                else:  # SHORT
                    pnl_usd = round((entry - mark_price) * qty, 2)
                # Calculate PnL% from margin
                notional = entry * qty
                margin = notional / leverage if leverage > 0 else notional
                if margin > 0:
                    pnl_pct = round((pnl_usd / margin) * 100, 2)
        try:
            pos_val = float(item.get("positionValue", 0) or 0)
            position_size_usd = round(pos_val, 2) if pos_val else round(abs(szi) * entry, 2)
        except (TypeError, ValueError):
            position_size_usd = round(abs(szi) * entry, 2) if entry else None
        opened_at = None
        try:
            pt = item.get("time")
            if pt is not None:
                ms = int(pt)
                opened_at = datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except (TypeError, ValueError):
            pass
        # Use symbol with USDT suffix for dashboard (matches trading pairs)
        symbol_display = f"{coin}USDT" if (isinstance(coin, str) and coin) else ""
        out.append({
            "symbol": symbol_display or coin,
            "side": side,
            "entry_price": entry,
            "entry_qty": qty,
            "leverage": leverage,
            "tp_price": None,
            "sl_price": None,
            "opened_at": opened_at,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_usd,
            "position_size_usd": position_size_usd,
        })
    return out


def _hl_equity_from_spot_state(spot_state: Dict[str, Any]) -> Optional[float]:
    """Extract total USDC balance from spotClearinghouseState (matches Hyperliquid UI 'Total Balance')."""
    balances = spot_state.get("balances", [])
    if not isinstance(balances, list):
        return None
    for bal in balances:
        if not isinstance(bal, dict):
            continue
        coin = bal.get("coin", "")
        if coin == "USDC":
            try:
                total = float(bal.get("total", 0) or 0)
                return round(total, 2) if total > 0 else None
            except (TypeError, ValueError):
                return None
    return None


def _hl_equity_from_state(state: Dict[str, Any]) -> Optional[float]:
    ms = state.get("marginSummary")
    if not isinstance(ms, dict):
        ms = state.get("crossMarginSummary") if isinstance(state.get("crossMarginSummary"), dict) else {}
    if not ms:
        return None
    try:
        return round(float(ms.get("accountValue", 0) or 0), 2)
    except (TypeError, ValueError):
        return None


def _hl_user_fills() -> List[Dict[str, Any]]:
    """Fetch user fills from Hyperliquid (up to 2000 most recent). No auth.
    aggregateByTime: true so partial fills for the same order are combined; closedPnl then
    matches the exchange UI (one logical trade = one row with total PnL).
    Returns [] on 429/5xx/timeout."""
    if not HL_ACCOUNT_ADDRESS or not HL_ACCOUNT_ADDRESS.strip():
        return []
    user = HL_ACCOUNT_ADDRESS.strip().lower()
    payload = {"type": "userFills", "user": user, "aggregateByTime": True}
    if HL_DEX:
        payload["dex"] = HL_DEX
    data = _hl_post(payload, timeout=HL_REQUEST_TIMEOUT)
    return data if isinstance(data, list) else []


def _hl_is_close_fill(f: Dict[str, Any]) -> bool:
    """True if fill is a close (Close Long / Close Short), not an open."""
    dir_str = (f.get("dir") or "").strip() if isinstance(f.get("dir"), str) else ""
    return dir_str.startswith("Close ") or dir_str in ("Close Long", "Close Short")


def _hl_net_pnl_from_fill(f: Dict[str, Any]) -> Optional[float]:
    """HL fill: closedPnl is gross; UI shows net (closedPnl - fee). Return net or None if no closedPnl."""
    try:
        closed = f.get("closedPnl")
        if closed is None:
            return None
        pnl = float(closed)
        fee = float(f.get("fee") or 0)
        return pnl - fee
    except (TypeError, ValueError):
        return None


def _hl_win_rate_from_fills(fills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute total_trades, won, lost, win_rate_pct from user fills (close fills only, net PnL = closedPnl - fee)."""
    total = won = lost = 0
    for f in fills:
        if not isinstance(f, dict):
            continue
        if not _hl_is_close_fill(f):
            continue
        pnl = _hl_net_pnl_from_fill(f)
        if pnl is None or pnl == 0:
            continue
        total += 1
        if pnl > 0:
            won += 1
        else:
            lost += 1
    win_rate = round((won / total) * 100, 2) if total > 0 else 0.0
    return {
        "total_trades": total,
        "won": won,
        "lost": lost,
        "win_rate_pct": win_rate,
    }


# Default leverage for closed-trade PnL% when exchange fill doesn't provide it (ROE = PnL/margin).
DEFAULT_LEVERAGE_FOR_CLOSED_TRADES = 5


def _hl_last_10_trades_from_fills(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build dashboard last_10_trades from close fills only. PnL% = ROE (on margin) so it reflects leverage."""
    closed = []
    for f in fills:
        if not isinstance(f, dict):
            continue
        if not _hl_is_close_fill(f):
            continue
        pnl = _hl_net_pnl_from_fill(f)
        if pnl is None or pnl == 0:
            continue
        ts_ms = f.get("time")
        if ts_ms is None:
            continue
        try:
            t = int(ts_ms)
        except (TypeError, ValueError):
            continue
        coin = f.get("coin", "")
        if isinstance(coin, str) and coin.startswith("@"):
            continue
        pnl_pct = None
        notional_usd = None
        volume_usd = None  # open + close notional per position
        leverage = DEFAULT_LEVERAGE_FOR_CLOSED_TRADES
        try:
            px = float(f.get("px") or 0)
            sz = float(f.get("sz") or 0)
            if px > 0 and sz > 0:
                close_notional = px * sz
                notional_usd = round(close_notional, 2)
                # ROE = PnL / margin (margin = notional/leverage); HL fills don't include leverage, use default
                margin = notional_usd / leverage if leverage else notional_usd
                if margin > 0:
                    pnl_pct = round((pnl / margin) * 100, 2)
                # Open notional: Close Long => entry*qty = exit*qty - pnl; Close Short => entry*qty = exit*qty + pnl
                dir_str = (f.get("dir") or "").strip()
                dir_lower = dir_str.lower()
                if "long" in dir_lower or dir_str == "L":
                    open_notional = close_notional - pnl
                else:
                    open_notional = close_notional + pnl
                open_notional = max(0.0, open_notional)
                volume_usd = round(open_notional + close_notional, 2)
        except (TypeError, ValueError):
            pass
        dir_str = (f.get("dir") or "").strip()
        dir_lower = dir_str.lower()
        side = "LONG" if "long" in dir_lower or dir_str == "L" else "SHORT" if "short" in dir_lower or dir_str == "S" else None
        closed.append({
            "symbol": coin,
            "pnl_usd": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "notional_usd": notional_usd,
            "volume_usd": volume_usd,
            "leverage": leverage,
            "side": side,
            "exit_type": "TAKE_PROFIT" if pnl > 0 else "STOP_LOSS",
            "time": f"{t}",
        })
    # Sort by time descending (most recent first), take 10
    closed.sort(key=lambda x: int(x["time"]), reverse=True)
    out = closed[:10]
    # Normalize time to ISO for dashboard
    for t in out:
        try:
            ms = int(t["time"])
            t["time"] = datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except Exception:
            pass
    return out


def _hl_all_trades_from_fills(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build full trade history from close fills only for chart. PnL% = ROE (on margin) so it reflects leverage."""
    closed = []
    for f in fills:
        if not isinstance(f, dict):
            continue
        if not _hl_is_close_fill(f):
            continue
        pnl = _hl_net_pnl_from_fill(f)
        if pnl is None or pnl == 0:
            continue
        ts_ms = f.get("time")
        if ts_ms is None:
            continue
        try:
            t = int(ts_ms)
        except (TypeError, ValueError):
            continue
        coin = f.get("coin", "")
        if isinstance(coin, str) and coin.startswith("@"):
            continue
        pnl_pct = None
        notional_usd = None
        volume_usd = None
        leverage = DEFAULT_LEVERAGE_FOR_CLOSED_TRADES
        try:
            px = float(f.get("px") or 0)
            sz = float(f.get("sz") or 0)
            if px > 0 and sz > 0:
                close_notional = px * sz
                notional_usd = round(close_notional, 2)
                margin = notional_usd / leverage if leverage else notional_usd
                if margin > 0:
                    pnl_pct = round((pnl / margin) * 100, 2)
                dir_str = (f.get("dir") or "").strip()
                dir_lower = dir_str.lower()
                if "long" in dir_lower or dir_str == "L":
                    open_notional = close_notional - pnl
                else:
                    open_notional = close_notional + pnl
                open_notional = max(0.0, open_notional)
                volume_usd = round(open_notional + close_notional, 2)
        except (TypeError, ValueError):
            pass
        dir_str = (f.get("dir") or "").strip()
        dir_lower = dir_str.lower()
        side = "LONG" if "long" in dir_lower or dir_str == "L" else "SHORT" if "short" in dir_lower or dir_str == "S" else None
        closed.append({
            "symbol": coin,
            "pnl_usd": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "notional_usd": notional_usd,
            "volume_usd": volume_usd,
            "leverage": leverage,
            "side": side,
            "exit_type": "TAKE_PROFIT" if pnl > 0 else "STOP_LOSS",
            "time": f"{t}",
        })
    closed.sort(key=lambda x: int(x["time"]), reverse=True)
    for t in closed:
        try:
            ms = int(t["time"])
            t["time"] = datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except Exception:
            pass
    return closed


def fetch_live_hyperliquid() -> Optional[Dict[str, Any]]:
    """
    Fetch live Hyperliquid: clearinghouse state (equity + positions) and user fills (win rate).
    No auth. Returns: equity, open_positions, and when fills available: total_trades, won, lost, win_rate_pct.
    Uses spot balance (spotClearinghouseState) for equity to match Hyperliquid UI 'Total Balance'.
    """
    if not HL_ACCOUNT_ADDRESS or not HL_ACCOUNT_ADDRESS.strip():
        return None
    user = HL_ACCOUNT_ADDRESS.strip().lower()
    
    # Fetch spot balance first (matches UI "Total Balance")
    equity = None
    spot_payload = {"type": "spotClearinghouseState", "user": user}
    if HL_DEX:
        spot_payload["dex"] = HL_DEX
    spot_state = _hl_post(spot_payload, timeout=HL_REQUEST_TIMEOUT)
    if isinstance(spot_state, dict):
        equity = _hl_equity_from_spot_state(spot_state)

    # Fetch perpetuals state for positions
    payload = {"type": "clearinghouseState", "user": user}
    if HL_DEX:
        payload["dex"] = HL_DEX
    state = _hl_post(payload, timeout=HL_REQUEST_TIMEOUT)
    try:
        if not isinstance(state, dict):
            return None
        # Use spot equity if available, otherwise fall back to perpetuals accountValue
        if equity is None:
            equity = _hl_equity_from_state(state)
        positions = _hl_normalize_positions(state)
        out = {
            "equity": equity,
            "open_positions": positions,
            "open_positions_count": len(positions),
        }
        # Live win rate + last 10 trades + full history from exchange fills
        fills = _hl_user_fills()
        if fills:
            stats = _hl_win_rate_from_fills(fills)
            out["total_trades"] = stats["total_trades"]
            out["won"] = stats["won"]
            out["lost"] = stats["lost"]
            out["win_rate_pct"] = stats["win_rate_pct"]
            last_10 = _hl_last_10_trades_from_fills(fills)
            out["last_10_trades"] = last_10
            out["last_10_pnl_usd"] = round(sum(t.get("pnl_usd", 0) for t in last_10), 2)
            all_trades = _hl_all_trades_from_fills(fills)
            out["all_trades"] = all_trades
        return out
    except Exception:
        return None
