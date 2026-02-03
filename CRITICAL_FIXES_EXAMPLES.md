# Critical Fixes - Example Scenarios

## Example 1: XRP Signal with RR 0.3

**Signal Data:**
```json
{
  "signal": {"dir": "LONG", "entry": 1.91, "sl": 1.88, "tp": 1.95, "conf": 1.0, "rr": 0.3},
  "clusters": {"best": {"price": 1.95, "side": "short", "str": 1.0, "dist": 0.2}}
}
```

**Agent Self-Audit:**
1. ✅ "Is 0.3 < 0.5?" → YES → **ACCEPT** (this is a sniper entry)
2. ✅ "Is conf >= 0.6?" → YES (1.0)
3. ✅ "Is dist < 2%?" → YES (0.2%)
4. ✅ **EXECUTE TRADE**

**Action:** Enter LONG at 1.91, SL at 1.88, TP at 1.95 (RR 0.3 = excellent entry)

---

## Example 2: ETH Signal with Bearish Bias (Bias Mismatch)

**Signal Data:**
```json
{
  "signal": {"dir": "LONG", "entry": 3019.46, "sl": 2959.07, "tp": 3043.59, "conf": 1.0, "rr": 0.4},
  "sentiment": {"bias": "BEARISH", "lsr": 0.54, "oi": 6894.0},
  "clusters": {"best": {"price": 3028.45, "side": "short", "str": 1.0, "dist": 0.3}}
}
```

**Agent Self-Audit:**
1. ✅ "Is 0.4 < 0.5?" → YES → **ACCEPT**
2. ✅ "Is there a Bias Mismatch?" → YES (signal LONG, bias BEARISH)
3. ✅ "Extract `clusters.best.price`" → 3028.45 (data EXISTS in response)
4. ✅ **SCALP ONLY protocol activated**

**Action:**
- Enter LONG at 3019.46
- SL at 2959.07 (or adjust if near support)
- **TP = 3028.45** (from `clusters.best.price`, NOT 3043.59)
- Exit **100%** at cluster price (no partial exits)
- Mark as SCALP trade

**❌ WRONG:** "No TP cluster price provided" → REJECT
**✅ CORRECT:** Extract `clusters.best.price` = 3028.45 → Set as TP → Execute

---

## Example 3: BNB Signal with Confluence

**Signal Data:**
```json
{
  "signal": {"dir": "LONG", "entry": 904.58, "sl": 886.49, "tp": 910.82, "conf": 1.0, "rr": 0.34},
  "levels": {"support": [887.50, 884.00]},
  "clusters": {"best": {"price": 906.29, "side": "short", "str": 1.0, "dist": 0.19}}
}
```

**Agent Self-Audit:**
1. ✅ "Is 0.34 < 0.5?" → YES → **ACCEPT**
2. ✅ "Is SL near support?" → Check: SL 886.49, Support[0] 887.50
   - Distance: |886.49 - 887.50| / 887.50 = 0.11% (within 0.5%)
   - ✅ **ADJUST SL** to 0.1% below support = 887.50 * 0.999 = 886.63

**Action:**
- Enter LONG at 904.58
- **SL = 886.63** (adjusted to 0.1% below support, not original 886.49)
- TP at 910.82 (or cluster price if bias mismatch)

---

## Example 4: Batch Scan with Incomplete Data

**Batch Response:**
```json
{
  "results": {
    "ETHUSDT": {"signal": {"dir": "LONG", ...}, "clusters": {"best": {...}}},
    "SOLUSDT": {"signal": {"dir": "NEUTRAL"}},
    "TRXUSDT": {"signal": {"dir": "LONG", ...}}  // Missing clusters field
  }
}
```

**Agent Self-Audit:**
1. ✅ "Is data complete for all symbols?" → NO (TRX missing clusters)
2. ✅ **Process available symbols independently**
3. ✅ ETH: Process if meets criteria
4. ✅ SOL: Skip (NEUTRAL)
5. ✅ TRX: Process if signal valid (even without clusters)

**Action:**
- **DO NOT stop entire batch scan**
- Process ETH, SOL, TRX independently
- Missing clusters for TRX ≠ failure for ETH

---

## Summary: How Agent Will Handle Examples

### XRP Signal (RR 0.3):
- ✅ **ACCEPT** (0.3 < 0.5 = sniper entry)
- Execute LONG trade
- Use provided SL/TP

### ETH Signal (Bearish Bias):
- ✅ **ACCEPT** (RR 0.4 < 0.5)
- ✅ **Bias Mismatch detected** → SCALP ONLY
- ✅ **Extract `clusters.best.price`** = 3028.45
- ✅ **Set TP = 3028.45** (ignore original TP 3043.59)
- ✅ Exit 100% at cluster price

**Key Fixes Applied:**
1. ✅ RR 0.3 < 0.5 = ACCEPT (not reject)
2. ✅ Extract `clusters.best.price` for bias mismatch TP
3. ✅ Adjust SL to 0.1% below support if within 0.5%
4. ✅ Process all symbols independently
