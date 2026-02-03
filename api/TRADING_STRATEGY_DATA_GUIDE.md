# Trading Strategy Data Guide
## What Data Does the Liquidation Heatmap Generate?

The predictive liquidation heatmap generates rich, actionable data for trading strategies. Here's everything available and how to use it.

---

## 📊 Available Data Points

### 1. **Liquidation Clusters** (Primary Trading Signals)

Each cluster represents a price level where significant liquidations are predicted to occur.

**Data Structure:**
```json
{
  "price_level": 89175.50,        // Exact price where liquidations occur
  "side": "short",                 // "long" or "short" (position type at risk)
  "leverage_tier": 50.0,           // Average leverage (100x, 50x, 25x, etc.)
  "open_interest": 2500000.0,      // Total OI at risk (USD)
  "liquidation_count": 125000,    // Estimated number of positions
  "strength": 0.75,                // Signal strength (0-1, higher = stronger)
  "distance_from_price": 0.48,     // % distance from current price
  "cluster_id": 5,                 // Unique cluster identifier
  "last_updated": "2026-01-28T22:30:00"
}
```

**Trading Applications:**
- **Support/Resistance Levels**: Strong clusters act as price magnets
- **Entry Zones**: Enter positions near clusters for better risk/reward
- **Stop Loss Placement**: Avoid placing stops at cluster levels (high liquidation risk)
- **Take Profit Targets**: Use clusters as profit targets (price often reacts at these levels)

---

### 2. **Cluster States** (Active vs Broken)

Tracks whether clusters are still active or have been "broken" by price movement.

**States:**
- `active: true` - Cluster is still intact, price hasn't reached it yet
- `active: false` - Price has moved through the cluster (liquidity consumed)
- `firstSeen` - When cluster was first detected
- `lastSeen` - Last update time

**Trading Applications:**
- **Momentum Signals**: When price breaks through a strong cluster, expect continuation
- **Reversal Signals**: Price bouncing off active clusters suggests support/resistance
- **Liquidity Tracking**: Broken clusters = consumed liquidity (less likely to hold)

---

### 3. **Open Interest Distribution**

Shows how OI is distributed across leverage tiers and price levels.

**Data Available:**
- Total OI (USD)
- Long OI vs Short OI
- Long/Short Ratio
- OI per leverage tier

**Trading Applications:**
- **Market Sentiment**: High long OI = bullish bias, high short OI = bearish bias
- **Leverage Analysis**: More OI at higher leverage = higher volatility risk
- **Position Sizing**: Adjust size based on OI concentration

---

### 4. **Real-Time Price Data**

Current market price and historical OHLC candlestick data.

**Trading Applications:**
- **Price Action Analysis**: Combine with clusters for entry/exit timing
- **Trend Confirmation**: Price movement relative to clusters
- **Volatility Assessment**: Candle patterns near clusters

---

## 🔌 API Endpoints for Strategy Integration

### 1. **Get All Clusters for a Symbol**

```python
GET /api/heatmap/{SYMBOL}?min_strength=0.3&max_distance=5.0
```

**Response:**
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "clusters": [
    {
      "price_level": 89365.00,
      "side": "short",
      "strength": 0.85,
      "distance_from_price": 0.21,
      "total_notional": 3500000.0,
      "leverage_tier": 50.0
    }
  ],
  "total_clusters": 8
}
```

**Use Case:** Get all active liquidation zones for entry/exit planning.

---

### 2. **Get Best Trading Cluster**

```python
GET /api/heatmap/{SYMBOL}/best?min_strength=0.6
```

**Response:**
```json
{
  "price_level": 89365.00,
  "side": "short",
  "strength": 0.85,
  "distance_from_price": 0.21,
  "total_notional": 3500000.0,
  "leverage_tier": 50.0
}
```

**Use Case:** Find the strongest, most tradable cluster for immediate action.

---

### 3. **Get Statistics**

```python
GET /api/stats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_symbols": 27,
    "active_symbols": 15,
    "total_clusters": 45,
    "debug": {
      "open_interest_summary": {
        "BTCUSDT": {
          "total_oi_usd": 9067667699.67,
          "long_short_ratio": 0.91
        }
      }
    }
  }
}
```

**Use Case:** Monitor overall market conditions and OI distribution.

---

## 🎯 Trading Strategy Applications

### Strategy 1: **Liquidation Hunt (Momentum)**

**Concept:** Enter positions when price approaches strong liquidation clusters, expecting a "liquidation cascade."

**Data Needed:**
- Strong clusters (strength ≥ 0.6)
- Distance from price (< 2%)
- Side (long/short) to determine direction

**Logic:**
```python
# Pseudo-code
if cluster.strength >= 0.6 and cluster.distance_from_price < 2.0:
    if cluster.side == "short" and current_price >= cluster.price_level * 0.98:
        # Enter LONG - expect short liquidations to push price up
        entry_price = current_price
        stop_loss = cluster.price_level * 0.995  # Just below cluster
        take_profit = cluster.price_level * 1.02  # Above cluster
```

---

### Strategy 2: **Support/Resistance Trading**

**Concept:** Use clusters as support (long clusters below) and resistance (short clusters above).

**Data Needed:**
- Cluster price levels
- Strength scores
- Active status

**Logic:**
```python
# Find support (long clusters below price)
support_clusters = [c for c in clusters 
                   if c.side == "long" 
                   and c.price_level < current_price
                   and c.active
                   and c.strength >= 0.5]

# Find resistance (short clusters above price)
resistance_clusters = [c for c in clusters 
                      if c.side == "short" 
                      and c.price_level > current_price
                      and c.active
                      and c.strength >= 0.5]

# Enter LONG near support
if current_price <= min(support_clusters, key=lambda x: x.price_level).price_level * 1.01:
    # Price near support, enter long
    pass
```

---

### Strategy 3: **Cluster Breakout Trading**

**Concept:** Trade breakouts when price moves through strong clusters.

**Data Needed:**
- Cluster states (active → broken)
- Price movement history

**Logic:**
```python
# Monitor cluster breaks
for cluster in clusters:
    if cluster.active == False and cluster.lastSeen == recent:
        # Cluster just broken
        if cluster.side == "long":
            # Long liquidations triggered, price broke down
            # Enter SHORT or exit LONG positions
        elif cluster.side == "short":
            # Short liquidations triggered, price broke up
            # Enter LONG or exit SHORT positions
```

---

### Strategy 4: **OI-Based Position Sizing**

**Concept:** Adjust position size based on Open Interest concentration.

**Data Needed:**
- Total OI
- OI per cluster
- Long/Short ratio

**Logic:**
```python
# Calculate position size based on OI
total_oi = stats['open_interest_summary']['BTCUSDT']['total_oi_usd']
long_ratio = stats['open_interest_summary']['BTCUSDT']['long_short_ratio']

# More OI = more liquidity = can take larger positions
if total_oi > 5000000000:  # $5B+ OI
    position_multiplier = 1.5
elif total_oi > 1000000000:  # $1B+ OI
    position_multiplier = 1.0
else:
    position_multiplier = 0.5

# Adjust for long/short bias
if long_ratio > 1.2:  # More longs
    # Favor short positions (more longs to liquidate)
    short_bias = 1.2
elif long_ratio < 0.8:  # More shorts
    # Favor long positions
    long_bias = 1.2
```

---

## 📈 Integration with Your Trading Agent

### Example: Adding to `trading_agent.py`

```python
import httpx
from typing import List, Dict, Optional

class LiquidationStrategy:
    def __init__(self, api_base: str = "https://api.wagmi-global.eu"):
        self.api_base = api_base
    
    def get_trading_signals(self, symbol: str) -> Dict:
        """
        Get trading signals based on liquidation clusters
        """
        # Fetch clusters
        response = httpx.get(
            f"{self.api_base}/api/heatmap/{symbol}",
            params={
                "min_strength": 0.5,  # Only strong signals
                "max_distance": 3.0   # Within 3% of price
            }
        )
        data = response.json()
        
        if not data['success'] or not data['clusters']:
            return {"signal": "NEUTRAL", "reason": "No strong clusters"}
        
        current_price = data['current_price']
        clusters = data['clusters']
        
        # Find strongest nearby clusters
        long_clusters = [c for c in clusters 
                        if c['side'] == 'long' 
                        and c['price_level'] < current_price]
        short_clusters = [c for c in clusters 
                         if c['side'] == 'short' 
                         and c['price_level'] > current_price]
        
        # Determine signal
        if short_clusters:
            strongest_short = max(short_clusters, key=lambda x: x['strength'])
            if strongest_short['distance_from_price'] < 1.0:
                return {
                    "signal": "LONG",
                    "entry": current_price,
                    "stop_loss": strongest_short['price_level'] * 0.998,
                    "take_profit": strongest_short['price_level'] * 1.01,
                    "confidence": strongest_short['strength'],
                    "reason": f"Strong short liquidation cluster at ${strongest_short['price_level']:.2f}"
                }
        
        if long_clusters:
            strongest_long = max(long_clusters, key=lambda x: x['strength'])
            if strongest_long['distance_from_price'] < 1.0:
                return {
                    "signal": "SHORT",
                    "entry": current_price,
                    "stop_loss": strongest_long['price_level'] * 1.002,
                    "take_profit": strongest_long['price_level'] * 0.99,
                    "confidence": strongest_long['strength'],
                    "reason": f"Strong long liquidation cluster at ${strongest_long['price_level']:.2f}"
                }
        
        return {"signal": "NEUTRAL", "reason": "No immediate opportunities"}
    
    def get_support_resistance_levels(self, symbol: str) -> Dict:
        """
        Get key support and resistance levels from clusters
        """
        response = httpx.get(
            f"{self.api_base}/api/heatmap/{symbol}",
            params={"min_strength": 0.4, "max_distance": 10.0}
        )
        data = response.json()
        
        current_price = data['current_price']
        clusters = data['clusters']
        
        # Support levels (long clusters below price)
        support = sorted(
            [c for c in clusters if c['side'] == 'long' and c['price_level'] < current_price],
            key=lambda x: x['price_level'],
            reverse=True
        )[:3]  # Top 3 support levels
        
        # Resistance levels (short clusters above price)
        resistance = sorted(
            [c for c in clusters if c['side'] == 'short' and c['price_level'] > current_price],
            key=lambda x: x['price_level']
        )[:3]  # Top 3 resistance levels
        
        return {
            "support": [c['price_level'] for c in support],
            "resistance": [c['price_level'] for c in resistance],
            "current_price": current_price
        }
```

---

## 🎲 Signal Quality Metrics

### Strength Score (0-1)
- **0.0-0.3**: Weak signal (filter out)
- **0.3-0.5**: Moderate signal (use with caution)
- **0.5-0.7**: Strong signal (good for trading)
- **0.7-1.0**: Very strong signal (high confidence)

### Distance from Price
- **< 1%**: Immediate risk/reward zone
- **1-3%**: Near-term target
- **3-5%**: Medium-term level
- **> 5%**: Long-term reference

### Open Interest (USD)
- **< $500k**: Low significance
- **$500k-$2M**: Moderate significance
- **$2M-$10M**: High significance
- **> $10M**: Very high significance (major level)

---

## 🔄 Real-Time Data Updates

The heatmap updates every 5 seconds with:
- New cluster calculations
- Price updates
- Cluster state changes (active → broken)
- OI updates (every 30 seconds)

**For Strategy:**
- Poll `/api/heatmap/{SYMBOL}` every 5-10 seconds
- Track cluster state changes
- React to cluster breaks in real-time

---

## 💡 Recommended Strategy Workflow

1. **Monitor Clusters**: Continuously fetch clusters for your trading symbols
2. **Filter Quality**: Only use clusters with strength ≥ 0.5 and distance < 3%
3. **Track State**: Monitor when clusters become active/broken
4. **Enter Positions**: When price approaches strong clusters
5. **Set Stops**: Place stops just beyond cluster levels
6. **Take Profits**: Use clusters as profit targets
7. **Exit on Break**: Close positions when clusters break (liquidity consumed)

---

## 📝 Example: Complete Trading Signal

```python
{
  "symbol": "BTCUSDT",
  "current_price": 89175.10,
  "signal": "LONG",
  "entry_price": 89175.10,
  "stop_loss": 88750.00,      // Below nearest long cluster
  "take_profit": 89365.00,    // At strong short cluster
  "risk_reward": 2.5,         // 2.5:1 ratio
  "confidence": 0.75,         // Based on cluster strength
  "reason": "Strong short liquidation cluster at $89,365 (strength: 0.85, OI: $3.5M)",
  "clusters": {
    "support": [88750.00, 88400.00],
    "resistance": [89365.00, 89650.00]
  },
  "oi_data": {
    "total_oi_usd": 9067667699.67,
    "long_short_ratio": 0.91
  }
}
```

---

## 🚀 Next Steps

1. **Integrate API calls** into your trading agent
2. **Build signal filters** based on your risk tolerance
3. **Backtest strategies** using historical cluster data
4. **Monitor cluster breaks** for momentum signals
5. **Combine with technical analysis** for confirmation

The liquidation heatmap provides **predictive** data - it shows where liquidations WILL occur BEFORE they happen, giving you a significant edge in trading decisions.
