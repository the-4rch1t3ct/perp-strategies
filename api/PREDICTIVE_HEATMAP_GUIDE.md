# Predictive Liquidation Heatmap - Complete Guide

## 🎯 What Changed

**From Post-Mortem to Predictive:**
- **OLD**: Waited for liquidation events to occur, then clustered them
- **NEW**: Calculates liquidation risk zones BEFORE liquidations happen

## 🔥 How It Works

### Core Logic

1. **Open Interest Data**: Fetches total OI and Long/Short ratio from Binance
2. **Liquidation Price Calculation**: For each leverage tier, calculates where liquidations would occur:
   - **Long liquidation**: `L = P × (1 - 1/Leverage)` (below current price)
   - **Short liquidation**: `L = P × (1 + 1/Leverage)` (above current price)
3. **OI Distribution**: Estimates OI distribution across leverage tiers using order book depth
4. **Clustering**: Groups nearby liquidation levels into price buckets (0.1% windows)
5. **Heat Intensity**: Maps OI volume to visual intensity (brighter = more risk)

### Leverage Tiers

Default tiers: `[100x, 50x, 25x, 10x, 5x]`

- **100x leverage**: Liquidates at ±1% from entry
- **50x leverage**: Liquidates at ±2% from entry  
- **25x leverage**: Liquidates at ±4% from entry
- **10x leverage**: Liquidates at ±10% from entry
- **5x leverage**: Liquidates at ±20% from entry

### Data Sources

1. **Binance Futures API**:
   - `/fapi/v1/openInterest` - Total OI
   - `/fapi/v1/depth` - Order book for position distribution
   - `/fapi/v1/ticker/price` - Current prices

2. **Order Book Analysis**:
   - Uses bid/ask depth to estimate Long/Short ratio
   - Distributes OI across leverage tiers

## 📊 What You See

### Heat Zones

- **Bright Yellow/Orange**: High OI concentration = Strong magnet zones
- **Red Bands**: Long liquidation clusters (potential support)
- **Green Bands**: Short liquidation clusters (potential resistance)
- **Current Price**: White vertical line

### Key Metrics

- **Total Clusters**: Number of risk zones identified
- **Long Clusters**: Support levels (long liquidations below price)
- **Short Clusters**: Resistance levels (short liquidations above price)
- **Current Price**: Real-time market price

## ⚙️ Configuration

### Parameters

- `leverage_tiers`: `[100, 50, 25, 10, 5]` - Leverage levels to calculate
- `price_bucket_pct`: `0.001` (0.1%) - Price bucket size for clustering
- `min_oi_threshold`: `50000` ($50k USD) - Minimum OI to display
- `update_interval`: `5.0` seconds - How often to recalculate

### Adjusting Sensitivity

**Show More Clusters:**
- Lower `min_oi_threshold` (e.g., 10000)
- Increase `max_distance` filter in UI (e.g., 20%)

**Show Stronger Clusters Only:**
- Increase `min_strength` filter in UI (e.g., 0.5)
- Keep `min_oi_threshold` higher

## 🚀 API Endpoints

### Get Heatmap Data
```
GET /api/heatmap/{SYMBOL}?min_strength=0.0&max_distance=10.0
```

**Response:**
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "current_price": 89431.6,
  "clusters": [
    {
      "price_level": 88545.2,
      "side": "long",
      "leverage_tier": 50.0,
      "open_interest": 5000000.0,
      "strength": 0.75,
      "distance_from_price": 0.99
    }
  ],
  "total_clusters": 12
}
```

### Get Statistics
```
GET /api/stats
```

Shows:
- Total symbols tracked
- Active symbols with clusters
- Open Interest summary
- Configuration

## 🎨 UI Features

1. **Symbol Search**: Search and select any supported symbol
2. **Filters**:
   - **Min Strength**: Minimum cluster intensity (0-1)
   - **Max Distance**: Maximum % from current price
3. **Auto Refresh**: Updates every 5 seconds
4. **Interactive Heatmap**: Click clusters for details

## 📈 Real-Time Updates

- **Prices**: Updated every 10 seconds
- **Open Interest**: Updated every 30 seconds
- **Liquidation Levels**: Recalculated every 5 seconds
- **Heatmap**: Moves dynamically as price changes

## 🔍 Understanding the Heatmap

### What Makes a Zone "Hot"?

1. **High Open Interest**: More positions = more potential liquidations
2. **High Leverage**: Positions closer to liquidation price
3. **Concentration**: Many positions at similar price levels

### Why These Zones Matter

- **Support/Resistance**: Price often reacts at these levels
- **Liquidation Cascades**: One liquidation can trigger others
- **Market Reversals**: Strong clusters can cause price bounces
- **Volatility Spikes**: High concentration = potential for violent moves

## 🛠️ Technical Details

### Formula Reference

**Long Liquidation Price:**
```
L_long = P_current × (1 - 1/Leverage)
```

**Short Liquidation Price:**
```
L_short = P_current × (1 + 1/Leverage)
```

**Example (BTC at $90,000, 50x leverage):**
- Long liquidates at: $90,000 × (1 - 1/50) = $88,200 (-2%)
- Short liquidates at: $90,000 × (1 + 1/50) = $91,800 (+2%)

### Clustering Algorithm

1. Calculate liquidation levels for all leverage tiers
2. Group levels within 0.1% price buckets
3. Aggregate OI within each bucket
4. Calculate weighted average price
5. Determine dominant side (long/short)
6. Normalize strength (0-1 scale)

## ✅ Status

**Current Status**: ✅ **OPERATIONAL**

- API running on port 8004
- Predictive heatmap active
- Real-time OI data fetching
- Liquidation levels calculated
- UI accessible at `https://api.wagmi-global.eu/liquidation-heatmap/`

## 🎯 Next Steps

The predictive heatmap is now live and showing risk zones BEFORE liquidations occur. You should see heat zones appearing immediately (no waiting for liquidation events).

**To verify it's working:**
1. Open the UI
2. Select a symbol (e.g., BTCUSDT)
3. You should see colored bands above and below the current price
4. These represent predicted liquidation zones

The system is now **predictive** rather than **reactive**! 🔥
