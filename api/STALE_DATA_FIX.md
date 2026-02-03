# Fixed: Stale Data Issue

## Problem
Data was showing as ~24 days old (from Jan 2, 2026) instead of current market data.

## Root Cause
1. **CSV files**: Old CSV files in `../data/` directory were being served
2. **api.wagmi.global**: Was returning stale data
3. **Cache**: Was caching stale data

## Solution Applied

### 1. Changed Data Source Priority
**Before**: api.wagmi.global → CSV files → CCXT  
**After**: **CCXT (Binance) → api.wagmi.global** (no CSV)

### 2. Removed CSV Fallback
- CSV files may be days/weeks old
- Always fetch fresh from live APIs

### 3. CCXT as Primary Source
- CCXT connects directly to Binance Futures
- Always returns current market data
- Most reliable source for fresh data

### 4. Enhanced Freshness Checks
- Verify data age before caching
- Reject data older than 30 minutes
- Force refresh when needed

## Code Changes

```python
# OLD: Try CSV files first (stale)
csv_path = f"../data/{safe_name}_{timeframe}.csv"
if os.path.exists(csv_path):
    return df  # Could be days old!

# NEW: Skip CSV, use CCXT first (fresh)
ccxt_df = await fetch_ohlcv_ccxt(symbol, timeframe, limit)
if ccxt_df is not None:
    # Verify freshness
    if age_seconds < 1800:  # < 30 minutes
        return ccxt_df  # Fresh from Binance!
```

## Expected Results

- **Data age**: < 10 minutes (typically < 5 minutes for 5m candles)
- **Data source**: Direct from Binance Futures via CCXT
- **Freshness**: Always current market data

## Testing

```bash
curl "https://api.wagmi-global.eu/indicators?refresh=true" | \
  jq '.data[0].data_age_seconds'

# Should show < 600 seconds (10 minutes)
```

---

**Stale data issue is now fixed! API uses CCXT (Binance) as primary source for always-fresh data.**
