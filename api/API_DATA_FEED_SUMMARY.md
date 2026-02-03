# API Data Feed Summary - What to Feed Through API

## ✅ **RECOMMENDED DATA TO EXPOSE**

Based on trading strategy needs, here's what should be fed through the API:

---

## 🎯 **Core Trading Data** (MUST HAVE)

### 1. **Trading Signals** ⭐ **HIGHEST PRIORITY**
**Endpoint:** `GET /api/trading-signal/{symbol}`

**What it provides:**
- Pre-computed trading signals (LONG/SHORT/NEUTRAL)
- Entry price, stop loss, take profit levels
- Confidence score (0-1)
- Risk/reward ratio
- Reasoning behind the signal

**Why:** Saves strategy code from re-implementing signal logic. Ready-to-use.

**Example Response:**
```json
{
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "signal": {
    "direction": "LONG",
    "entry": 89175.10,
    "stop_loss": 87386.99,
    "take_profit": 89874.15,
    "confidence": 0.85,
    "risk_reward": 2.5,
    "reason": "Strong short liquidation cluster at $89,427"
  },
  "cluster_data": {
    "price_level": 89427.01,
    "side": "short",
    "strength": 0.85
  }
}
```

---

### 2. **Support/Resistance Levels** ⭐ **HIGH PRIORITY**
**Endpoint:** `GET /api/levels/{symbol}`

**What it provides:**
- Support levels (long clusters below price)
- Resistance levels (short clusters above price)
- Strength and OI for each level
- Distance from current price

**Why:** Most common trading use case - key levels for entry/exit.

**Example Response:**
```json
{
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "support": [
    {"price": 88750.00, "strength": 0.75, "oi_usd": 2500000.0}
  ],
  "resistance": [
    {"price": 89427.01, "strength": 0.85, "oi_usd": 3500000.0}
  ]
}
```

---

### 3. **Market Sentiment** ⭐ **MEDIUM PRIORITY**
**Endpoint:** `GET /api/sentiment/{symbol}`

**What it provides:**
- Long/short ratio
- Total OI
- Market bias (BULLISH/BEARISH/NEUTRAL)
- Interpretation

**Why:** Helps with position sizing and direction bias.

**Example Response:**
```json
{
  "symbol": "BTCUSDT",
  "sentiment": "BULLISH_BIAS",
  "long_short_ratio": 1.15,
  "total_oi_usd": 9067667699.67,
  "interpretation": "More long positions - Short liquidations more likely"
}
```

---

## 📊 **Existing Endpoints** (Already Available)

### 4. **Liquidation Clusters**
**Endpoint:** `GET /api/heatmap/{symbol}`

**What it provides:**
- All liquidation clusters with filters
- Price levels, sides, strength, OI
- Distance from price

**Use Case:** Raw cluster data for custom analysis

---

### 5. **Best Cluster**
**Endpoint:** `GET /api/heatmap/{symbol}/best`

**What it provides:**
- Single strongest cluster

**Use Case:** Quick signal for immediate action

---

### 6. **Statistics**
**Endpoint:** `GET /api/stats`

**What it provides:**
- Overall system stats
- OI summaries
- Configuration

**Use Case:** Monitoring and debugging

---

## 🚀 **Implementation Status**

### ✅ **IMPLEMENTED** (Just Added):
1. ✅ `/api/trading-signal/{symbol}` - Ready-to-use trading signals
2. ✅ `/api/levels/{symbol}` - Support/resistance levels
3. ✅ `/api/sentiment/{symbol}` - Market sentiment

### 📋 **Available** (Already Exists):
4. ✅ `/api/heatmap/{symbol}` - All clusters
5. ✅ `/api/heatmap/{symbol}/best` - Best cluster
6. ✅ `/api/stats` - Statistics

---

## 💡 **Recommended Usage Flow**

### **For Simple Strategies:**
```
GET /api/trading-signal/{symbol}
  ↓
Use signal.direction, entry, stop_loss, take_profit
  ↓
Execute trade
```

### **For Advanced Strategies:**
```
GET /api/levels/{symbol}  → Support/Resistance
GET /api/sentiment/{symbol}  → Market bias
GET /api/heatmap/{symbol}  → Raw clusters
  ↓
Custom strategy logic
  ↓
Execute trade
```

---

## 📈 **Data Update Frequency**

- **Clusters:** Every 5 seconds
- **Prices:** Every 10 seconds  
- **OI Data:** Every 30 seconds
- **Signals:** Calculated on-demand (uses latest clusters)

**Recommendation:** Poll every 5-10 seconds for real-time trading

---

## 🎯 **Priority Ranking**

1. **Trading Signals** - Most useful, ready-to-use
2. **Support/Resistance** - Most common use case
3. **Market Sentiment** - Useful for bias
4. **Raw Clusters** - For custom analysis
5. **Best Cluster** - Quick reference
6. **Statistics** - Monitoring

---

## ✅ **Summary**

**Feed these through the API:**
- ✅ Trading signals (pre-computed)
- ✅ Support/resistance levels
- ✅ Market sentiment
- ✅ Raw cluster data (already exists)
- ✅ Best cluster (already exists)
- ✅ Statistics (already exists)

**All endpoints are now available and ready to use!** 🚀
