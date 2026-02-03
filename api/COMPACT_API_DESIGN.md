# Compact API Design - 2 Endpoints Only

## 🎯 Goal
Feed ALL essential trading data through just 2 API endpoints - super compact and efficient.

---

## 📊 Endpoint 1: Single Symbol Trading Data
**`GET /api/trade/{symbol}`**

**Purpose:** Everything needed for trading ONE symbol in a single call.

**Response Structure:**
```json
{
  "symbol": "BTCUSDT",
  "price": 89175.10,
  "signal": {
    "dir": "LONG",           // "LONG", "SHORT", "NEUTRAL"
    "entry": 89175.10,
    "sl": 87386.99,          // stop_loss
    "tp": 89874.15,          // take_profit
    "conf": 0.85,            // confidence
    "rr": 2.5                // risk_reward
  },
  "levels": {
    "support": [88750.00, 88400.00],    // Top 3 support prices
    "resistance": [89427.01, 89650.00]  // Top 3 resistance prices
  },
  "sentiment": {
    "bias": "BULLISH",       // "BULLISH", "BEARISH", "NEUTRAL"
    "lsr": 1.15,            // long_short_ratio
    "oi": 9067667699.67     // total_oi_usd
  },
  "clusters": {
    "best": {
      "price": 89427.01,
      "side": "short",
      "str": 0.85,           // strength
      "dist": 0.28           // distance_from_price %
    },
    "count": 8               // total clusters
  },
  "ts": "2026-01-28T22:30:00"  // timestamp
}
```

**Key Features:**
- ✅ Trading signal (ready to use)
- ✅ Support/resistance levels
- ✅ Market sentiment
- ✅ Best cluster (for context)
- ✅ All in one compact response

---

## 📊 Endpoint 2: Multi-Symbol Batch
**`POST /api/trade/batch`**

**Purpose:** Get trading data for MULTIPLE symbols in one call.

**Request:**
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "min_strength": 0.6,
  "max_distance": 3.0
}
```

**Response Structure:**
```json
{
  "results": {
    "BTCUSDT": {
      "price": 89175.10,
      "signal": {"dir": "LONG", "entry": 89175.10, "sl": 87386.99, "tp": 89874.15, "conf": 0.85, "rr": 2.5},
      "levels": {"support": [88750.00], "resistance": [89427.01]},
      "sentiment": {"bias": "BULLISH", "lsr": 1.15, "oi": 9067667699.67},
      "clusters": {"best": {"price": 89427.01, "side": "short", "str": 0.85, "dist": 0.28}, "count": 8}
    },
    "ETHUSDT": {
      "price": 2450.30,
      "signal": {"dir": "NEUTRAL", "entry": 2450.30, "sl": null, "tp": null, "conf": 0.0, "rr": null},
      "levels": {"support": [2400.00], "resistance": [2500.00]},
      "sentiment": {"bias": "NEUTRAL", "lsr": 1.0, "oi": 1500000000.0},
      "clusters": {"best": null, "count": 3}
    }
  },
  "ts": "2026-01-28T22:30:00"
}
```

**Key Features:**
- ✅ Multiple symbols in one call
- ✅ Same compact structure per symbol
- ✅ Efficient for multi-coin strategies

---

## 🎯 Field Abbreviations (For Compactness)

| Full Name | Abbreviation | Type |
|-----------|--------------|------|
| direction | dir | string |
| stop_loss | sl | float |
| take_profit | tp | float |
| confidence | conf | float |
| risk_reward | rr | float |
| long_short_ratio | lsr | float |
| open_interest | oi | float |
| strength | str | float |
| distance | dist | float |
| timestamp | ts | string |

---

## 💡 Usage Examples

### Single Symbol Strategy:
```python
response = httpx.get("https://api.wagmi-global.eu/api/trade/BTCUSDT")
data = response.json()

if data["signal"]["dir"] == "LONG":
    execute_trade(
        entry=data["signal"]["entry"],
        stop_loss=data["signal"]["sl"],
        take_profit=data["signal"]["tp"]
    )
```

### Multi-Symbol Strategy:
```python
response = httpx.post(
    "https://api.wagmi-global.eu/api/trade/batch",
    json={"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]}
)
data = response.json()

for symbol, info in data["results"].items():
    if info["signal"]["dir"] != "NEUTRAL":
        # Trade this symbol
        pass
```

---

## ✅ Benefits

1. **Efficiency:** 1-2 API calls instead of 4-5
2. **Compact:** Abbreviated field names reduce payload size
3. **Complete:** All essential data included
4. **Fast:** Single request = faster execution
5. **Simple:** Easy to integrate into strategies

---

## 📋 Data Included

### Signal Data:
- Direction (LONG/SHORT/NEUTRAL)
- Entry, Stop Loss, Take Profit
- Confidence & Risk/Reward

### Level Data:
- Top 3 Support levels
- Top 3 Resistance levels

### Sentiment Data:
- Market bias
- Long/Short ratio
- Total OI

### Cluster Data:
- Best cluster (price, side, strength, distance)
- Total cluster count

---

## 🚀 Implementation Priority

**Phase 1:** Single symbol endpoint (`/api/trade/{symbol}`)
**Phase 2:** Multi-symbol batch endpoint (`/api/trade/batch`)

Both endpoints use the same compact response structure for consistency.
