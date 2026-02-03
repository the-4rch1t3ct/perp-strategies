# Live Indicators API - Endpoint Information

## API Endpoint

**Base URL**: `http://localhost:8001` (or check with `./start_api.sh`)

## Main Endpoint (All Symbols)

**GET** `/indicators`

Returns indicators for all 31 symbols in a single request.

**Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "timestamp": "2026-01-26T22:00:00",
      "price": 0.19266,
      "volume": 470121744.0,
      "indicators": {
        "ema_fast": 0.19250,
        "ema_slow": 0.19200,
        "rsi": 55.2,
        "momentum": 0.005,
        "atr": 0.001,
        "atr_pct": 0.52,
        "volume_ma": 300000000.0,
        "volume_ratio": 1.57,
        "volume_percentile": 75.5,
        "macd": 0.0001,
        "macd_signal": 0.00008,
        "macd_histogram": 0.00002,
        "trend_strength": 0.0026,
        "price_position": 0.65
      },
      "signal_strength": 0.68,
      "entry_signal": "LONG",
      "leverage": 20.0
    },
    ... (30 more symbols)
  ],
  "timestamp": "2026-01-26T22:00:00",
  "latency_ms": 1250.5
}
```

## Features

- **Low Latency**: 
  - 5-second caching
  - Vectorized calculations
  - Parallel fetching (batched)
  - Expected latency: 1-3 seconds for all 31 symbols

- **Rate Limit Compliant**:
  - 10 requests per second max
  - Automatic rate limiting
  - Batched processing (10 symbols at a time)

- **Complete Data**:
  - All 11 required indicators
  - Entry signals (LONG/SHORT)
  - Signal strength (0-1)
  - Recommended leverage (10x/15x/20x)
  - Current price and volume

## Usage Example

```python
import httpx
import asyncio

async def get_all_indicators():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get("http://localhost:8001/indicators")
        data = response.json()
        
        if data['success']:
            print(f"Fetched {len(data['data'])} symbols in {data['latency_ms']}ms")
            
            # Filter for entry signals
            signals = [d for d in data['data'] if d['entry_signal']]
            print(f"Found {len(signals)} entry signals:")
            
            for signal in signals:
                print(f"  {signal['symbol']}: {signal['entry_signal']} @ {signal['leverage']}x leverage")

asyncio.run(get_all_indicators())
```

## Other Endpoints

- `GET /indicators/{symbol}` - Single symbol (e.g., `/indicators/DOGE/USDT:USDT`)
- `GET /symbols` - List all 31 allowed symbols
- `GET /` - API information

## Performance

- **Single Symbol**: ~100-300ms
- **All 31 Symbols**: ~1-3 seconds
- **Cache TTL**: 5 seconds
- **Rate Limit**: 10 req/sec

## Starting the API

```bash
cd /home/botadmin/memecoin-perp-strategies/api
./start_api.sh
```

Or manually:
```bash
python3 live_indicators_api_optimized.py
```

The API will automatically find an available port (starting from 8001).
