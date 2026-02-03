# Data Refresh Mechanism - How It Works

## Current Implementation

### 1. **Caching System**

The API uses a **5-second TTL (Time To Live) cache** for OHLCV data:

```python
cache_ttl = 5.0  # 5 seconds
data_cache = {}  # In-memory cache: {symbol_timeframe: (dataframe, timestamp)}
```

### 2. **Data Fetch Flow**

When a request comes in, here's what happens:

```
Request → Check Cache → [Cache Hit?] → Return Cached Data
                    ↓
              [Cache Miss/Expired]
                    ↓
         Fetch from api.wagmi.global
                    ↓
         [Success?] → Cache & Return
                    ↓
              [Failed?]
                    ↓
         Fallback to CCXT (Binance)
                    ↓
         Cache & Return
```

### 3. **Cache Check Logic**

For each symbol request:

1. **Check cache first**:
   ```python
   cache_key = f"{symbol}_{timeframe}"  # e.g., "DOGE_5m"
   if cache_key in data_cache:
       cached_data, cached_time = data_cache[cache_key]
       if time.time() - cached_time < 5.0:  # Still fresh?
           return cached_data  # Return cached data immediately
   ```

2. **If cache expired or missing**:
   - Fetch fresh data from `api.wagmi.global`
   - If that fails, fallback to CCXT (Binance)
   - Store in cache with current timestamp
   - Return fresh data

### 4. **Indicator Calculation**

**Important**: Indicators are **calculated fresh on every request**, even if data is cached.

- Cached: OHLCV price/volume data (5-second TTL)
- Not cached: Indicator calculations (RSI, EMA, MACD, etc.)

This means:
- **Price data**: Refreshed every 5 seconds max
- **Indicators**: Always calculated from the latest cached data

### 5. **Current Behavior**

**Scenario 1: Rapid Requests (< 5 seconds apart)**
```
Request 1 (t=0s):  Fetch from API → Cache → Return
Request 2 (t=2s):   Use cache → Return (fast!)
Request 3 (t=4s):   Use cache → Return (fast!)
Request 4 (t=6s):   Cache expired → Fetch fresh → Cache → Return
```

**Scenario 2: All 31 Symbols Request**
- Each symbol checked independently
- Some may be cached, some may need fresh fetch
- Parallel processing (batched in groups of 10)
- Rate limiting: 10 requests/second max

## Current Settings

| Setting | Value | Description |
|---------|-------|-------------|
| Cache TTL | 5 seconds | How long cached data is valid |
| Rate Limit | 10 req/sec | Max API calls per second |
| Batch Size | 10 symbols | Process 10 at a time |
| Timeout | 5 seconds | Max wait per symbol |
| Data Source Priority | 1. api.wagmi.global<br>2. CCXT (Binance) | Fallback chain |

## Implications

### ✅ Advantages

1. **Fast responses**: Cached requests return in ~50-100ms
2. **Reduced API calls**: Only fetches when cache expires
3. **Rate limit compliant**: Respects 10 req/sec limit
4. **Fresh indicators**: Always calculated from latest data

### ⚠️ Considerations

1. **5-second delay**: Data can be up to 5 seconds old
2. **Memory usage**: Cache grows with number of symbols
3. **No background refresh**: Data only fetched on request

## Customization Options

### Change Cache TTL

To make data refresh more/less frequent:

```python
# In live_indicators_api_optimized.py, line 73
cache_ttl = 5.0  # Change to desired seconds
```

Examples:
- `cache_ttl = 1.0` → Refresh every 1 second (more API calls)
- `cache_ttl = 10.0` → Refresh every 10 seconds (fewer API calls)
- `cache_ttl = 60.0` → Refresh every minute (very few API calls)

### Add Background Refresh (Optional)

To always have fresh data ready, you could add a background task:

```python
# This would require adding to FastAPI
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_refresh())
    
async def background_refresh():
    while True:
        # Refresh all symbols every 5 seconds
        await asyncio.sleep(5.0)
        # Fetch and cache all symbols
```

## Monitoring Cache Performance

You can check cache hit rate by adding logging:

```python
cache_hits = 0
cache_misses = 0

# In fetch_ohlcv_wagmi:
if cache_key in data_cache and time.time() - cached_time < cache_ttl:
    cache_hits += 1
    return cached_data
else:
    cache_misses += 1
    # ... fetch new data
```

## Current Status

- ✅ Cache working: 5-second TTL
- ✅ Rate limiting: 10 req/sec enforced
- ✅ Fallback chain: wagmi.global → CCXT
- ✅ Parallel processing: Batched for efficiency
- ⚠️ No background refresh: Data fetched on-demand

## Recommendations

For **trading agents** that need very fresh data:

1. **Option A**: Reduce cache TTL to 1-2 seconds
   ```python
   cache_ttl = 1.0  # Refresh every second
   ```

2. **Option B**: Add a `?refresh=true` parameter to force refresh
   ```python
   @app.get("/indicators")
   async def get_indicators_all(refresh: bool = False):
       if refresh:
           # Clear cache for all symbols
           data_cache.clear()
   ```

3. **Option C**: Add background refresh task (most complex but best for high-frequency)

---

**Current setup is optimal for most use cases: fast responses with reasonable freshness (5 seconds).**
