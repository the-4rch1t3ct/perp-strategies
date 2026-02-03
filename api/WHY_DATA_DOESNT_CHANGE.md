# Why Data Doesn't Change When You Refresh

## The Core Issue

**You're using 5-minute candles**, which means data only updates every 5 minutes when a new candle closes.

### Example:

```
10:00:00 - New 5m candle opens (price: $0.12737)
10:01:00 - You refresh → Still $0.12737 (same candle)
10:02:00 - You refresh → Still $0.12737 (same candle)  
10:03:00 - You refresh → Still $0.12737 (same candle)
10:04:00 - You refresh → Still $0.12737 (same candle)
10:05:00 - New 5m candle closes → Price might be $0.12750
10:05:01 - You refresh → NOW shows $0.12750 (new candle!)
```

## Understanding the Two Different "Refresh" Concepts

### 1. **Cache Refresh** (5 seconds)
- How long to cache fetched data in memory
- This is working correctly
- Even if you bypass cache, you'll still see the same price until a new candle closes

### 2. **Candle Update** (5 minutes)
- How often new OHLCV candles are created
- This is the real limitation
- Prices only change when a new 5-minute candle closes

## Solutions

### Option 1: Use `?refresh=true` Parameter

This forces a fresh fetch (bypasses cache), but you'll still see the same price until a new candle closes:

```bash
curl "https://api.wagmi-global.eu/indicators?refresh=true"
```

### Option 2: Check `data_age_seconds` Field

The API now includes `data_age_seconds` showing how old the latest candle is:

```json
{
  "symbol": "DOGE/USDT:USDT",
  "price": 0.12737,
  "timestamp": "2026-01-26T23:25:00",
  "data_age_seconds": 120.5  // Candle is 2 minutes old
}
```

- If `data_age_seconds < 300` (5 minutes), you're seeing the current active candle
- The price won't change until `data_age_seconds` resets (new candle closes)

### Option 3: Switch to 1-Minute Timeframe

For more frequent updates, modify the API to use 1-minute candles:

**In `live_indicators_api_optimized.py`, line 354:**
```python
# Change from:
df = await fetch_ohlcv_wagmi(symbol, timeframe='5m', limit=200, force_refresh=force_refresh)

# To:
df = await fetch_ohlcv_wagmi(symbol, timeframe='1m', limit=200, force_refresh=force_refresh)
```

**Trade-offs:**
- ✅ Updates every 1 minute (instead of 5)
- ✅ More responsive to price changes
- ⚠️ More API calls
- ⚠️ Indicators may be less stable (more noise)

### Option 4: Add Real-Time Price Endpoint

For truly live prices (updates every second), you'd need a separate endpoint that fetches tick data, not OHLCV candles.

## Current Behavior Summary

| Aspect | Value | Meaning |
|--------|-------|---------|
| **Cache TTL** | 5 seconds | How long to cache fetched data |
| **Candle Timeframe** | 5 minutes | How often new candles are created |
| **Price Updates** | Every 5 minutes | When new candle closes |

## Testing

To see when data actually updates:

```bash
# Check current candle age
curl -s "https://api.wagmi-global.eu/indicators" | \
  jq '.data[0].data_age_seconds'

# Wait for next 5-minute mark (e.g., 10:05:00, 10:10:00, etc.)
# Then check again - you should see a new price
```

## Recommendation

For your trading agent:

1. **Keep 5m candles** for indicators (more stable signals)
2. **Accept that prices update every 5 minutes** (this is normal for OHLCV data)
3. **Use `?refresh=true`** to ensure you have the latest candle data
4. **Monitor `data_age_seconds`** to know how fresh the data is

---

**The data IS refreshing correctly - it's just that 5-minute candles only update every 5 minutes!**

If you need more frequent updates, consider switching to 1-minute candles or adding a separate real-time price endpoint.
