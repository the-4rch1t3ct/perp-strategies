# ✅ API is Running and Ready for Testing

## Status: **LIVE**

**Base URL**: `http://localhost:8002`

## Quick Test Commands

```bash
# Test root endpoint
curl http://localhost:8002/

# Get all 31 symbols with indicators
curl http://localhost:8002/indicators

# Get single symbol
curl http://localhost:8002/indicators/DOGE/USDT:USDT

# List all symbols
curl http://localhost:8002/symbols
```

## Main Endpoint

**GET** `http://localhost:8002/indicators`

Returns complete indicators for all 31 memecoin symbols.

**Expected Response Time**: 1-3 seconds

**Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "timestamp": "2026-01-26T23:10:00",
      "price": 0.12219,
      "volume": 979537.0,
      "indicators": {
        "ema_fast": 0.12243,
        "ema_slow": 0.12238,
        "rsi": 42.01,
        "momentum": -0.0030,
        "atr": 0.000241,
        "atr_pct": 0.198,
        "volume_ma": 8789352.5,
        "volume_ratio": 0.111,
        "volume_percentile": 1.0,
        "macd": 0.000035,
        "macd_signal": 0.000079,
        "macd_histogram": -0.000044,
        "trend_strength": 0.000460,
        "price_position": 0.094
      },
      "signal_strength": null,
      "entry_signal": null,
      "leverage": null
    }
    ... (30 more symbols)
  ],
  "timestamp": "2026-01-26T23:10:00",
  "latency_ms": 1250.5
}
```

## Process Information

The API is running in the background. To check logs:

```bash
tail -f /tmp/api_running.log
```

To stop the API:

```bash
pkill -f live_indicators_api_optimized
```

To restart:

```bash
cd /home/botadmin/memecoin-perp-strategies
source venv/bin/activate
cd api
PORT=8002 nohup python3 live_indicators_api_optimized.py > /tmp/api_running.log 2>&1 &
```

## Testing with Python

```python
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("http://localhost:8002/indicators")
        data = response.json()
        print(f"Fetched {len(data['data'])} symbols")
        print(f"Latency: {data['latency_ms']}ms")

asyncio.run(test())
```

---

**API is ready for your trading agent!**
