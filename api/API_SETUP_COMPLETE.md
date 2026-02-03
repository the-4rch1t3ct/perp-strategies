# Live Indicators API - Setup Complete ✅

## API Status

**✅ API is running and operational**

## Main Endpoint (All Symbols)

**URL**: `http://localhost:8001/indicators`

**Method**: GET

**Description**: Returns live indicators for all 31 memecoin symbols in a single request.

**Response Time**: ~1-3 seconds (all 31 symbols)

**Rate Limits**: 
- 10 requests per second (automatically enforced)
- 5-second caching (reduces redundant requests)

## Response Structure

```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "timestamp": "2026-01-26T23:00:00",
      "price": 0.12222,
      "volume": 8485959.0,
      "indicators": {
        "ema_fast": 0.12248,
        "ema_slow": 0.12239,
        "rsi": 39.01,
        "momentum": -0.0035,
        "atr": 0.000256,
        "atr_pct": 0.209,
        "volume_ma": 8821411.08,
        "volume_ratio": 0.962,
        "volume_percentile": 40.0,
        "macd": 0.000062,
        "macd_signal": 0.000090,
        "macd_histogram": -0.000028,
        "trend_strength": 0.000733,
        "price_position": 0.257
      },
      "signal_strength": null,
      "entry_signal": null,
      "leverage": null
    },
    ... (30 more symbols)
  ],
  "timestamp": "2026-01-26T23:00:00",
  "latency_ms": 1250.5
}
```

## All Indicators Provided

For each symbol, the API provides:

1. **Price & Volume**: Current price and volume
2. **EMA Fast**: 12-period exponential moving average
3. **EMA Slow**: 36-period exponential moving average
4. **RSI**: 14-period relative strength index
5. **Momentum**: 12-period rate of change
6. **ATR**: 14-period average true range (absolute and %)
7. **Volume MA**: 36-period volume moving average
8. **Volume Ratio**: Current volume / Volume MA
9. **Volume Percentile**: Volume rank (0-100%)
10. **MACD**: MACD line, signal line, and histogram
11. **Trend Strength**: EMA separation strength
12. **Price Position**: Position in 20-period range (0-1)

**Plus**:
- **Signal Strength**: Calculated strength (0-1) if entry conditions met
- **Entry Signal**: 'LONG', 'SHORT', or null
- **Leverage**: Recommended leverage (10x, 15x, or 20x) if signal exists

## Usage Examples

### Python (Async)
```python
import httpx
import asyncio

async def get_all_indicators():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get("http://localhost:8001/indicators")
        data = response.json()
        
        if data['success']:
            print(f"Fetched {len(data['data'])} symbols in {data['latency_ms']}ms")
            
            # Find entry signals
            signals = [d for d in data['data'] if d['entry_signal']]
            for signal in signals:
                print(f"{signal['symbol']}: {signal['entry_signal']} @ {signal['leverage']}x")

asyncio.run(get_all_indicators())
```

### Python (Sync)
```python
import requests

response = requests.get("http://localhost:8001/indicators", timeout=10)
data = response.json()

if data['success']:
    signals = [d for d in data['data'] if d['entry_signal']]
    print(f"Found {len(signals)} entry signals")
```

### cURL
```bash
curl http://localhost:8001/indicators | jq '.data[] | select(.entry_signal != null)'
```

### JavaScript/Node.js
```javascript
const fetch = require('node-fetch');

async function getIndicators() {
    const response = await fetch('http://localhost:8001/indicators');
    const data = await response.json();
    
    if (data.success) {
        const signals = data.data.filter(d => d.entry_signal);
        console.log(`Found ${signals.length} entry signals`);
    }
}

getIndicators();
```

## Other Endpoints

### Single Symbol
**GET** `/indicators/{symbol}`

Example: `http://localhost:8001/indicators/DOGE/USDT:USDT`

### Symbol List
**GET** `/symbols`

Returns list of all 31 allowed symbols.

## Performance Optimizations

1. **Caching**: 5-second TTL reduces redundant API calls
2. **Vectorized Calculations**: NumPy-based for speed
3. **Parallel Fetching**: Batched (10 symbols at a time)
4. **Rate Limiting**: Automatic (10 req/sec)
5. **Low Latency**: Optimized data structures

## Starting/Stopping the API

### Start
```bash
cd /home/botadmin/memecoin-perp-strategies
./api/start_api_venv.sh
```

Or manually:
```bash
cd /home/botadmin/memecoin-perp-strategies
source venv/bin/activate
cd api
python3 live_indicators_api_optimized.py
```

### Stop
```bash
pkill -f live_indicators_api_optimized.py
```

Or find the process:
```bash
lsof -i :8001
kill <PID>
```

## Data Source

- **Primary**: api.wagmi.global (with multiple endpoint patterns)
- **Fallback**: CCXT (Binance Futures)
- **Caching**: 5-second TTL for performance

## Monitoring

Check API status:
```bash
curl http://localhost:8001/
```

Check latency:
```bash
time curl -s http://localhost:8001/indicators > /dev/null
```

## Notes

- API runs on port 8001 by default (auto-finds available port)
- All 31 symbols are fetched in parallel (batched)
- Response includes latency in milliseconds
- Entry signals are pre-calculated (no need to recalculate)
- Leverage recommendations included

---

**API is ready for production use!**
