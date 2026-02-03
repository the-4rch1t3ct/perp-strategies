# Live Indicators API

Real-time API providing all required trading indicators for the memecoin momentum strategy.

## Setup

```bash
cd api
pip install -r requirements_api.txt
python live_indicators_api.py
```

Or with uvicorn:
```bash
uvicorn live_indicators_api:app --host 0.0.0.0 --port 8000
```

## Endpoints

### GET `/`
API information and available endpoints

### GET `/symbols`
List all 31 allowed trading symbols

### GET `/indicators/{symbol}`
Get live indicators for a single symbol

**Example**: `GET /indicators/DOGE/USDT:USDT`

**Response**:
```json
{
  "success": true,
  "data": {
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
  "timestamp": "2026-01-26T22:00:00"
}
```

### GET `/indicators`
Get live indicators for all 31 symbols (parallel fetch)

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "timestamp": "2026-01-26T22:00:00",
      "price": 0.19266,
      "volume": 470121744.0,
      "indicators": {...},
      "signal_strength": 0.68,
      "entry_signal": "LONG",
      "leverage": 20.0
    },
    ...
  ],
  "timestamp": "2026-01-26T22:00:00"
}
```

## Indicators Provided

All 11 required indicators:
1. **ema_fast**: Fast EMA (12 periods)
2. **ema_slow**: Slow EMA (36 periods)
3. **rsi**: RSI (14 periods)
4. **momentum**: Momentum/ROC (12 periods)
5. **atr**: Average True Range (14 periods)
6. **atr_pct**: ATR as percentage of price
7. **volume_ma**: Volume moving average (36 periods)
8. **volume_ratio**: Current volume / Volume MA
9. **volume_percentile**: Volume percentile (0-100)
10. **macd**: MACD line
11. **macd_signal**: MACD signal line
12. **macd_histogram**: MACD histogram
13. **trend_strength**: Trend strength (EMA separation)
14. **price_position**: Price position in 20-period range (0-1)

## Additional Data

- **signal_strength**: Calculated signal strength (0-1)
- **entry_signal**: 'LONG', 'SHORT', or null
- **leverage**: Recommended leverage (10x, 15x, or 20x)

## Data Source

- Primary: api.wagmi.global
- Fallback: CCXT (Binance Futures)

## Usage Example

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get single symbol
    response = await client.get("http://localhost:8000/indicators/DOGE/USDT:USDT")
    data = response.json()
    
    if data['data']['entry_signal']:
        print(f"Entry signal: {data['data']['entry_signal']}")
        print(f"Leverage: {data['data']['leverage']}x")
        print(f"Signal strength: {data['data']['signal_strength']}")
    
    # Get all symbols
    response = await client.get("http://localhost:8000/indicators")
    all_data = response.json()
    
    # Filter for entry signals
    signals = [d for d in all_data['data'] if d['entry_signal']]
    print(f"Found {len(signals)} entry signals")
```
