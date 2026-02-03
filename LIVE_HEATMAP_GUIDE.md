# Live Liquidation Heatmap Guide

## 🎯 Overview

Build your own **real-time liquidation cluster heatmap** using Binance WebSocket streams - **100% FREE**!

No API keys needed, no monthly fees, just real-time liquidation data from Binance.

---

## ✅ What You Get

- ✅ **Real-time liquidation stream** from Binance WebSocket
- ✅ **Live cluster building** (updates every 5 seconds)
- ✅ **Time-weighted clustering** (recent liquidations weighted more)
- ✅ **Same format as expensive heatmap models**
- ✅ **Works with liquidation hunter**
- ✅ **100% free** (no API keys needed)

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
pip install websocket-client pandas numpy scipy
```

### Step 2: Basic Usage

```python
from live_liquidation_heatmap import LiveLiquidationHeatmap
import time

# Initialize heatmap
heatmap = LiveLiquidationHeatmap(
    cluster_window_pct=0.02,  # 2% clustering window
    min_cluster_size=5,  # Minimum 5 liquidations per cluster
    time_decay_minutes=60,  # 60-minute time decay
    update_interval=5.0  # Update every 5 seconds
)

# Start stream for symbols
symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
heatmap.start_stream(symbols=symbols)

# Set current prices (fetch from Binance API)
heatmap.update_price('BTCUSDT', 90000.0)
heatmap.update_price('ETHUSDT', 3000.0)

# Get clusters
clusters = heatmap.get_clusters('BTCUSDT')

for cluster in clusters:
    print(f"{cluster.side.upper()} @ ${cluster.price_level:,.2f}")
    print(f"  Strength: {cluster.strength:.2f}")
    print(f"  Count: {cluster.liquidation_count}")
```

### Step 3: Integration with Liquidation Hunter

```python
from liquidation_hunter import LiquidationHunter

hunter = LiquidationHunter()

# Use live Binance heatmap
hunter.set_data_source(
    source='live_binance',
    symbols=['BTCUSDT', 'ETHUSDT']  # Symbols to monitor
)

# Generate signals (uses live clusters)
signal, strength, cluster = hunter.generate_signal('BTC/USDT:USDT', 90000.0)
```

---

## 📊 How It Works

### 1. WebSocket Connection

Connects to Binance liquidation stream:
- **Single symbol**: `wss://fstream.binance.com/ws/btcusdt@forceOrder`
- **Multiple symbols**: `wss://fstream.binance.com/stream?streams=btcusdt@forceOrder/ethusdt@forceOrder`
- **All symbols**: `wss://fstream.binance.com/ws/!forceOrder@arr`

### 2. Real-Time Processing

- Receives liquidation events every second (if any occur)
- Buffers last 10,000 liquidations
- Updates clusters every 5 seconds (configurable)

### 3. Cluster Building

- Groups liquidations by price (2% windows)
- Weights by time (recent = higher weight)
- Calculates strength (count + notional)
- Identifies dominant side (long vs short)

### 4. Time Decay

Recent liquidations weighted more heavily:
```
weight = exp(-age_minutes / 60)
```

Liquidations from 1 hour ago have ~37% weight  
Liquidations from 30 minutes ago have ~61% weight  
Liquidations from 5 minutes ago have ~92% weight

---

## 🔧 Configuration

### Cluster Parameters

```python
heatmap = LiveLiquidationHeatmap(
    cluster_window_pct=0.02,  # Price window for clustering (2%)
    min_cluster_size=5,  # Minimum liquidations per cluster
    time_decay_minutes=60,  # Time decay period
    update_interval=5.0  # Seconds between updates
)
```

### Symbol Format

- **Input**: `'BTCUSDT'` (no slashes)
- **Hunter format**: `'BTC/USDT:USDT'` (automatically converted)

---

## 📈 Performance

### Update Frequency

- **WebSocket**: Real-time (1 second updates)
- **Cluster updates**: Every 5 seconds (configurable)
- **Buffer size**: Last 10,000 liquidations

### Memory Usage

- ~1-2 MB per symbol (depends on liquidation frequency)
- Scales linearly with number of symbols

### CPU Usage

- Minimal (clustering is fast)
- Updates are non-blocking

---

## 🎯 Use Cases

### 1. Real-Time Trading

```python
# Get best cluster for trading
best_cluster = heatmap.get_best_cluster('BTCUSDT', min_strength=0.6)

if best_cluster:
    if best_cluster.side == 'long' and current_price > best_cluster.price_level:
        # Short toward long liquidations
        enter_short(best_cluster.price_level)
```

### 2. Monitoring Multiple Symbols

```python
symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
heatmap.start_stream(symbols=symbols)

# Monitor all
for symbol in symbols:
    clusters = heatmap.get_clusters(symbol)
    print(f"{symbol}: {len(clusters)} clusters")
```

### 3. Integration with Trading Bot

```python
hunter = LiquidationHunter()
hunter.set_data_source(source='live_binance', symbols=['BTCUSDT'])

# In your trading loop
while True:
    current_price = get_current_price('BTCUSDT')
    signal, strength, cluster = hunter.generate_signal('BTC/USDT:USDT', current_price)
    
    if signal != 0 and strength > 0.7:
        execute_trade(signal, cluster)
    
    time.sleep(5)
```

---

## 🔍 Cluster Properties

Each cluster has:

- `price_level`: Weighted average price
- `side`: 'long' or 'short' (which side gets liquidated)
- `liquidation_count`: Number of liquidations in cluster
- `total_notional`: Total USD value
- `strength`: 0-1 (cluster strength score)
- `distance_from_price`: Distance from current price (%)
- `last_updated`: Timestamp of last update

---

## ⚠️ Limitations

1. **Binance Only**: Only Binance futures data (not other exchanges)
2. **1 Second Updates**: Binance sends max 1 liquidation per second per symbol
3. **No Historical Data**: Only real-time (no past liquidations)
4. **WebSocket Reliability**: May need reconnection logic

---

## 🛠️ Troubleshooting

### No Clusters Appearing

**Check**:
1. Are liquidations occurring? (check Binance website)
2. Is WebSocket connected? (check console output)
3. Is `min_cluster_size` too high? (try lowering to 3)

### Clusters Not Updating

**Check**:
1. Is `update_interval` too long? (try 2-3 seconds)
2. Are prices being updated? (`heatmap.update_price()`)
3. Is WebSocket still connected?

### High Memory Usage

**Solutions**:
1. Reduce buffer size: `deque(maxlen=5000)`
2. Filter by time: Only keep last 30 minutes
3. Reduce number of symbols

---

## 📚 Files

- `live_liquidation_heatmap.py` - Main implementation
- `example_live_heatmap.py` - Usage examples
- `liquidation_hunter.py` - Integration with hunter

---

## 🎉 Summary

**You now have a FREE, real-time liquidation heatmap!**

- ✅ No API keys needed
- ✅ No monthly fees
- ✅ Real-time updates
- ✅ Works with liquidation hunter
- ✅ Same result as expensive heatmap models

**Perfect for live trading!** 🚀
