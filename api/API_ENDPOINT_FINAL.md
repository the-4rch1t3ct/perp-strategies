# Live Indicators API - Final Endpoint

## ✅ API is Running and Ready

**Endpoint**: `http://localhost:8002/indicators`

**Method**: GET

**Returns**: Complete indicators for all 31 memecoin symbols

## Quick Access

```bash
# Get all indicators (all 31 symbols)
curl http://localhost:8002/indicators

# Get single symbol
curl http://localhost:8002/indicators/DOGE/USDT:USDT

# List symbols
curl http://localhost:8002/symbols
```

## Response Format

```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "timestamp": "2026-01-26T23:05:00",
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
  "timestamp": "2026-01-26T23:05:00",
  "latency_ms": 1250.5
}
```

## All Indicators Provided

For each of the 31 symbols:

1. **Price & Volume**: Current market data
2. **EMA Fast** (12 periods)
3. **EMA Slow** (36 periods)
4. **RSI** (14 periods)
5. **Momentum** (12 periods)
6. **ATR** (14 periods) + ATR%
7. **Volume MA** (36 periods)
8. **Volume Ratio**
9. **Volume Percentile** (0-100%)
10. **MACD** (line, signal, histogram)
11. **Trend Strength**
12. **Price Position** (0-1)

**Plus**:
- **Signal Strength** (if entry conditions met)
- **Entry Signal** ('LONG'/'SHORT' or null)
- **Leverage** (10x/15x/20x if signal exists)

## Performance

- **Latency**: 1-3 seconds for all 31 symbols
- **Caching**: 5-second TTL
- **Rate Limits**: 10 req/sec (auto-enforced)
- **Data Source**: api.wagmi.global → CCXT fallback → Local CSV cache

## Starting the API

```bash
cd /home/botadmin/memecoin-perp-strategies
./api/start_api_venv.sh
```

The API will find an available port and start automatically.

---

**Your trading agent can now call: `GET http://localhost:8002/indicators`**
