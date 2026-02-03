# Rolling Refresh Mechanism

## How It Works

### Before (All at Once)
- All 31 symbols cached at same time
- All expire together after 3 minutes
- **Average data age**: 1.5 minutes (0-3 min range)
- **Problem**: When cache expires, all 31 symbols refresh at once (slow)

### After (Rolling Refresh)
- Each symbol gets a random 0-60 second offset
- Symbols expire at different times (staggered)
- **Average data age**: ~1.5 minutes, but more recent on average
- **Benefit**: Never all refresh at once, smoother load

## Example Timeline

```
t=0:00  - Request → Fetch all 31 → Cache all
         - DOGE: expires at t=3:00
         - WIF: expires at t=3:15 (15s offset)
         - BRETT: expires at t=3:30 (30s offset)
         - TURBO: expires at t=3:45 (45s offset)
         - etc.

t=1:00  - Request → All cached → Fast
t=2:00  - Request → All cached → Fast
t=3:00  - Request → DOGE expired → Refresh DOGE only
         - Others still cached → Fast
t=3:15  - Request → WIF expired → Refresh WIF only
         - Others cached → Fast
t=3:30  - Request → BRETT expired → Refresh BRETT only
         - Others cached → Fast
```

## Benefits

1. **Smoother Load**: Never all 31 symbols refresh at once
2. **More Recent Data**: On average, data is fresher
3. **Better Performance**: Most requests only refresh a few symbols
4. **Consistent Latency**: No sudden 8-10 second spikes

## Cache Offset Distribution

- **Offset Range**: 0-60 seconds (random per symbol)
- **Expiry Window**: 3:00 to 3:60 (180-240 seconds)
- **Average Refresh**: ~1-2 symbols per minute (after initial cache)

## Performance Impact

**Before (All at Once)**:
- Every 3 minutes: 8-10 seconds (all 31 refresh)
- Other times: 50-200ms (all cached)

**After (Rolling)**:
- Most requests: 100-500ms (only 1-2 symbols refresh)
- Rarely: 2-3 seconds (if many symbols expired)
- Average: ~200-300ms (much better!)

---

**Rolling refresh is now active! Data stays fresher on average.**
