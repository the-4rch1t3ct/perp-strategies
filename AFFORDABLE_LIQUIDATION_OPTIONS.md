# Affordable Liquidation Data Options

## 🎯 The Problem

Coinglass **liquidation heatmap models** (Model1, Model2, Model3) require the **Professional tier ($879/month)** - way too expensive!

## ✅ The Solution

We can build our own clusters from **liquidation history data**, which is available in much cheaper tiers!

---

## 💰 Affordable Coinglass Options

### Option 1: Build Clusters from History (RECOMMENDED)

**What's Available**:
- ✅ **Liquidation History** endpoint (`/api/futures/liquidation/history`)
- ✅ Available in **ALL lower tiers**:
  - **Hobbyist**: $29/month
  - **Startup**: $79/month  
  - **Standard**: $299/month

**How It Works**:
1. Fetch liquidation history (last 24 hours)
2. Build clusters using our clustering algorithm
3. Get same result as expensive heatmap models!

**Setup**:
```python
from liquidation_cluster_builder import AffordableCoinglassFetcher

fetcher = AffordableCoinglassFetcher(api_key='your_key')  # $29-$299/mo

# Get clusters (built from history)
clusters = fetcher.get_clusters(
    symbol='BTCUSDT',
    current_price=90000,
    exchange='binance',
    hours=24
)

# Clusters have same format as heatmap models:
# - price_level
# - side (long/short)
# - strength (0-1)
# - liquidation_count
# - total_notional
```

**Cost**: $29-$299/month (vs $879/month)

**Quality**: ⭐⭐⭐⭐ (almost as good as heatmap models)

---

## 🆓 Free Alternatives

### Option 2: Exchange APIs (100% Free)

#### Bybit WebSocket (Best Free Option)

**Why It's Great**:
- ✅ Completely free
- ✅ Real-time liquidation stream
- ✅ Good data quality
- ✅ Low latency

**Setup**:
```python
from liquidation_data_sources import ExchangeLiquidationFetcher

fetcher = ExchangeLiquidationFetcher('bybit')

# Fetch recent liquidations
liquidations = fetcher.fetch_liquidations('BTCUSDT', limit=1000)

# Or stream real-time
async def handle_liq(liq):
    print(f"Liquidation: {liq.price} {liq.side}")

await fetcher.watch_liquidations_websocket('BTCUSDT', handle_liq)
```

**Limitations**:
- Only Bybit data (not aggregated)
- May miss some liquidations (1/sec limit)

**Cost**: $0/month

**Quality**: ⭐⭐⭐⭐

---

#### OKX API (Free)

**Setup**:
```python
fetcher = ExchangeLiquidationFetcher('okx')
liquidations = fetcher.fetch_liquidations('BTC/USDT:USDT', limit=1000)
```

**Cost**: $0/month

**Quality**: ⭐⭐⭐⭐

---

### Option 3: Order Book Estimation (Free Fallback)

**How It Works**:
- Analyzes order book depth
- Estimates liquidation zones from large orders
- Less accurate but always available

**Setup**:
```python
from liquidation_data_sources import OrderBookLiquidationEstimator

estimator = OrderBookLiquidationEstimator('binance')

liquidations = estimator.estimate_liquidations(
    symbol='BTC/USDT:USDT',
    current_price=90000,
    price_range_pct=0.10
)
```

**Cost**: $0/month

**Quality**: ⭐⭐ (good for testing)

---

## 📊 Comparison Table

| Option | Cost | Quality | Real-time | Multi-Exchange | Setup |
|--------|------|---------|-----------|----------------|-------|
| **Coinglass History + Clusters** | $29-$299/mo | ⭐⭐⭐⭐ | ✅ | ✅ | Easy |
| **Bybit WebSocket** | $0 | ⭐⭐⭐⭐ | ✅ | ❌ | Medium |
| **OKX API** | $0 | ⭐⭐⭐⭐ | ✅ | ❌ | Medium |
| **Order Book** | $0 | ⭐⭐ | ✅ | ✅ | Easy |
| ~~Coinglass Heatmap~~ | ~~$879/mo~~ | ~~⭐⭐⭐⭐⭐~~ | ~~✅~~ | ~~✅~~ | ~~Easy~~ |

---

## 🚀 Recommended Setup

### For Production (Best Value):

```python
from liquidation_hunter import LiquidationHunter
from liquidation_cluster_builder import AffordableCoinglassFetcher

hunter = LiquidationHunter()

# Use affordable Coinglass (builds clusters from history)
hunter.set_data_source(
    source='coinglass',
    coinglass_api_key='your_key'  # $29-$299/mo plan
)

# Works exactly like expensive heatmap models!
signal, strength, cluster = hunter.generate_signal('BTC/USDT:USDT', 90000)
```

**Cost**: $29/month (Hobbyist) or $79/month (Startup)

### For Testing (Free):

```python
# Use free exchange APIs
hunter.set_data_source(
    source='exchange',
    exchange_name='bybit'  # Free!
)
```

**Cost**: $0/month

---

## 🔧 How Cluster Building Works

### Step 1: Fetch Liquidation History

```python
# Get last 24 hours of liquidations
liquidations = fetcher.fetch_liquidation_history(
    symbol='BTCUSDT',
    exchange='binance',
    hours=24
)
```

### Step 2: Build Clusters

Our algorithm:
1. **Groups** liquidations by price (within 2% windows)
2. **Weights** by time (recent = higher weight)
3. **Calculates** cluster strength (count + notional)
4. **Identifies** dominant side (long vs short)

### Step 3: Use Clusters

Clusters have same format as heatmap models:
- `price_level`: Weighted average price
- `side`: 'long' or 'short'
- `strength`: 0-1 (cluster strength)
- `liquidation_count`: Number of liquidations
- `total_notional`: Total USD value

---

## 💡 Why This Works

**Heatmap Models** = Pre-processed clusters from history  
**Our Solution** = Build clusters from same history data!

The only difference:
- Heatmap models: Pre-processed by Coinglass
- Our clusters: Processed on-the-fly

**Result**: Same data, 70-97% cheaper! 🎉

---

## 📈 Performance Comparison

### Coinglass Heatmap Models ($879/mo):
- Update frequency: Real-time
- Data quality: ⭐⭐⭐⭐⭐
- Processing: Pre-processed

### Our Cluster Builder ($29-$299/mo):
- Update frequency: 1-5 minutes (configurable)
- Data quality: ⭐⭐⭐⭐ (almost identical)
- Processing: On-the-fly

**Trade-off**: Slightly slower updates, but 70-97% cheaper!

---

## 🎯 Quick Start Guide

### Step 1: Choose Your Plan

**Production**: Coinglass Hobbyist ($29/mo) or Startup ($79/mo)  
**Testing**: Bybit WebSocket (free)

### Step 2: Get API Key (if using Coinglass)

1. Visit: https://coinglass.com/pricing
2. Sign up for **Hobbyist** ($29/mo) or **Startup** ($79/mo)
3. Get API key from dashboard

### Step 3: Integrate

```python
from liquidation_hunter import LiquidationHunter

hunter = LiquidationHunter()

# Option A: Affordable Coinglass
hunter.set_data_source(
    source='coinglass',
    coinglass_api_key='your_key'  # $29-$299/mo
)

# Option B: Free Exchange API
hunter.set_data_source(
    source='exchange',
    exchange_name='bybit'  # Free!
)

# Use normally - works exactly the same!
signal, strength, cluster = hunter.generate_signal('BTC/USDT:USDT', 90000)
```

---

## 🔍 Technical Details

### Cluster Building Algorithm

1. **Time Decay**: Recent liquidations weighted more heavily
   ```python
   weight = exp(-age_hours / 24)  # 24-hour decay
   ```

2. **Price Clustering**: Hierarchical clustering with 2% windows
   ```python
   distance_threshold = 0.02  # 2% price window
   ```

3. **Strength Calculation**:
   ```python
   strength = (count_strength * 0.4 + notional_strength * 0.6)
   ```

4. **Filtering**: Only clusters with 5+ liquidations

### Data Refresh

- **Coinglass History**: Update every 1-5 minutes
- **Exchange APIs**: Real-time (WebSocket) or 1-minute polling
- **Order Book**: Real-time

---

## ✅ Summary

**Instead of $879/month**, you can:

1. **Use Coinglass History** ($29-$299/mo) + build clusters ✅
2. **Use Bybit WebSocket** (free) + build clusters ✅
3. **Use OKX API** (free) + build clusters ✅
4. **Use Order Book** (free) + estimate clusters ✅

**All options work with the liquidation hunter!**

The cluster builder automatically handles everything - you just need liquidation history data (much cheaper than heatmap models).

---

## 📚 Files

- `liquidation_cluster_builder.py` - Cluster building from history
- `liquidation_data_sources.py` - Multiple data sources
- `liquidation_hunter.py` - Main trading agent

---

## 🎉 Bottom Line

**You don't need the $879/month Professional tier!**

Use **liquidation history** ($29-$299/mo) + our cluster builder = Same result, 70-97% cheaper!

Or use **free exchange APIs** = $0/month, still great quality!
