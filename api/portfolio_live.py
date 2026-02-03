"""
Live portfolio fetch for Aster and Hyperliquid (positions + equity).
Used by vantagev2_api to show correct open position counts and equity.
- Aster: EIP-712 signed GET /fapi/v3/account (requires ASTER_API_KEY, ASTER_API_SECRET, etc.)
- Hyperliquid: public POST info endpoint (no auth; requires HL_ACCOUNT_ADDRESS).
"""
import os
import time
import math
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

# Aster EIP-712 (same as clawd/trader.py)
ASTER_BASE = os.getenv("ASTER_BASE_URL", "https://fapi.asterdex.com").strip()
ASTER_API_KEY = os.getenv("ASTER_API_KEY")
ASTER_API_SECRET = os.getenv("ASTER_API_SECRET")
ASTER_USER_ADDRESS = os.getenv("ASTER_USER_ADDRESS", "0x587Fa034fb673974E00DCF7F4078a498f9799D54")
ASTER_API_SIGNER = os.getenv("ASTER_API_SIGNER", "0xf25645a642207EadE9203F9E96aa31C08Ba963e9")

# Hyperliquid (read-only; no private key needed)
HL_INFO_URL = os.getenv("HL_BASE_URL", "https://api.hyperliquid.xyz").strip().rstrip("/") + "/info"
HL_ACCOUNT_ADDRESS = os.getenv("HL_ACCOUNT_ADDRESS")
HL_DEX = os.getenv("HL_DEX", "")

EIP712_DOMAIN = {
    "name": "AsterSignTransaction",
    "version": "1",
    "chainId": 1666,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}


def _aster_eip712_sign(params: Dict[str, str]) -> Optional[tuple]:
    """Sign params with EIP-712. Returns (signature_hex_no_0x, query_string) or None."""
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError:
        return None
    api_secret = (ASTER_API_SECRET or "").strip()
    if api_secret.startswith("0x"):
        api_secret = api_secret[2:]
    if not api_secret:
        return None
    try:
        account = Account.from_key(api_secret)
    except Exception:
        return None
    sorted_items = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_items])
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Message": [{"name": "msg", "type": "string"}],
        },
        "primaryType": "Message",
        "domain": EIP712_DOMAIN,
        "message": {"msg": query_string},
    }
    encoded = encode_typed_data(full_message=typed_data)
    signed = account.sign_message(encoded)
    sig_hex = signed.signature.hex()
    if sig_hex.startswith("0x"):
        sig_hex = sig_hex[2:]
    return sig_hex, query_string


def _aster_equity_from_account(account: Dict[str, Any]) -> Optional[float]:
    try:
        available = float(account.get("availableBalance", 0) or 0)
        pos_margin = float(account.get("totalPositionInitialMargin", 0) or 0)
        order_margin = float(account.get("totalOpenOrderInitialMargin", 0) or 0)
        wallet = float(account.get("totalWalletBalance", 0) or 0)
        total = available + pos_margin + order_margin
        if wallet > total:
            total = wallet
        if total <= 0:
            total = available
        return round(total, 2)
    except (TypeError, ValueError):
        return None


def _aster_positions_to_dashboard(account: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Aster /fapi/v3/account positions to dashboard open_positions format (may lack PnL if account omits it)."""
    out = []
    for p in account.get("positions", []) or []:
        try:
            amt = float(p.get("positionAmt", 0) or 0)
        except (TypeError, ValueError):
            amt = 0
        if amt == 0:
            continue
        try:
            entry = float(p.get("entryPrice", 0) or 0)
        except (TypeError, ValueError):
            entry = 0
        leverage = 1
        try:
            lev_val = p.get("leverage") or p.get("leveragePercent")
            if lev_val is not None:
                leverage = int(lev_val) if isinstance(lev_val, (int, float)) else 1
        except (TypeError, ValueError):
            pass
        side = "LONG" if amt > 0 else "SHORT"
        try:
            upnl = float(p.get("unrealizedProfit", 0) or p.get("unRealizedProfit", 0) or p.get("up", 0) or 0)
        except (TypeError, ValueError):
            upnl = 0
        pnl_pct = None
        notional = abs(amt) * entry if entry else 0
        if notional:
            pnl_pct = round((upnl / notional) * 100, 2)
        position_size_usd = round(notional, 2) if notional else None
        pnl_usd = round(upnl, 2) if upnl is not None else None
        opened_at = None
        try:
            ut = p.get("updateTime") or p.get("update_time")
            if ut is not None:
                ms = int(ut)
                opened_at = datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except (TypeError, ValueError):
            pass
        out.append({
            "symbol": p.get("symbol", ""),
            "side": side,
            "entry_price": entry,
            "entry_qty": abs(amt),
            "leverage": leverage,
            "tp_price": None,
            "sl_price": None,
            "opened_at": opened_at,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_usd,
            "position_size_usd": position_size_usd,
        })
    return out


def _aster_positions_from_risk(position_risk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Aster /fapi/v2/positionRisk array to dashboard open_positions format (includes unRealizedProfit)."""
    out = []
    for p in position_risk or []:
        try:
            amt = float(p.get("positionAmt", 0) or 0)
        except (TypeError, ValueError):
            amt = 0
        if amt == 0:
            continue
        try:
            entry = float(p.get("entryPrice", 0) or 0)
        except (TypeError, ValueError):
            entry = 0
        leverage = 1
        try:
            lev_val = p.get("leverage")
            if lev_val is not None:
                leverage = int(float(lev_val)) if lev_val else 1
        except (TypeError, ValueError):
            pass
        side = "LONG" if amt > 0 else "SHORT"
        try:
            upnl = float(p.get("unRealizedProfit", 0) or p.get("unrealizedProfit", 0) or p.get("up", 0) or 0)
        except (TypeError, ValueError):
            upnl = 0
        notional = abs(amt) * entry if entry else 0
        pnl_pct = round((upnl / notional) * 100, 2) if notional else None
        position_size_usd = round(notional, 2) if notional else None
        pnl_usd = round(upnl, 2)
        opened_at = None
        try:
            ut = p.get("updateTime") or p.get("update_time")
            if ut is not None:
                ms = int(ut)
                opened_at = datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except (TypeError, ValueError):
            pass
        out.append({
            "symbol": p.get("symbol", ""),
            "side": side,
            "entry_price": entry,
            "entry_qty": abs(amt),
            "leverage": leverage,
            "tp_price": None,
            "sl_price": None,
            "opened_at": opened_at,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_usd,
            "position_size_usd": position_size_usd,
        })
    return out


def _aster_signed_get(path: str) -> Optional[Any]:
    """Perform EIP-712 signed GET request to Aster. Returns JSON response or None."""
    sig_result = _aster_eip712_sign(
        {
            "nonce": str(math.trunc(time.time() * 1_000_000)),
            "recvWindow": "5000",
            "signer": ASTER_API_SIGNER,
            "timestamp": str(int(time.time() * 1000)),
            "user": ASTER_USER_ADDRESS,
        }
    )
    if not sig_result:
        return None
    sig_hex, query_string = sig_result
    url = f"{ASTER_BASE}{path}?{query_string}&signature={sig_hex}"
    headers = {"X-ASTER-APIKEY": ASTER_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_live_aster() -> Optional[Dict[str, Any]]:
    """
    Fetch live Aster account (equity + positions). Uses position risk for live PnL when available.
    Returns: {"equity": float, "open_positions": list, "open_positions_count": int}
    """
    if not ASTER_API_KEY or not ASTER_API_SECRET:
        return None
    # Get account for equity and fallback positions
    data = _aster_signed_get("/fapi/v3/account")
    if not isinstance(data, dict):
        return None
    equity = _aster_equity_from_account(data)
    positions = _aster_positions_to_dashboard(data)
    # Prefer position risk for live PnL (unRealizedProfit); fallback to account positions
    risk_data = _aster_signed_get("/fapi/v2/positionRisk")
    if isinstance(risk_data, list) and len(risk_data) > 0:
        positions_from_risk = _aster_positions_from_risk(risk_data)
        if positions_from_risk:
            positions = positions_from_risk
    return {
        "equity": equity,
        "open_positions": positions,
        "open_positions_count": len(positions),
    }


def _hl_get_mark_prices() -> Dict[str, float]:
    """Fetch current mark prices from Hyperliquid metaAndAssetCtxs.
    Response is a list: [meta, asset_ctxs] where meta has universe and asset_ctxs has markPx.
    """
    marks = {}
    try:
        r = requests.post(HL_INFO_URL, json={"type": "metaAndAssetCtxs"}, timeout=5)
        r.raise_for_status()
        data = r.json()
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
        out.append({
            "symbol": coin,
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
    matches the exchange UI (one logical trade = one row with total PnL)."""
    if not HL_ACCOUNT_ADDRESS or not HL_ACCOUNT_ADDRESS.strip():
        return []
    user = HL_ACCOUNT_ADDRESS.strip().lower()
    payload = {"type": "userFills", "user": user, "aggregateByTime": True}
    if HL_DEX:
        payload["dex"] = HL_DEX
    try:
        r = requests.post(HL_INFO_URL, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


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


def _hl_last_10_trades_from_fills(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build dashboard last_10_trades from close fills only (Close Long/Short). Use net PnL = closedPnl - fee to match HL UI."""
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
        # Skip spot (e.g. @107)
        if isinstance(coin, str) and coin.startswith("@"):
            continue
        pnl_pct = None
        notional_usd = None
        try:
            px = float(f.get("px") or 0)
            sz = float(f.get("sz") or 0)
            if px > 0 and sz > 0:
                notional_usd = round(px * sz, 2)
                pnl_pct = round((pnl / notional_usd) * 100, 2)
        except (TypeError, ValueError):
            pass
        dir_str = (f.get("dir") or "").strip()
        side = "LONG" if "Long" in dir_str or dir_str == "L" else "SHORT" if "Short" in dir_str or dir_str == "S" else None
        closed.append({
            "symbol": coin,
            "pnl_usd": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "notional_usd": notional_usd,
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
    """Build full trade history from close fills only (Close Long/Short) for chart. Use net PnL = closedPnl - fee to match HL UI."""
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
        try:
            px = float(f.get("px") or 0)
            sz = float(f.get("sz") or 0)
            if px > 0 and sz > 0:
                notional_usd = round(px * sz, 2)
                pnl_pct = round((pnl / notional_usd) * 100, 2)
        except (TypeError, ValueError):
            pass
        dir_str = (f.get("dir") or "").strip()
        side = "LONG" if "Long" in dir_str or dir_str == "L" else "SHORT" if "Short" in dir_str or dir_str == "S" else None
        closed.append({
            "symbol": coin,
            "pnl_usd": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "notional_usd": notional_usd,
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
    """
    if not HL_ACCOUNT_ADDRESS or not HL_ACCOUNT_ADDRESS.strip():
        return None
    user = HL_ACCOUNT_ADDRESS.strip().lower()
    payload = {"type": "clearinghouseState", "user": user}
    if HL_DEX:
        payload["dex"] = HL_DEX
    try:
        r = requests.post(HL_INFO_URL, json=payload, timeout=10)
        r.raise_for_status()
        state = r.json()
        if not isinstance(state, dict):
            return None
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
