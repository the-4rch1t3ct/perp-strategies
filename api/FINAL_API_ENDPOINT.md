# Live Indicators API - Final Endpoint Information

## ✅ API Status: RUNNING

**Base URL**: `http://localhost:8002` (or check available port)

## Main Endpoint - All Symbols

**GET** `http://localhost:8002/indicators`

**Returns**: Live indicators for all 31 memecoin symbols

**Response Time**: ~1-3 seconds

**Rate Limits**: 
- 10 requests per second (auto-enforced)
- 5-second caching

## Complete Response Structure

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
    },
    ... (30 more symbols)
  ],
  "timestamp": "2026-01-26T23:05:00",
  "latency_ms": 1250.5
}
```

## All 31 Symbols Included

1. DOGE/USDT:USDT
2. WIF/USDT:USDT
3. BRETT/USDT:USDT
4. TURBO/USDT:USDT
5. MEW/USDT:USDT
6. BAN/USDT:USDT
7. PNUT/USDT:USDT
8. POPCAT/USDT:USDT
9. MOODENG/USDT:USDT
10. MEME/USDT:USDT
11. NEIRO/USDT:USDT
12. PEOPLE/USDT:USDT
13. BOME/USDT:USDT
14. DEGEN/USDT:USDT
15. GOAT/USDT:USDT
16. BANANA/USDT:USDT
17. ACT/USDT:USDT
18. DOGS/USDT:USDT
19. CHILLGUY/USDT:USDT
20. HIPPO/USDT:USDT
21. 1000SHIB/USDT:USDT
22. 1000PEPE/USDT:USDT
23. 1000BONK/USDT:USDT
24. 1000FLOKI/USDT:USDT
25. 1000CHEEMS/USDT:USDT
26. 1000000MOG/USDT:USDT
27. 1000SATS/USDT:USDT
28. 1000CAT/USDT:USDT
29. 1MBABYDOGE/USDT:USDT
30. 1000WHY/USDT:USDT
31. KOMA/USDT:USDT

## Quick Test

```bash
# Test API
curl http://localhost:8002/

# Get all indicators
curl http://localhost:8002/indicators

# Get single symbol
curl http://localhost:8002/indicators/DOGE/USDT:USDT

# List symbols
curl http://localhost:8002/symbols
```

## Starting the API

```bash
cd /home/botadmin/memecoin-perp-strategies
./api/start_api_venv.sh
```

The API will automatically find an available port and start serving requests.

---

**API is ready for your trading agent!**
