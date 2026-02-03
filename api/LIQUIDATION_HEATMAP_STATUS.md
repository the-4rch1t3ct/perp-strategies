# Liquidation Heatmap Status & Explanation

## Current Status ✅

**The UI is working correctly!** The system is:
- ✅ Connected to Binance WebSocket liquidation stream
- ✅ Collecting real-time liquidation data
- ✅ Processing and clustering liquidation events
- ✅ Serving the interactive heatmap UI

## Why You're Not Seeing Clusters Yet

### 1. **Liquidations Are Rare Events**
Liquidations don't happen constantly - they occur when:
- Price moves significantly against leveraged positions
- Margin requirements are breached
- Stop-loss levels are hit

**The system needs time to accumulate liquidation events** before clusters can form.

### 2. **Cluster Formation Requirements**
The system requires:
- **Minimum 3 liquidations** within a **5% price window** (recently lowered from 5 liquidations in 2% window)
- Liquidations must occur within **120 minutes** of each other (with time decay weighting)

### 3. **Current Configuration**
- `min_cluster_size`: **3** (lowered to show clusters sooner)
- `cluster_window_pct`: **5%** (increased from 2% to capture more liquidations)
- `time_decay_minutes`: **120** (increased from 60 to include more historical data)

## What the System Is Doing Right Now

1. **WebSocket Connection**: Connected to Binance Futures liquidation stream for 27 symbols
2. **Data Collection**: Buffering liquidation events as they occur
3. **Price Updates**: Fetching current prices every 10 seconds
4. **Cluster Building**: Every 5 seconds, analyzing recent liquidations to form clusters

## When Will Clusters Appear?

Clusters will appear when:
- **At least 3 liquidations** occur at similar price levels (within 5%)
- These liquidations happen within the **last 2 hours**
- The cluster strength meets the **minimum threshold** (default: 0.0, meaning any cluster will show)

## Visual Representation

Once clusters form, you'll see:
- **Bright yellow/orange bands** = Dense liquidation clusters (high leverage risk zones)
- **Red bands** = Long liquidation clusters (price support levels)
- **Green bands** = Short liquidation clusters (price resistance levels)
- **Current price line** = White vertical line showing current market price

These clusters act as **"magnet zones"** where price may:
- Reverse direction (support/resistance)
- Experience violent moves (liquidation cascades)
- Find temporary equilibrium

## How to Verify It's Working

1. **Check Stats**: Visit `https://api.wagmi-global.eu/api/stats` to see:
   - Total liquidations in buffer
   - Recent liquidations per symbol
   - Stream connection status

2. **Wait for Market Volatility**: Clusters appear faster during:
   - High volatility periods
   - Major price movements
   - Market corrections or pumps

3. **Lower Filters**: In the UI, try:
   - **Min Strength**: Set to `0` (show all clusters)
   - **Max Distance**: Set to `20%` (show clusters further from price)

## Technical Details

- **Data Source**: Binance Futures WebSocket (`wss://fstream.binance.com`)
- **Stream Type**: Force Order Stream (`@forceOrder`)
- **Update Frequency**: 1000ms (Binance pushes latest liquidation per symbol per second)
- **Processing**: Hierarchical clustering with time decay weighting

## Next Steps

The system is correctly implemented and working. **Clusters will appear automatically** as liquidation events accumulate. During quiet market periods, you may see few or no clusters, which is normal.

To see clusters sooner:
1. Wait for market volatility
2. Monitor during major price movements
3. Check back periodically - clusters accumulate over time

The heatmap is **live and operational** - it's just waiting for the market to provide liquidation data! 🔥
