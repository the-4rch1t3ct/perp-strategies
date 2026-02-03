# Cache TTL Alignment with Agent Polling

## Configuration

**Cache TTL**: 180 seconds (3 minutes)
**Agent Polling**: Every 3 minutes

## Why This Alignment Works

### Before (5-second cache)
- Agent polls every 3 minutes
- Cache expires every 5 seconds
- **Problem**: Data refreshed 36 times between agent polls (wasteful)
- **Result**: Unnecessary API calls

### After (3-minute cache)
- Agent polls every 3 minutes
- Cache expires every 3 minutes
- **Solution**: Data refreshed exactly when agent needs it
- **Result**: Minimal API calls, fresh data for agent

## Timeline Example

```
t=0:00  - Agent polls → Cache miss → Fetch fresh data → Cache for 3 min
t=0:05  - Someone else requests → Cache hit (fast, no API call)
t=0:10  - Someone else requests → Cache hit (fast, no API call)
...
t=3:00  - Agent polls → Cache expired → Fetch fresh data → Cache for 3 min
t=3:05  - Someone else requests → Cache hit (fast, no API call)
...
t=6:00  - Agent polls → Cache expired → Fetch fresh data → Cache for 3 min
```

## Benefits

1. **Efficient**: Data refreshed only when agent needs it
2. **Fresh**: Agent always gets data from latest 3-minute window
3. **Reduced Load**: Fewer API calls (1 per 3 minutes vs 36 per 3 minutes)
4. **Cost Effective**: Lower API usage
5. **Rate Limit Friendly**: Less pressure on rate limiter

## Rate Limit Impact

With 3-minute cache:
- **API calls per hour**: ~20 (31 symbols × ~20 refresh cycles)
- **API calls per day**: ~480
- **Well within limits**: Even at 10 req/sec, this is very conservative

## For Other Clients

If other clients need more frequent updates:
- Use `?refresh=true` parameter to force fresh fetch
- Cache will still be updated for next 3 minutes
- Agent polling remains aligned

## Monitoring

To verify alignment:
```bash
# Check cache age in response
curl -s "https://api.wagmi-global.eu/indicators" | \
  jq '.data[0].data_age_seconds'

# Should show < 180 seconds if cache is fresh
```

---

**Cache is now perfectly aligned with your agent's 3-minute polling frequency!**
