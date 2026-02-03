# Rate Limits and Optimization Guide

## Current Rate Limits

### API Rate Limiter
- **Max Calls**: 10 requests per second
- **Period**: 1.0 second
- **Type**: Token bucket / sliding window
- **Scope**: Applied to all external API calls (api.wagmi.global, CCXT)

### Current Settings

| Setting | Value | Purpose |
|---------|-------|---------|
| **Rate Limit** | 10 req/sec | Prevents API throttling |
| **Cache TTL** | 5 seconds | Reduces redundant API calls |
| **Batch Size** | 10 symbols | Processes symbols in parallel batches |
| **Timeout** | 5 seconds per symbol | Prevents hanging requests |
| **HTTP Timeout** | 3 seconds | Fast failure for slow endpoints |

## How It Works

### Rate Limiter Flow

```
Request → Check if < 10 calls in last 1 second
    ↓
[Yes] → Execute immediately
    ↓
[No] → Wait until oldest call expires
    ↓
Execute → Record timestamp
```

### Example Timeline

```
t=0.0s:  Request 1-10 → Execute immediately ✅
t=0.1s:  Request 11 → Wait 0.9s → Execute ✅
t=0.2s:  Request 12 → Wait 0.8s → Execute ✅
t=1.0s:  Request 1 expires, slot available
t=1.1s:  Request 13 → Execute immediately ✅
```

### For 31 Symbols

- **Batch 1** (10 symbols): ~1 second
- **Batch 2** (10 symbols): ~1 second  
- **Batch 3** (11 symbols): ~1.1 seconds
- **Total**: ~3.1 seconds for all 31 symbols

## Optimization Options

### Option 1: Increase Rate Limit (If API Allows)

If `api.wagmi.global` allows more than 10 req/sec:

```python
# In live_indicators_api_optimized.py, line 69
rate_limiter = RateLimiter(max_calls=20, period=1.0)  # 20 req/sec
```

**Impact:**
- 31 symbols in ~1.6 seconds (instead of ~3.1 seconds)
- ⚠️ Risk: May hit API rate limits if too aggressive

### Option 2: Increase Cache TTL

Reduce refresh frequency:

```python
# In live_indicators_api_optimized.py, line 73
cache_ttl = 10.0  # 10 seconds instead of 5
```

**Impact:**
- Fewer API calls (data cached longer)
- ⚠️ Trade-off: Data can be up to 10 seconds old

### Option 3: Larger Batch Size

Process more symbols in parallel:

```python
# In live_indicators_api_optimized.py, line 447
batch_size = 20  # Instead of 10
```

**Impact:**
- Faster processing if rate limit allows
- ⚠️ Risk: May overwhelm rate limiter

### Option 4: Per-Endpoint Rate Limiting

Different limits for different APIs:

```python
# Separate limiters
wagmi_limiter = RateLimiter(max_calls=15, period=1.0)  # More permissive
ccxt_limiter = RateLimiter(max_calls=5, period=1.0)    # More restrictive
```

**Impact:**
- Optimize based on each API's actual limits
- More complex to manage

### Option 5: Connection Pooling

Reuse HTTP connections:

```python
# Create persistent client
client = httpx.AsyncClient(
    timeout=3.0,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
)
```

**Impact:**
- Faster requests (no connection overhead)
- Better resource utilization

### Option 6: Smart Caching Strategy

Cache by symbol popularity:

```python
# Cache popular symbols longer
if symbol in HIGH_VOLUME_SYMBOLS:
    cache_ttl = 3.0  # Refresh more often
else:
    cache_ttl = 10.0  # Cache longer
```

## Recommended Optimizations

### For Maximum Throughput

```python
# 1. Increase rate limit (if API allows)
rate_limiter = RateLimiter(max_calls=20, period=1.0)

# 2. Larger batches
batch_size = 20

# 3. Connection pooling
client = httpx.AsyncClient(
    timeout=3.0,
    limits=httpx.Limits(max_connections=30)
)
```

**Expected Result:**
- 31 symbols in ~1.5-2 seconds
- Higher throughput
- ⚠️ Monitor for rate limit errors

### For Maximum Efficiency (Fewer API Calls)

```python
# 1. Longer cache TTL
cache_ttl = 10.0  # 10 seconds

# 2. Keep current rate limit
rate_limiter = RateLimiter(max_calls=10, period=1.0)

# 3. Smart cache invalidation
# Only refresh symbols that changed significantly
```

**Expected Result:**
- Fewer API calls
- Lower latency for cached requests
- ⚠️ Data freshness trade-off

### For Balanced Performance (Recommended)

```python
# 1. Moderate rate limit increase
rate_limiter = RateLimiter(max_calls=15, period=1.0)

# 2. Keep cache TTL at 5 seconds
cache_ttl = 5.0

# 3. Connection pooling
client = httpx.AsyncClient(
    timeout=3.0,
    limits=httpx.Limits(max_connections=20)
)
```

**Expected Result:**
- 31 symbols in ~2 seconds
- Good balance of speed and API usage
- Lower risk of rate limit issues

## Monitoring Rate Limits

### Check Current Usage

Add logging to monitor:

```python
class RateLimiter:
    def __init__(self, max_calls: int = 10, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.total_calls = 0
        self.waited_count = 0
    
    async def acquire(self):
        # ... existing code ...
        if len(self.calls) >= self.max_calls:
            self.waited_count += 1  # Track waits
            # ... wait logic ...
        self.total_calls += 1
```

### Metrics to Track

- **Total calls per minute**
- **Wait time** (how often rate limit is hit)
- **Cache hit rate**
- **Average latency**

## Testing Rate Limits

```bash
# Test current rate limit
for i in {1..20}; do
    curl -s "https://api.wagmi-global.eu/indicators" > /dev/null &
done
wait
# Check if all requests succeeded
```

## Current Performance

- **31 symbols**: ~3 seconds
- **Rate limit**: 10 req/sec (conservative)
- **Cache hit rate**: ~80% (for requests within 5 seconds)
- **API calls per request**: ~31 (if cache expired) or ~0 (if cached)

## Recommendations

1. **Start conservative**: Current 10 req/sec is safe
2. **Monitor**: Watch for rate limit errors
3. **Gradually increase**: If no errors, try 15 req/sec
4. **Use caching**: 5-second TTL is good balance
5. **Connection pooling**: Easy win for performance

---

**Current setup is conservative and safe. You can optimize based on actual API limits and usage patterns.**
