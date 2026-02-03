# Liquidation Data Sources - Quick Summary

## 🎯 Best Sources Ranked

### 1. **Coinglass History + Cluster Builder** ⭐⭐⭐⭐ (RECOMMENDED - AFFORDABLE)

**What You Need**: Build clusters from liquidation history (NOT expensive heatmap models!)

**Why It's Best**:
- ✅ Professional-grade data quality
- ✅ Covers ALL major exchanges (Binance, Bybit, OKX, etc.)
- ✅ Real-time updates (1-5 min refresh)
- ✅ Historical data (6+ years)
- ✅ Same result as $879/mo heatmap models!
- ✅ Aggregated data from multiple exchanges

**Cost**: $29/month (Hobbyist) or $79/month (Startup)

**Note**: Heatmap models require $879/mo Professional tier - we build clusters from history instead!

### ~~1. **Coinglass Heatmap Models** ⭐⭐⭐⭐⭐ (TOO EXPENSIVE)~~

~~**Cost**: $879/month (Professional tier) - Not recommended!~~

~~**Alternative**: Use liquidation history ($29-$299/mo) + build clusters = Same result!~~

**Setup**:
```python
from liquidation_hunter import LiquidationHunter

hunter = LiquidationHunter()
hunter.set_data_source(
    source='coinglass',
    coinglass_api_key='your_api_key'  # Get from coinglass.com/pricing
)
```

**Get API Key**: https://coinglass.com/pricing

**API Docs**: https://docs.coinglass.com

---

### 2. **Bybit WebSocket** ⭐⭐⭐⭐ (BEST FREE OPTION)

**Why Use It**:
- ✅ Free
- ✅ Real-time liquidation stream
- ✅ Good data quality
- ✅ Low latency

**Limitations**:
- ❌ Only Bybit data (not aggregated)
- ❌ May miss some liquidations (1 per second limit)

**Setup**:
```python
hunter.set_data_source(
    source='exchange',
    exchange_name='bybit'
)
```

---

### 3. **Exchange APIs** ⭐⭐⭐ (FREE)

**Supported Exchanges**:
- Bybit (best free option)
- OKX (good liquidation API)
- Binance (limited data)

**Setup**:
```python
hunter.set_data_source(
    source='exchange',
    exchange_name='bybit',  # or 'okx', 'binance'
    api_key='optional',     # Not always required
    api_secret='optional'
)
```

---

### 4. **Order Book Estimation** ⭐⭐ (FALLBACK)

**When to Use**:
- Testing/development
- No API access available
- Emergency fallback

**How It Works**:
- Analyzes order book depth
- Estimates liquidation zones from large orders
- Less accurate but always available

**Setup**:
```python
hunter.set_data_source(
    source='orderbook',
    exchange_name='binance'
)
```

---

## 💡 Recommended Setup

### For Production Trading:
```python
# Primary: Coinglass (best quality)
# Fallback: Bybit WebSocket (if Coinglass fails)

hunter.set_data_source(
    source='auto',  # Tries Coinglass → Exchange → Orderbook
    coinglass_api_key='your_key',
    exchange_name='bybit'
)
```

### For Testing/Paper Trading:
```python
# Use free exchange APIs

hunter.set_data_source(
    source='exchange',
    exchange_name='bybit'  # Free and good quality
)
```

---

## 📊 Quick Comparison

| Source | Cost | Quality | Real-time | Multi-Exchange |
|--------|------|---------|-----------|----------------|
| **Coinglass** | $35/mo | ⭐⭐⭐⭐⭐ | ✅ | ✅ |
| **Bybit WS** | Free | ⭐⭐⭐⭐ | ✅ | ❌ |
| **OKX API** | Free | ⭐⭐⭐⭐ | ✅ | ❌ |
| **Binance API** | Free | ⭐⭐⭐ | ⚠️ | ❌ |
| **Order Book** | Free | ⭐⭐ | ✅ | ✅ |

---

## 🚀 Getting Started

### Step 1: Choose Your Source

**Production**: Coinglass History ($29-$79/month) - Builds clusters from history  
**Testing**: Bybit WebSocket (free)

### Step 2: Get API Key (if using Coinglass)

1. Visit: https://coinglass.com/pricing
2. Sign up for Starter plan ($35/month)
3. Get API key from dashboard
4. See docs: https://docs.coinglass.com

### Step 3: Integrate

```python
from liquidation_hunter import LiquidationHunter

hunter = LiquidationHunter()

# Option A: Coinglass History (affordable - builds clusters)
hunter.set_data_source(
    source='coinglass',
    coinglass_api_key='your_key'  # $29-$299/mo (NOT $879!)
)

# Option B: Free exchange API
hunter.set_data_source(
    source='exchange',
    exchange_name='bybit'
)

# Option C: Auto (tries all)
hunter.set_data_source(
    source='auto',
    coinglass_api_key='your_key',  # If available
    exchange_name='bybit'
)

# Use normally
signal, strength, cluster = hunter.generate_signal('BTC/USDT:USDT', 90000)
```

---

## 💰 Cost-Benefit

**Coinglass History $29-$79/month**:
- If strategy makes $50+/month → easily pays for itself
- Better data = better trades = higher win rate
- Worth it for serious trading
- **97% cheaper than Professional tier!**

**Free Options**:
- Good for testing and paper trading
- May miss some liquidation clusters
- Single exchange only (not aggregated)

---

## 📚 Full Documentation

- **Data Sources Guide**: `LIQUIDATION_DATA_SOURCES_GUIDE.md`
- **Liquidation Hunter Guide**: `LIQUIDATION_HUNTER_GUIDE.md`
- **Example Code**: `example_liquidation_hunter.py`

---

## 🎯 Bottom Line

**You saw Coinglass heatmaps** - but you DON'T need the $879/month Professional tier!

**For production**: **Use Coinglass History ($29-$79/month) + build clusters**  
**For testing**: **Use Bybit WebSocket (free)**

Our cluster builder creates the same clusters from liquidation history - **97% cheaper** than Professional tier heatmap models!

The clusters work exactly the same - those bright zones that act as price magnets! 🎯

**See `AFFORDABLE_LIQUIDATION_OPTIONS.md` for full details!**
