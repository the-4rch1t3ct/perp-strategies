# Compact API Reference - 2 Endpoints Only

## 🎯 **Endpoint 1: Single Symbol** 
**`GET /api/trade/{symbol}?min_strength=0.6&max_distance=3.0`**

### Response Structure:
```json
{
  "symbol": "BTCUSDT",
  "price": 89175.10,
  "signal": {
    "dir": "LONG",        // "LONG", "SHORT", "NEUTRAL"
    "entry": 89175.10,
    "sl": 87386.99,      // stop_loss
    "tp": 89874.15,      // take_profit
    "conf": 0.85,        // confidence (0-1)
    "rr": 2.5            // risk_reward ratio
  },
  "levels": {
    "support": [88750.00, 88400.00],      // Top 3 support prices
    "resistance": [89427.01, 89650.00]    // Top 3 resistance prices
  },
  "sentiment": {
    "bias": "BULLISH",    // "BULLISH", "BEARISH", "NEUTRAL"
    "lsr": 1.15,          // long_short_ratio
    "oi": 9067667699.67  // total_oi_usd
  },
  "clusters": {
    "best": {
      "price": 89427.01,
      "side": "short",
      "str": 0.85,        // strength (0-1)
      "dist": 0.28        // distance_from_price (%)
    },
    "count": 8           // total clusters
  },
  "ts": "2026-01-28T22:30:00"
}
```

### What's Included:
✅ **Trading Signal** - Ready to execute (dir, entry, sl, tp, conf, rr)  
✅ **Support/Resistance** - Top 3 levels each  
✅ **Market Sentiment** - Bias, long/short ratio, total OI  
✅ **Best Cluster** - Strongest cluster for context  
✅ **Current Price** - Latest market price  

---

## 🎯 **Endpoint 2: Multi-Symbol Batch (Auto-Push)**
**`GET /api/trade/batch?min_strength=0.6&max_distance=3.0`**

**No request body needed!** Automatically returns data for ALL 16 supported symbols:
ETH, SOL, BNB, XRP, TRX, DOGE, ADA, BCH, LINK, XMR, XLM, ZEC, HYPE, LTC, SUI, AVAX

### Query Parameters (optional):
- `min_strength`: Minimum cluster strength (default: 0.6)
- `max_distance`: Maximum distance from price % (default: 3.0)

### Response Structure:
```json
{
  "results": {
    "BTCUSDT": {
      "signal": {"dir": "LONG", "entry": 89175.10, "sl": 87386.99, "tp": 89874.15, "conf": 0.85, "rr": 2.5},
      "levels": {"support": [88750.00], "resistance": [89427.01]},
      "sentiment": {"bias": "BULLISH", "lsr": 1.15, "oi": 9067667699.67},
      "clusters": {"best": {"price": 89427.01, "side": "short", "str": 0.85, "dist": 0.28}, "count": 8}
    },
    "ETHUSDT": {
      "signal": {"dir": "NEUTRAL", "entry": null, "sl": null, "tp": null, "conf": 0.0, "rr": null},
      "levels": {"support": [2400.00], "resistance": [2500.00]},
      "sentiment": {"bias": "NEUTRAL", "lsr": 1.0, "oi": 1500000000.0},
      "clusters": {"best": null, "count": 3}
    }
  },
  "ts": "2026-01-28T22:30:00"
}
```

**Note:** Price field removed - agent gets price from its own data source. Entry price in signal is only provided when there's an active signal (LONG/SHORT), otherwise null.

### What's Included:
✅ **Trading Signal** - Ready to execute (dir, entry, sl, tp, conf, rr)  
✅ **Support/Resistance** - Top 3 levels each  
✅ **Market Sentiment** - Bias, long/short ratio, total OI  
✅ **Best Cluster** - Strongest cluster for context  
✅ **Multiple symbols** in one API call  
✅ **No price field** - Agent gets price from its own source  
✅ **Efficient** for multi-coin strategies  

---

## 📋 Field Abbreviations

| Full Name | Abbreviation | Type | Description |
|-----------|--------------|------|-------------|
| direction | dir | string | "LONG", "SHORT", "NEUTRAL" |
| stop_loss | sl | float | Stop loss price |
| take_profit | tp | float | Take profit price |
| confidence | conf | float | Signal confidence (0-1) |
| risk_reward | rr | float | Risk/reward ratio |
| long_short_ratio | lsr | float | Long/short ratio |
| open_interest | oi | float | Total OI in USD |
| strength | str | float | Cluster strength (0-1) |
| distance | dist | float | Distance from price (%) |
| timestamp | ts | string | ISO timestamp |

---

## 💡 Usage Examples

### Python - Single Symbol:
```python
import httpx

response = httpx.get(
    "https://api.wagmi-global.eu/api/trade/BTCUSDT",
    params={"min_strength": 0.6, "max_distance": 3.0}
)
data = response.json()

# Execute trade
if data["signal"]["dir"] == "LONG":
    execute_trade(
        entry=data["signal"]["entry"],
        stop_loss=data["signal"]["sl"],
        take_profit=data["signal"]["tp"]
    )
```

### Python - Multi-Symbol Batch (Auto-Push):
```python
import httpx

# No request body - automatically gets ALL 16 symbols
response = httpx.get(
    "https://api.wagmi-global.eu/api/trade/batch",
    params={"min_strength": 0.6, "max_distance": 3.0}
)
data = response.json()

# Process all symbols (agent already has price from its own source)
for symbol, info in data["results"].items():
    if info["signal"]["dir"] != "NEUTRAL":
        # Use agent's current price for entry if signal entry is None
        entry_price = info["signal"]["entry"] or get_current_price(symbol)
        execute_trade(
            symbol=symbol,
            direction=info["signal"]["dir"],
            entry=entry_price,
            stop_loss=info["signal"]["sl"],
            take_profit=info["signal"]["tp"]
        )
```

### JavaScript/Node.js:
```javascript
// Single symbol
const response = await fetch('https://api.wagmi-global.eu/api/trade/BTCUSDT?min_strength=0.6&max_distance=3.0');
const data = await response.json();

if (data.signal.dir === 'LONG') {
    executeTrade(data.signal.entry, data.signal.sl, data.signal.tp);
}

// Batch - Auto-push all symbols (no request body needed)
const batchResponse = await fetch('https://api.wagmi-global.eu/api/trade/batch?min_strength=0.6&max_distance=3.0');
const batchData = await batchResponse.json();

// Process all 16 symbols automatically
for (const [symbol, info] of Object.entries(batchData.results)) {
    if (info.signal.dir !== 'NEUTRAL') {
        executeTrade(symbol, info.signal);
    }
}
```

---

## ✅ Benefits

1. **Super Compact** - Abbreviated field names reduce payload size
2. **All Essential Data** - Signal, levels, sentiment, clusters in one call
3. **Efficient** - 1-2 API calls instead of 4-5
4. **Fast** - Single request = faster execution
5. **Simple** - Easy to integrate into strategies

---

## 🎯 Data Included Summary

### Signal Data:
- Direction (LONG/SHORT/NEUTRAL)
- Entry, Stop Loss, Take Profit prices
- Confidence score (0-1)
- Risk/Reward ratio

### Level Data:
- Top 3 Support levels (prices)
- Top 3 Resistance levels (prices)

### Sentiment Data:
- Market bias (BULLISH/BEARISH/NEUTRAL)
- Long/Short ratio
- Total Open Interest (USD)

### Cluster Data:
- Best cluster (price, side, strength, distance)
- Total cluster count

### Price Data:
- Current market price

---

## 🚀 Quick Start

**For single symbol strategies:**
```
GET /api/trade/{symbol}
```

**For multi-symbol strategies:**
```
POST /api/trade/batch
```

**That's it!** All essential trading data in 2 compact endpoints. 🎯
