# Ideal Timeframe for Trading Liquidation Clusters

## 🎯 **Quick Answer**

**Best Timeframes:**
- **1-minute to 5-minute charts** for active cluster hunting
- **15-minute to 1-hour charts** for support/resistance trading
- **Real-time monitoring** for cluster breakouts

---

## 📊 **Cluster Characteristics**

### Leverage Tiers & Liquidation Distances:

| Leverage | Liquidation Distance | Typical Timeframe |
|----------|---------------------|-------------------|
| **100x** | ~1% move | **1-5 minutes** (very fast) |
| **50x** | ~2% move | **5-15 minutes** (fast) |
| **25x** | ~4% move | **15 minutes - 1 hour** (moderate) |
| **10x** | ~10% move | **1-4 hours** (slower) |
| **5x** | ~20% move | **4+ hours** (slow) |

### Cluster Distance from Price:

- **< 1% distance**: Immediate risk zone - **1-5 minute timeframe**
- **1-3% distance**: Near-term target - **5-30 minute timeframe**
- **3-5% distance**: Medium-term level - **30 minutes - 2 hours**
- **> 5% distance**: Long-term reference - **2+ hours**

---

## ⏱️ **Recommended Timeframes by Strategy**

### Strategy 1: **Liquidation Hunt (Momentum)**

**Timeframe: 1-minute to 5-minute charts**

**Why:**
- Clusters within 1-2% of price can trigger liquidations quickly
- High leverage clusters (50x-100x) react within minutes
- Need fast execution to catch liquidation cascades
- Price moves toward clusters rapidly in volatile conditions

**Example:**
```
Cluster at $89,427 (short, 50x leverage, 0.3% away)
Current price: $89,160
Expected time to reach: 5-15 minutes
→ Use 1m or 5m chart for entry timing
```

---

### Strategy 2: **Support/Resistance Trading**

**Timeframe: 15-minute to 1-hour charts**

**Why:**
- Support/resistance levels are more stable
- Multiple leverage tiers create broader zones
- Price bounces/rejections take time to develop
- Less noise than 1-minute charts

**Example:**
```
Support cluster at $88,750 (long, multiple tiers)
Current price: $89,175 (0.48% above support)
Expected bounce: 15-60 minutes
→ Use 15m or 1h chart for confirmation
```

---

### Strategy 3: **Cluster Breakout Trading**

**Timeframe: 5-minute to 15-minute charts**

**Why:**
- Need to catch momentum immediately after break
- Cluster breaks happen quickly (seconds to minutes)
- Fast timeframe needed to enter before move completes
- Real-time monitoring + 5m chart for confirmation

**Example:**
```
Price breaks through $89,427 cluster
Momentum continues for 5-30 minutes
→ Use 5m chart to catch continuation move
```

---

## 🔄 **Dynamic Timeframe Selection**

### Based on Cluster Distance:

```python
def get_ideal_timeframe(distance_pct: float, leverage_tier: float) -> str:
    """
    Determine ideal timeframe based on cluster characteristics
    """
    # High leverage + close = very fast
    if leverage_tier >= 50 and distance_pct < 1.0:
        return "1m"  # 1-minute chart
    
    # Medium leverage + close = fast
    elif leverage_tier >= 25 and distance_pct < 2.0:
        return "5m"  # 5-minute chart
    
    # Any leverage + medium distance = moderate
    elif distance_pct < 3.0:
        return "15m"  # 15-minute chart
    
    # Wider distance = longer timeframe
    elif distance_pct < 5.0:
        return "1h"  # 1-hour chart
    
    else:
        return "4h"  # 4-hour chart for reference levels
```

---

## 📈 **Market Volatility Impact**

### High Volatility Markets:
- **Timeframe: 1m - 5m**
- Clusters reached faster
- More frequent signals
- Quick entries/exits needed

### Low Volatility Markets:
- **Timeframe: 15m - 1h**
- Clusters take longer to reach
- Fewer but stronger signals
- More time to plan entries

---

## 🎯 **Practical Recommendations**

### For Active Trading (Liquidation Hunt):

**Primary Timeframe: 5-minute chart**
- Good balance of speed and signal quality
- Catches most liquidation cascades
- Less noise than 1-minute

**Confirmation Timeframe: 15-minute chart**
- Use for trend confirmation
- Filter out false signals
- Better risk/reward assessment

### For Swing Trading (Support/Resistance):

**Primary Timeframe: 1-hour chart**
- Stronger support/resistance levels
- Better risk/reward ratios
- Less frequent but higher quality signals

**Entry Timeframe: 15-minute chart**
- Fine-tune entry timing
- Catch bounces/rejections
- Manage position size

### For Scalping (Cluster Breakouts):

**Primary Timeframe: 1-minute chart**
- Catch immediate momentum
- Fast entries/exits
- High frequency trading

**Confirmation: Real-time price action**
- Monitor cluster breaks live
- Use WebSocket price updates
- React within seconds

---

## ⚡ **Real-Time Monitoring**

**Update Frequency:**
- **Clusters update every 5 seconds**
- **Prices update every 10 seconds**
- **OI updates every 30 seconds**

**Ideal Setup:**
1. **Monitor clusters in real-time** (WebSocket or 5-second polling)
2. **Use 1m-5m chart** for active signals
3. **Use 15m-1h chart** for confirmation
4. **React quickly** when price approaches clusters (< 1% away)

---

## 📊 **Timeframe Decision Matrix**

| Cluster Distance | Leverage Tier | Volatility | Ideal Timeframe |
|-----------------|---------------|------------|-----------------|
| < 1% | 50x-100x | High | **1m** |
| < 1% | 25x-50x | High | **5m** |
| 1-2% | 50x-100x | Medium | **5m** |
| 1-2% | 25x-50x | Medium | **15m** |
| 2-3% | Any | Low | **15m-1h** |
| 3-5% | Any | Any | **1h-4h** |
| > 5% | Any | Any | **4h+** (reference) |

---

## 💡 **Best Practices**

1. **Start with 5-minute chart** - Good default for most strategies
2. **Use 1-minute for entries** - Fine-tune timing near clusters
3. **Use 15-minute for confirmation** - Filter signals
4. **Monitor real-time** - Clusters update every 5 seconds
5. **Adjust based on volatility** - Faster markets = shorter timeframes

---

## 🎯 **Recommended Setup**

### For Liquidation Hunt Strategy:
```
Primary Chart: 5-minute
Entry Chart: 1-minute (when price < 1% from cluster)
Confirmation: 15-minute (trend filter)
Monitoring: Real-time (5-second updates)
```

### For Support/Resistance Strategy:
```
Primary Chart: 1-hour
Entry Chart: 15-minute
Confirmation: 4-hour (trend context)
Monitoring: Every 30 seconds
```

### For Cluster Breakout Strategy:
```
Primary Chart: 1-minute
Entry: Real-time (immediate on break)
Confirmation: 5-minute (momentum check)
Monitoring: Real-time (WebSocket)
```

---

## ✅ **Summary**

**Most Versatile Timeframe: 5-minute chart**
- Catches liquidation cascades
- Good signal quality
- Manageable trade frequency
- Works for most cluster distances

**For Maximum Speed: 1-minute chart**
- Fastest entries
- Catch immediate moves
- Higher frequency
- More noise (use filters)

**For Quality Signals: 15-minute to 1-hour**
- Stronger levels
- Better risk/reward
- Fewer but better trades
- Less stress

**Key Insight:** The ideal timeframe depends on:
1. **Cluster distance** from current price
2. **Leverage tier** (higher = faster)
3. **Market volatility** (high = shorter timeframes)
4. **Your trading style** (scalping vs swing)

Start with **5-minute charts** and adjust based on your results! 🎯
