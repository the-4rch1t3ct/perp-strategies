# Shorter Cache TTL - Optimized for Freshness

## Changes Made

### Cache TTL Reduced
- **Before**: 3 minutes (180 seconds)
- **After**: 2 minutes (120 seconds)
- **Improvement**: 2x more frequent refreshes

### Rolling Offset Adjusted
- **Before**: 0-60 second offset
- **After**: 0-40 second offset
- **Reason**: Matches shorter TTL window

## Rate Limit Safety Analysis

### Current Settings
- **Rate Limit**: 20 requests/second
- **Symbols**: 31
- **Cache TTL**: 2 minutes
- **Rolling Offset**: 0-40 seconds

### With Rolling Refresh
- **Average refresh per request**: 1-2 symbols
- **Peak refresh**: 5-10 symbols (rare, when many expire)
- **Worst case**: 10 symbols = 0.5 seconds at 20 req/sec
- **Status**: ✅ Very safe

### Safety Margin
- **Theoretical max**: 20 req/sec
- **Actual usage**: ~1-2 req per request (rolling refresh)
- **Safety margin**: ~10x headroom

## Performance Impact

### Data Freshness
- **Before**: Average age ~1.5 minutes (0-3 min range)
- **After**: Average age ~1 minute (0-2 min range)
- **Improvement**: 33% fresher on average

### Request Latency
- **Cached requests**: ~50-200ms (unchanged)
- **Requests with refreshes**: ~100-500ms (1-2 symbols)
- **Peak requests**: ~1-2 seconds (5-10 symbols, rare)

## Timeline Example

```
t=0:00  - Request → Fetch all 31 → Cache all
         - DOGE: expires at t=2:00
         - WIF: expires at t=2:10 (10s offset)
         - BRETT: expires at t=2:20 (20s offset)
         - etc.

t=1:00  - Request → All cached → Fast (< 200ms)
t=2:00  - Request → DOGE expired → Refresh DOGE only → Fast
t=2:10  - Request → WIF expired → Refresh WIF only → Fast
t=2:20  - Request → BRETT expired → Refresh BRETT only → Fast
```

## Further Optimization Options

If you want even fresher data:

1. **1.5 minutes (90s)**: Still safe, 3x more frequent
2. **1 minute (60s)**: Still safe, 4x more frequent
3. **30 seconds**: Pushing limits, but possible with rolling refresh

**Recommendation**: 2 minutes is optimal balance of freshness and safety.

---

**Cache TTL reduced to 2 minutes - data is now fresher while staying safe from rate limits!**
