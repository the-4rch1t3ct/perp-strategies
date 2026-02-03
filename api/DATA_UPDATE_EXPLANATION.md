# Why Data Doesn't Change on Refresh

## The Issue

You're using **5-minute candles** (`timeframe='5m'`), which means:

- **New data only arrives every 5 minutes** when a new candle closes
- Refreshing the page within the same 5-minute window will show the **same data**
- Prices only update when a new 5-minute candle is created

## Example Timeline

```
10:00:00 - New 5m candle opens (price: $0.12737)
10:00:30 - You refresh → Still shows $0.12737 (same candle)
10:02:00 - You refresh → Still shows $0.12737 (same candle)
10:04:59 - You refresh → Still shows $0.12737 (same candle)
10:05:00 - New 5m candle closes → Price might be $0.12750
10:05:01 - You refresh → NOW shows $0.12750 (new candle)
```

## Solutions

### Option 1: Use `?refresh=true` Parameter (Force Fresh Fetch)

Even though the candle hasn't changed, this ensures you're getting the absolute latest data:

```bash
curl "https://api.wagmi-global.eu/indicators?refresh=true"
```

### Option 2: Check `data_age_seconds` Field

The API now includes a `data_age_seconds` field showing how old the latest candle is:

```json
{
  "symbol": "DOGE/USDT:USDT",
  "timestamp": "2026-01-26T23:25:00",
  "price": 0.12737,
  "data_age_seconds": 120.5  // Candle is 2 minutes old
}
```

- If `data_age_seconds < 300` (5 minutes), you're seeing the current active candle
- If `data_age_seconds > 300`, there might be a delay in data fetching

### Option 3: Switch to 1-Minute Timeframe (More Frequent Updates)

If you need more frequent updates, you could modify the API to use 1-minute candles:

```python
# In live_indicators_api_optimized.py, line 354
df = await fetch_ohlcv_wagmi(symbol, timeframe='1m', limit=200, force_refresh=force_refresh)
```

**Trade-offs:**
- ✅ More frequent updates (every 1 minute)
- ✅ More responsive to price changes
- ⚠️ More API calls
- ⚠️ Indicators may be less stable (more noise)

### Option 4: Use Real-Time Price (Not Candles)

For truly live prices that update every second, you'd need a WebSocket connection or a different endpoint that provides tick data, not OHLCV candles.

## Current Behavior

1. **Cache TTL**: 5 seconds (how long to cache fetched data)
2. **Candle Timeframe**: 5 minutes (how often new candles are created)
3. **Data Source**: api.wagmi.global → CCXT (Binance)

**Important**: Even if you bypass the cache, you'll still see the same price until a new 5-minute candle closes.

## Testing

To see when data actually updates:

```bash
# Check data age
curl -s "https://api.wagmi-global.eu/indicators" | jq '.data[0].data_age_seconds'

# Wait for next 5-minute mark (e.g., 10:05:00, 10:10:00, etc.)
# Then check again - you should see a new price
```

## Recommendation

For trading agents that need frequent updates:

1. **Keep 5m candles** for indicators (more stable signals)
2. **Add a separate endpoint** for real-time price (1-second updates)
3. **Use `?refresh=true`** when you need to ensure you have the latest candle data

---

**The data IS updating - it just updates every 5 minutes when new candles close, not on every page refresh!**
