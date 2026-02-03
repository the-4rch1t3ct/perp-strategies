# Wagmi Trading Signal API — Metric Logic (Aster / Batch)

This document explains how the batch API (`/api/trade/batch`, `/api/trade/batch/aster`, `/api/trade/batch/hyperliquid`) computes **conf**, **rr**, **entry**, **tp**, **sl**, and **dir** so you can verify correctness or debug.

---

## 1. CONFIDENCE (`conf`)

### How it is calculated

- **Source:** `conf` is the **strength** of the **single cluster** used to build the signal (the “strongest” cluster in the chosen direction).
- **Not** a blend of pattern, volume, or sentiment. It is **cluster strength only**.

**Main API (Binance OI):**  
Strength is derived from open interest at that liquidation tier (sqrt scale so conf differentiates):

```text
strength = min(1.0, sqrt((oi_per_tier / total_oi_usd) * 3))
```

- `oi_per_tier`: OI (long or short) attributed to that leverage tier.
- 33% of OI in one tier → 1.0; 20% → 0.77; 12% → 0.6 (min_strength). Capped at 1.0.
- Helper: `_strength_from_oi_fraction()` in `predictive_liquidation_heatmap.py`. Conf rounded to 2 decimals in API.

**Hyperliquid batch:**  
- Strength from **real OI share** across HL symbols (sqrt scale):  
  `strength = min(1.0, sqrt((oi_usd / total_oi_usd_all) * 3))`  
  This mirrors the Binance tier formula but uses actual HL OI in USD.
- Fallback (if total OI unavailable):  
  `0.3 + 0.7 * sqrt(oi_usd / 5_000_000)`

**Aster batch:**  
- Clusters from Binance or Hyperliquid only (no synthetic). Conf comes from whichever source is used for that symbol.

### Interpretation

- **conf = 1.0** — Maximum strength (OI concentration at that level is high relative to total OI).
- **conf = 0.65** — Moderate strength; often used as a minimum filter (e.g. `min_strength=0.6`).
- **conf = 0.0** — Only for NEUTRAL (no valid cluster used).

---

## 2. RISK/REWARD RATIO (`rr`)

### How it is calculated

- **Definition:** `rr = reward / risk` (one decimal).
- **Risk** = absolute distance from entry to stop-loss.
- **Reward** = absolute distance from entry to take-profit.

**LONG:**

- `risk   = entry - sl`  (entry > sl)
- `reward = tp  - entry` (tp > entry)
- `rr = (tp - entry) / (entry - sl)`

**SHORT:**

- `risk   = sl - entry`  (sl > entry)
- `reward = entry - tp`  (entry > tp)
- `rr = (entry - tp) / (sl - entry)`

So: **rr = reward / risk**. It is **not** (TP−Entry)/(Entry−SL) in a different order; the code uses the above.

### If rr = 0.3

- You risk 1 unit to make 0.3 units (reward smaller than risk).
- Mathematically: reward = 0.3 × risk (e.g. 0.3:1).
- Many agents filter for **rr &lt; 0.5** to prefer “sniper” setups (small reward, tight stop).

---

## 3. ENTRY PRICE

- **Entry is always the current market price** at signal-build time (the “reference” price for that request).
- For Aster batch, that is the **mark price** (or last price) from Aster (`/fapi/v1/ticker/price` or `premiumIndex.markPrice`).
- It is **not** a separate “recommended” level; it is the price used as reference for TP/SL and rr.
- **It should match** the top-level `price` field for that symbol in the batch response: both come from the same source (e.g. `current_prices[symbol]` for Aster).

---

## 4. TP/SL LOGIC AND FORMULAS

### Direction rules

- **LONG:** TP &gt; entry, SL &lt; entry (TP above, SL below).
- **SHORT:** TP &lt; entry, SL &gt; entry (TP below, SL above).

So yes: for LONG, TP above and SL below; for SHORT, TP below and SL above.

### How TP/SL are set (code logic)

**LONG (we go long, targeting resistance = short liquidation cluster above):**

- `entry   = current_price`
- `sl      = current_price * 0.98`  (2% below entry)
- `tp      = strongest_short_cluster.price_level * 1.005`  (just above the resistance cluster)

So TP is derived from the **short** cluster’s price (slightly above it).

**SHORT (we go short, targeting support = long liquidation cluster below):**

- `entry   = current_price`
- `sl      = current_price * 1.02`  (2% above entry)
- `tp      = strongest_long_cluster.price_level * 0.995`  (just below the support cluster)

So TP is derived from the **long** cluster’s price (slightly below it).

### Summary formulas

| Direction | SL              | TP (concept)                    |
|----------|-----------------|----------------------------------|
| LONG     | entry × 0.98    | short_cluster.price × 1.005      |
| SHORT    | entry × 1.02    | long_cluster.price × 0.995       |

`conf` and `rr` do **not** change TP/SL; TP/SL are fixed by the formulas above. `rr` is then **computed** from those TP/SL and entry.

---

## 5. DIRECTION (`dir`)

### How LONG / SHORT / NEUTRAL are chosen

- **LONG:** There is at least one **short** cluster **above** current price with:
  - `strength >= min_strength` (e.g. 0.6)
  - `distance_from_price < max_distance` (e.g. 3.0%).
  - The **strongest** such short cluster is used (resistance above → we target it with a long).
- **SHORT:** Same idea for **long** clusters **below** current price (support below → we target it with a short).
- **NEUTRAL:** No cluster passes the filters in either direction, or no levels at all.

**Priority:** LONG is evaluated first; if it passes, the signal is LONG. Otherwise SHORT is evaluated. So if both qualify, the API returns LONG.

### What drives “market conditions”

- **Main/Hyperliquid:** Real liquidation clusters (OI-based levels above/below price). Direction is “where is the nearest strong cluster we can trade toward?”
- **Aster:** Synthetic levels at ±0.5% from mark. So you always have one “support” and one “resistance”; which direction is returned depends on strength/distance filters and the LONG-first priority. With the fixed 0.6 strength and 0.5% distance, both directions typically qualify; you will usually see LONG (first in code).

---

## Quick verification checklist

1. **conf** — Equals the chosen cluster’s `strength`. For Aster batch, always 0.6 when not NEUTRAL.
2. **rr** — `(reward in price units) / (risk in price units)`; LONG: (tp−entry)/(entry−sl); SHORT: (entry−tp)/(sl−entry).
3. **entry** — Same as `results[symbol].price`; current/mark price at request time.
4. **TP/SL** — LONG: SL &lt; entry &lt; TP; SHORT: TP &lt; entry &lt; SL.
5. **dir** — LONG if strong short cluster above; else SHORT if strong long cluster below; else NEUTRAL.

If any of these don’t match in your responses, there may be a bug in the pipeline (e.g. wrong price source or wrong cluster passed into `_build_compact_signal`).

---

## Validation: minimum TP distance

Signals are **rejected** (treated as NEUTRAL / no signal) when the take-profit is too close to entry, which usually indicates poor cluster data rather than a real trade setup:

- **Rule:** `|TP − entry| / entry × 100 ≥ 0.5%` (TP must be at least 0.5% away from entry).
- **LONG:** `(tp − entry) / entry × 100 ≥ 0.5`.
- **SHORT:** `(entry − tp) / entry × 100 ≥ 0.5`.

Constant in code: `MIN_TP_DISTANCE_PCT = 0.5` in `liquidation_heatmap_api.py`. If the cluster would yield a TP within 0.5% of entry, the signal is not returned (fall-through to NEUTRAL or `None` for single-direction).
