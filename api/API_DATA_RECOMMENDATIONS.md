# API Data Recommendations for Trading Strategies

## 🎯 Current API Endpoints

### ✅ Already Exposed:
1. **`/api/heatmap/{symbol}`** - Clusters with filters
2. **`/api/heatmap/{symbol}/best`** - Single strongest cluster
3. **`/api/stats`** - Overall statistics

---

## 📊 Recommended API Enhancements

### 1. **Trading Signal Endpoint** (HIGH PRIORITY)
**Endpoint:** `GET /api/trading-signal/{symbol}`

**Purpose:** Pre-computed trading signals ready for strategy use

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "signal": {
    "direction": "LONG",
    "entry_price": 89175.10,
    "stop_loss": 87386.99,
    "take_profit": 89874.15,
    "confidence": 0.85,
    "risk_reward": 2.5,
    "reason": "Strong short liquidation cluster at $89,427"
  },
  "cluster_data": {
    "price_level": 89427.01,
    "side": "short",
    "strength": 0.85,
    "distance_from_price": 0.28
  },
  "timestamp": "2026-01-28T22:30:00"
}
```

**Why:** Saves strategy code from re-implementing signal logic

---

### 2. **Support/Resistance Levels** (HIGH PRIORITY)
**Endpoint:** `GET /api/levels/{symbol}`

**Purpose:** Separated support (long clusters below) and resistance (short clusters above)

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "support": [
    {
      "price": 88750.00,
      "strength": 0.75,
      "oi_usd": 2500000.0,
      "distance_pct": 0.48
    }
  ],
  "resistance": [
    {
      "price": 89427.01,
      "strength": 0.85,
      "oi_usd": 3500000.0,
      "distance_pct": 0.28
    }
  ]
}
```

**Why:** Most common trading use case - key levels

---

### 3. **Market Sentiment** (MEDIUM PRIORITY)
**Endpoint:** `GET /api/sentiment/{symbol}`

**Purpose:** OI-based market sentiment analysis

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "sentiment": "BULLISH_BIAS",
  "long_short_ratio": 1.15,
  "total_oi_usd": 9067667699.67,
  "long_oi_usd": 4850000000.0,
  "short_oi_usd": 4217667699.67,
  "interpretation": "More long positions - Short liquidations more likely on price rise",
  "bias_strength": "MODERATE"
}
```

**Why:** Helps with position sizing and direction bias

---

### 4. **Cluster State Tracking** (MEDIUM PRIORITY)
**Endpoint:** `GET /api/cluster-states/{symbol}`

**Purpose:** Track which clusters are active vs broken

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "clusters": [
    {
      "cluster_id": 1,
      "price_level": 89427.01,
      "side": "short",
      "active": true,
      "first_seen": "2026-01-28T22:00:00",
      "last_seen": "2026-01-28T22:30:00",
      "strength": 0.85
    },
    {
      "cluster_id": 2,
      "price_level": 88750.00,
      "side": "long",
      "active": false,
      "first_seen": "2026-01-28T21:45:00",
      "last_seen": "2026-01-28T22:15:00",
      "broken_at": "2026-01-28T22:15:00",
      "strength": 0.75
    }
  ]
}
```

**Why:** Momentum signals - broken clusters = liquidity consumed

---

### 5. **Risk Metrics** (LOW PRIORITY)
**Endpoint:** `GET /api/risk/{symbol}`

**Purpose:** Risk assessment for position sizing

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "risk_metrics": {
    "nearest_long_liquidation_pct": 0.48,
    "nearest_short_liquidation_pct": 0.28,
    "total_oi_at_risk_usd": 6000000.0,
    "max_leverage_tier": 100,
    "volatility_estimate": "HIGH",
    "recommended_max_position_size_usd": 50000.0
  }
}
```

**Why:** Automated risk management

---

### 6. **Multi-Symbol Batch** (MEDIUM PRIORITY)
**Endpoint:** `POST /api/batch-signals`

**Purpose:** Get signals for multiple symbols at once

**Request:**
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "min_strength": 0.6,
  "max_distance": 3.0
}
```

**Response:**
```json
{
  "signals": [
    {
      "symbol": "BTCUSDT",
      "signal": "LONG",
      "confidence": 0.85
    }
  ]
}
```

**Why:** Efficient for multi-symbol strategies

---

## 🎯 Priority Ranking

### **MUST HAVE** (Implement First):
1. ✅ **Trading Signal Endpoint** - Core functionality
2. ✅ **Support/Resistance Levels** - Most common use case

### **SHOULD HAVE** (Implement Next):
3. ✅ **Market Sentiment** - Useful for bias
4. ✅ **Multi-Symbol Batch** - Efficiency for multi-coin strategies

### **NICE TO HAVE** (Optional):
5. ✅ **Cluster State Tracking** - Advanced momentum signals
6. ✅ **Risk Metrics** - Automated risk management

---

## 📝 Recommended Data Structure Changes

### Enhance Current `/api/heatmap/{symbol}` Response:

**Add to ClusterData:**
- `active` (bool) - Is cluster still intact?
- `first_seen` (datetime) - When cluster first appeared
- `broken_at` (optional datetime) - When price moved through

**Add to HeatmapResponse:**
- `support_levels` (array) - Pre-filtered long clusters below
- `resistance_levels` (array) - Pre-filtered short clusters above
- `market_sentiment` (object) - OI-based sentiment
- `risk_metrics` (object) - Risk assessment

---

## 🔄 Data Update Frequency

**Current:**
- Clusters: Every 5 seconds
- Prices: Every 10 seconds
- OI: Every 30 seconds

**Recommended:**
- Keep same frequency
- Add `last_updated` timestamp to all responses
- Add `cache_ttl` header for client-side caching

---

## 💡 Implementation Priority

**Phase 1 (Essential):**
1. Trading Signal endpoint
2. Support/Resistance endpoint
3. Enhanced cluster data (active/broken states)

**Phase 2 (Useful):**
4. Market Sentiment endpoint
5. Multi-symbol batch endpoint

**Phase 3 (Advanced):**
6. Risk Metrics endpoint
7. Historical cluster tracking

---

## 🚀 Quick Wins

**Easiest to implement (use existing data):**
- Support/Resistance endpoint (just filter existing clusters)
- Market Sentiment endpoint (use existing OI data)
- Enhanced cluster states (add active/broken tracking)

**Requires new logic:**
- Trading Signal endpoint (needs signal generation logic)
- Risk Metrics endpoint (needs risk calculation)

---

## 📊 Data Flow for Trading Strategy

```
Trading Agent
    ↓
GET /api/trading-signal/{symbol}
    ↓
{
  signal: "LONG",
  entry: 89175.10,
  stop_loss: 87386.99,
  take_profit: 89874.15,
  confidence: 0.85
}
    ↓
Execute Trade
```

**OR**

```
Trading Agent
    ↓
GET /api/levels/{symbol}
    ↓
{
  support: [88750.00, 88400.00],
  resistance: [89427.01, 89650.00]
}
    ↓
Custom Strategy Logic
    ↓
Execute Trade
```

---

## ✅ Recommendation

**Start with these 3 endpoints:**
1. `/api/trading-signal/{symbol}` - Ready-to-use signals
2. `/api/levels/{symbol}` - Support/resistance
3. Enhanced `/api/heatmap/{symbol}` - Add `active` field to clusters

This gives strategies everything they need while keeping API simple.
