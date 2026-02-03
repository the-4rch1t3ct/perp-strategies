# Available Trading Data from Liquidation Heatmap

## 📊 Complete Data Inventory

### 1. **Liquidation Cluster Data** (Primary Trading Signals)

**What it is:** Predicted price levels where liquidations will occur, calculated BEFORE they happen.

**Data Fields:**
- `price_level` (float): Exact price where liquidations occur
- `side` (str): "long" or "short" - type of positions at risk
- `leverage_tier` (float): Average leverage (100x, 50x, 25x, 10x, 5x)
- `open_interest` (float): Total USD value of OI at risk
- `liquidation_count` (int): Estimated number of positions
- `strength` (float): Signal strength 0-1 (higher = stronger magnet)
- `distance_from_price` (float): % distance from current price
- `cluster_id` (int): Unique identifier
- `last_updated` (datetime): When cluster was last calculated

**Trading Uses:**
✅ Support/Resistance levels  
✅ Entry/Exit zones  
✅ Stop Loss placement  
✅ Take Profit targets  
✅ Liquidation cascade predictions  

---

### 2. **Cluster State Tracking**

**What it is:** Tracks whether clusters are active (intact) or broken (price moved through).

**Data Fields:**
- `active` (bool): True = cluster intact, False = broken
- `firstSeen` (datetime): When cluster first appeared
- `lastSeen` (datetime): Last update time

**Trading Uses:**
✅ Momentum signals (cluster breaks = continuation)  
✅ Reversal signals (price bounces off active clusters)  
✅ Liquidity tracking (broken = consumed)  

---

### 3. **Open Interest (OI) Data**

**What it is:** Total open interest and distribution across long/short positions.

**Data Fields:**
- `total_oi_usd` (float): Total OI in USD
- `long_oi_usd` (float): Long positions OI
- `short_oi_usd` (float): Short positions OI
- `long_short_ratio` (float): Ratio of longs to shorts

**Trading Uses:**
✅ Market sentiment analysis  
✅ Position sizing  
✅ Volatility prediction  
✅ Leverage risk assessment  

---

### 4. **Real-Time Price Data**

**What it is:** Current market price and historical OHLC candlestick data.

**Data Fields:**
- `current_price` (float): Latest market price
- `ohlc_data` (array): Historical candles with open, high, low, close, time

**Trading Uses:**
✅ Price action analysis  
✅ Trend confirmation  
✅ Entry timing  
✅ Technical analysis overlay  

---

## 🎯 Trading Strategy Data Applications

### Strategy 1: **Liquidation Hunt**

**Data Needed:**
- Strong clusters (strength ≥ 0.6)
- Distance from price (< 2%)
- Side (long/short)

**Signal Logic:**
```python
if cluster.strength >= 0.6 and cluster.distance_from_price < 2.0:
    if cluster.side == "short":
        # Enter LONG - expect short liquidations to push price up
        signal = "LONG"
        target = cluster.price_level
    elif cluster.side == "long":
        # Enter SHORT - expect long liquidations to push price down
        signal = "SHORT"
        target = cluster.price_level
```

**Expected Outcome:** Price moves towards cluster, triggering liquidations and momentum.

---

### Strategy 2: **Support/Resistance Trading**

**Data Needed:**
- Long clusters below price (support)
- Short clusters above price (resistance)
- Strength scores

**Signal Logic:**
```python
# Support = Long clusters below current price
support_levels = [c for c in clusters 
                  if c.side == "long" 
                  and c.price_level < current_price
                  and c.strength >= 0.5]

# Resistance = Short clusters above current price
resistance_levels = [c for c in clusters 
                     if c.side == "short" 
                     and c.price_level > current_price
                     and c.strength >= 0.5]

# Enter LONG near support
if current_price <= nearest_support.price_level * 1.01:
    signal = "LONG"
    
# Enter SHORT near resistance
if current_price >= nearest_resistance.price_level * 0.99:
    signal = "SHORT"
```

**Expected Outcome:** Price bounces off support/resistance levels.

---

### Strategy 3: **Cluster Breakout Trading**

**Data Needed:**
- Cluster state changes (active → broken)
- Price movement history

**Signal Logic:**
```python
# Monitor when clusters break
if cluster.active == False and cluster.lastSeen == recent:
    if cluster.side == "long":
        # Long liquidations triggered = price broke down
        signal = "SHORT"  # Continue down
    elif cluster.side == "short":
        # Short liquidations triggered = price broke up
        signal = "LONG"  # Continue up
```

**Expected Outcome:** Momentum continuation after cluster break.

---

### Strategy 4: **OI-Based Position Sizing**

**Data Needed:**
- Total OI
- OI per cluster
- Long/Short ratio

**Signal Logic:**
```python
# More OI = more liquidity = larger positions
if total_oi > 5000000000:  # $5B+
    position_size = base_size * 1.5
elif total_oi > 1000000000:  # $1B+
    position_size = base_size * 1.0
else:
    position_size = base_size * 0.5

# Adjust for bias
if long_short_ratio > 1.2:
    # More longs = favor short positions
    short_multiplier = 1.2
elif long_short_ratio < 0.8:
    # More shorts = favor long positions
    long_multiplier = 1.2
```

**Expected Outcome:** Optimized position sizing based on market conditions.

---

## 📡 API Endpoints Summary

### `/api/heatmap/{SYMBOL}`
**Returns:** All clusters with filters  
**Use:** Get all liquidation zones for analysis

### `/api/heatmap/{SYMBOL}/best`
**Returns:** Single strongest cluster  
**Use:** Quick signal for immediate action

### `/api/stats`
**Returns:** Overall statistics and OI data  
**Use:** Market sentiment and OI analysis

---

## 💡 Key Metrics for Decision Making

### Signal Strength (0-1)
- **0.7-1.0**: Very Strong - High confidence trades
- **0.5-0.7**: Strong - Good trading opportunities
- **0.3-0.5**: Moderate - Use with caution
- **0.0-0.3**: Weak - Filter out

### Distance from Price (%)
- **< 1%**: Immediate zone - Enter now
- **1-3%**: Near-term target - Plan entry
- **3-5%**: Medium-term level - Reference point
- **> 5%**: Long-term level - Monitor only

### Open Interest (USD)
- **> $10M**: Major level - Very significant
- **$2M-$10M**: High significance - Strong signal
- **$500k-$2M**: Moderate significance
- **< $500k**: Low significance - Filter out

### Leverage Tier
- **100x**: Very tight liquidation (1% move)
- **50x**: Tight liquidation (2% move)
- **25x**: Moderate liquidation (4% move)
- **10x-5x**: Wider liquidation (10-20% move)

---

## 🔄 Real-Time Updates

**Update Frequency:**
- Clusters: Every 5 seconds
- Prices: Every 10 seconds
- OI Data: Every 30 seconds
- Cluster States: Real-time (on price movement)

**For Strategy:**
- Poll API every 5-10 seconds
- Track cluster state changes
- React to breaks immediately
- Update positions based on new clusters

---

## 🎲 Example Trading Signal Output

```json
{
  "symbol": "BTCUSDT",
  "signal": "LONG",
  "entry_price": 89175.10,
  "stop_loss": 87386.99,
  "take_profit": 89874.15,
  "confidence": 0.85,
  "risk_reward": 2.5,
  "reason": "Strong short liquidation cluster at $89,427 (strength: 0.85, OI: $3.5M)",
  "cluster_data": {
    "price_level": 89427.01,
    "side": "short",
    "strength": 0.85,
    "open_interest": 3500000.0,
    "distance_from_price": 0.28
  },
  "support_levels": [88750.00, 88400.00],
  "resistance_levels": [89427.01, 89650.00],
  "market_sentiment": {
    "sentiment": "BULLISH_BIAS",
    "long_short_ratio": 1.15
  }
}
```

---

## 🚀 Integration Checklist

- [ ] Fetch clusters via API
- [ ] Filter by strength (≥ 0.5)
- [ ] Filter by distance (< 3%)
- [ ] Track cluster states
- [ ] Generate entry/exit signals
- [ ] Calculate stop loss/take profit
- [ ] Monitor cluster breaks
- [ ] Adjust position sizing based on OI
- [ ] Combine with technical analysis
- [ ] Backtest strategy

---

## 📝 Quick Reference

**Strong Signal Criteria:**
- Strength ≥ 0.6
- Distance < 2%
- OI ≥ $2M
- Active cluster (not broken)

**Entry Logic:**
- LONG: Price approaching short cluster (above)
- SHORT: Price approaching long cluster (below)

**Exit Logic:**
- Take Profit: At cluster level
- Stop Loss: Just beyond cluster (opposite side)

**Risk Management:**
- Never place stops at cluster levels
- Use cluster breaks as momentum signals
- Adjust size based on OI and strength

---

The liquidation heatmap provides **predictive** data showing where liquidations WILL occur BEFORE they happen, giving you a significant edge in trading decisions! 🎯
