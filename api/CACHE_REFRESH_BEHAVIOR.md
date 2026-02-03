# Cache Refresh Behavior Analysis

## Current Implementation: ROLLING REFRESHES

### How It Works Now

1. **Per-Symbol Cache**: Each symbol has its own cache entry with timestamp
2. **Independent Expiry**: Each symbol's cache expires independently after 3 minutes
3. **Rolling Refresh**: When a symbol's cache expires, only that symbol is fetched fresh
4. **Mixed State**: Some symbols may be cached, others may be fresh

### Example Timeline

```
t=0:00  - Agent polls → All 31 symbols fetched → All cached
t=0:30  - Agent polls → All symbols still cached (< 3 min) → Fast response
t=1:00  - Agent polls → All symbols still cached → Fast response
t=3:00  - Agent polls → Cache expires for all → All fetched fresh
t=3:05  - Someone requests → All symbols cached → Fast response
t=6:00  - Agent polls → Cache expires → All fetched fresh
```

**Actually, with current implementation:**
- If all symbols are fetched at t=0:00, they all expire at t=3:00
- So they DO refresh all at once (not rolling)

### Current Behavior: ALL AT ONCE (when cache expires)

Since all symbols are fetched in the same request and cached at the same time, they all expire together after 3 minutes. This means:

- **First request after 3 minutes**: All 31 symbols fetched fresh (~8-10 seconds)
- **Subsequent requests within 3 minutes**: All from cache (~50-200ms)

## Options

### Option 1: Keep Current (All at Once)
- ✅ Simple
- ✅ Predictable (all data same age)
- ⚠️ Slower when cache expires (8-10 seconds)

### Option 2: Rolling Refreshes (Staggered)
- ✅ Smoother load (never all at once)
- ✅ Faster individual requests
- ⚠️ Data age varies per symbol
- ⚠️ More complex

### Option 3: Background Refresh (Pre-fetch)
- ✅ Always fresh data ready
- ✅ Fast responses
- ⚠️ More complex
- ⚠️ Uses more resources

## Recommendation

**Keep current (all at once)** because:
1. Your agent polls every 3 minutes
2. All data is same age (consistent)
3. Cache hit rate is high (most requests are fast)
4. Simple and predictable

---

**Current: All symbols refresh together when cache expires (every 3 minutes)**
