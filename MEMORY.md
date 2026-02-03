# Cursor / Project Memory — Current Status

**Last updated:** 2025-01-29 (signal metrics doc, TP validation, ranking framework)

---

## Project: memecoin-perp-strategies

Trading strategy and API around **predictive liquidation clusters** (Wagmi). Agent uses UNTRUSTED batch API only for signals; CTX for balance/fees/indicators. Stalker mode: runway required, no chasing exhausted moves.

---

## API (api.wagmi-global.eu)

- **Batch (primary for agent):**  
  `GET https://api.wagmi-global.eu/api/trade/batch?min_strength=0.6&max_distance=3.0`
  - Returns **all 10 symbols**: ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, TRXUSDT, DOGEUSDT, ADAUSDT, BCHUSDT, LINKUSDT, XMRUSDT.
  - **Per-symbol shape:** `price` (float, top-level, refreshed on request), `signal`, `levels`, `sentiment`, `clusters`.
  - `signal.entry` = reference price at signal build time; TP/SL are scaled to it. Data is refreshed on each request via `heatmap.refresh_prices()`.
- **Single symbol:**  
  `GET https://api.wagmi-global.eu/api/trade/{symbol}?min_strength=0.6&max_distance=3.0`  
  Same shape plus `signal_long` / `signal_short` when both directions have valid clusters.
- **Heatmap UI:**  
  `https://api.wagmi-global.eu/liquidation-heatmap`  
  Served by same API (port 8004).
- **Batch (Hyperliquid, same shape):**  
  `GET https://api.wagmi-global.eu/api/trade/batch/hyperliquid?min_strength=0.6&max_distance=3.0`  
  Same response shape as `/api/trade/batch` but data is pulled from Hyperliquid (metaAndAssetCtxs: mark price, OI, impact prices). Same 10 symbols; sentiment uses total OI (no L/S split on HL public API).
- **Batch (Aster, same shape):**  
  `GET https://api.wagmi-global.eu/api/trade/batch/aster?min_strength=0.6&max_distance=3.0`  
  Prices from Aster DEX (fapi.asterdex.com) so entry/TP/SL match venue. **Clusters:** Binance (primary) or Hyperliquid only (no synthetic). Symbols without real cluster data are omitted. Symbols: ETH, SOL, BNB, XRP, DOGE, BCH, LINK, XMR, ASTER, HYPE, SUI, PUMP (XAG, XAU removed). Per-symbol `cluster_source`: `"binance"` | `"hyperliquid"`.

---

## Signal metrics (WAGMI_SIGNAL_METRICS.md)

- **Path:** `api/WAGMI_SIGNAL_METRICS.md` — full reference for conf, rr, entry, tp, sl, dir.
- **conf:** Cluster strength (0–1). Aster batch: real conf from Binance/HL only (no synthetic).
- **rr:** reward/risk; LONG: (tp−entry)/(entry−sl); SHORT: (entry−tp)/(sl−entry).
- **entry:** Current/mark price at signal build time; matches `results.{SYMBOL}.price`.
- **TP/SL:** LONG: sl = entry×0.98, tp = short_cluster×1.005; SHORT: sl = entry×1.02, tp = long_cluster×0.995.
- **dir:** LONG if strong short cluster above; SHORT if strong long cluster below; else NEUTRAL. LONG checked first.

---

## Validation: minimum TP distance

- **Rule:** Reject signals where TP is &lt; 0.5% from entry (poor cluster data, not a real setup).
- **Constant:** `MIN_TP_DISTANCE_PCT = 0.5` in `api/liquidation_heatmap_api.py`.
- **Logic:** In `_build_compact_signal` and `_build_signal_for_direction`, after computing tp: LONG uses `(tp−entry)/entry×100 ≥ 0.5`; SHORT uses `(entry−tp)/entry×100 ≥ 0.5`. Otherwise fall through to NEUTRAL / None.

---

## Ranking / scoring framework (planned, not implemented)

- **Goal:** Best trade opportunities first in line when opening positions (limited slots).
- **Formula (agreed):**  
  `score = w_conf*conf + w_sniper*(0.5−rr) + w_dist*dist_score(dist) + w_tp*min(tp_distance−0.5, 2.0)`  
  (tp term capped so it stays a tiebreaker.)
- **Weights:** w_conf=1.0, w_sniper=0.3, w_dist=0.2, w_tp=0.1 (tune on results).
- **dist_score:** ideal_dist=0.7%; if dist&lt;0.4% or dist&gt;1.0% then 0; else `1.0 − abs(dist−0.7)/0.7`.
- **Process:** Sort qualifying signals by score descending; process top N until max positions. Tie-break by stable key (e.g. symbol).
- **Where to implement:** API (add score/rank per symbol) or agent (compute from batch fields). Not yet coded.

---

## Agent prompt (AI_TRADING_AGENT_PROMPT.md)

- **Path:** `memecoin-perp-strategies/AI_TRADING_AGENT_PROMPT.md` (compact, &lt;5k chars).
- **Mode:** Stalker, not chaser.
- **Entry:** Runway required: `0.4% <= clusters.best.dist < 2.0%`; **never** enter if `dist < 0.2%` (exhaustion).
- **RR gate:** `signal.rr < 0.9` (relaxed from 0.5 so more symbols qualify).
- **Anti-whipsaw:** If signal flips within 3 minutes of entry, **hold** unless SL is hit.
- **Bias mismatch:** If `sentiment.bias ≠ signal.dir` and dist 0.4–1.0%, scalp only; TP = `clusters.best.price`.
- **Data hierarchy:** UNTRUSTED = only source for signals/clusters; CTX = balance, fees, indicators only.

---

## Predictive heatmap (backend)

- **Entrypoint:** `api/liquidation_heatmap_api.py` (FastAPI, port 8004).
- **Core logic:** `predictive_liquidation_heatmap.py` (PredictiveLiquidationHeatmap).
- **Update speeds (Binance-safe):**
  - Prices: every **5s** (1 req, all symbols).
  - OI + depth: every **15s**, 0.25s between symbols.
  - Level recalc: every **3s** (no external calls).
- **Batch response:** Uses `SymbolTradeData` with `price` first so `results.{SYMBOL}.price` is always present.

---

## Heatmap UI (liquidation_heatmap_ui.html)

- **Path:** `api/liquidation_heatmap_ui.html`.
- **Features:** Candles (Binance OHLC), cluster bands, **LONG and SHORT TP/SL** (from API + derived from levels when only one direction has clusters).
- **Decimal precision:** Dynamic by price (`formatPrice` / `getPriceDecimals`); e.g. DOGE 5 decimals, BTC 2.
- **Auto-refresh:** 3s when ON; label shows "Auto Refresh: ON (3s)".
- **Explainer in UI:** "Understanding TP/SL Lines vs Cluster Bands" — cluster bands = risk zones; TP/SL = strategy exit levels. LONG TP/SL when resistance (short clusters above); SHORT TP/SL when support (long clusters below). Why only one side sometimes: no resistance ⇒ no LONG TP; no support ⇒ no SHORT TP.

---

## Deployment / restart (heatmap API)

- **Process:** Runs as **nohup** on port **8004** (no systemd in repo).
- **Start (from repo root):**  
  `cd /home/botadmin/memecoin-perp-strategies && source venv/bin/activate && nohup python api/liquidation_heatmap_api.py >> /tmp/liquidation_heatmap.log 2>&1 &`
- **Restart:** Find PID (e.g. `pgrep -af liquidation_heatmap_api` or `lsof -i :8004`), `kill <PID>`, then run the Start command above. Wait ~5s then check e.g.  
  `curl -s "http://127.0.0.1:8004/api/trade/batch?min_strength=0.6&max_distance=3.0"`  
  and confirm `results.ETHUSDT.price` exists.

---

## Key file map

| Role | Path |
|------|------|
| Agent prompt | `AI_TRADING_AGENT_PROMPT.md` |
| Batch + single trade API | `api/liquidation_heatmap_api.py` |
| Heatmap backend logic | `predictive_liquidation_heatmap.py` |
| Heatmap UI | `api/liquidation_heatmap_ui.html` |
| Start script | `api/start_liquidation_heatmap.sh` |
| Deployment notes | `api/LIQUIDATION_HEATMAP_DEPLOYMENT.md` |
| Hyperliquid batch data | `api/hyperliquid_batch.py` |
| Aster batch data | `api/aster_batch.py` |
| Signal metrics reference | `api/WAGMI_SIGNAL_METRICS.md` |

---

*This file is for Cursor and humans to resume context. **Keep it updated as work progresses:** update when major decisions or structure change, when adding/removing key files or APIs, and when changing agent rules or deployment steps.*
