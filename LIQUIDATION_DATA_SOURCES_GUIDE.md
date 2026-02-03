# Liquidation Data Sources Guide

## Overview

This guide covers the best sources for liquidation cluster data, which is essential for the liquidation hunter strategy. The quality of your liquidation data directly impacts strategy performance.

---

## Data Source Comparison

| Source | Cost | Quality | Update Freq | Coverage | Ease of Use |
|--------|------|---------|-------------|----------|-------------|
| **Coinglass API** | $35/mo+ | ⭐⭐⭐⭐⭐ | Real-time | All exchanges | Easy |
| **Bybit WebSocket** | Free | ⭐⭐⭐⭐ | Real-time | Bybit only | Medium |
| **Binance API** | Free | ⭐⭐⭐ | 1-5 min | Binance only | Medium |
| **OKX API** | Free | ⭐⭐⭐⭐ | Real-time | OKX only | Medium |
| **Order Book** | Free | ⭐⭐ | Real-time | Any exchange | Easy |

---

## 1. Coinglass API (Recommended for Production)

### Why Coinglass?

✅ **Best Quality**: Professional-grade liquidation heatmap data  
✅ **Comprehensive**: Covers all major exchanges (Binance, Bybit, OKX, etc.)  
✅ **Real-time**: WebSocket and REST API options  
✅ **Historical Data**: 6+ years of historical liquidation data  
✅ **Visual Tools**: Web interface for manual analysis  

### Pricing

- **Starter**: $35/month - Basic API access
- **Professional**: $99/month - Advanced features
- **Enterprise**: Custom pricing

### Setup

1. **Get API Key**:
   - Visit: https://coinglass.com/pricing
   - Sign up and subscribe to API plan
   - Get your API key from dashboard

2. **API Endpoints**:
   - **Heatmap**: `/api/futures/liquidation/heatmap/model1`
   - **History**: `/api/futures/liquidation/history`
   - **Aggregated**: `/api/futures/liquidation/aggregated-history`

3. **Integration**:
```python
from liquidation_data_sources import LiquidationDataAggregator

# Initialize with Coinglass
aggregator = LiquidationDataAggregator(
    source='coinglass',
    coinglass_api_key='your_api_key_here'
)

# Fetch heatmap data
liquidations = aggregator.fetch('BTCUSDT', current_price=90000)
```

### API Documentation

- **Full Docs**: https://docs.coinglass.com
- **Heatmap Endpoint**: https://docs.coinglass.com/reference/liquidation-heatmap
- **History Endpoint**: https://docs.coinglass.com/reference/liquidation-history

### Response Format

```json
{
  "data": [
    {
      "price": 90000.0,
      "longLiquidation": 1250000.0,
      "shortLiquidation": 850000.0
    },
    {
      "price": 89500.0,
      "longLiquidation": 2100000.0,
      "shortLiquidation": 450000.0
    }
  ]
}
```

---

## 2. Exchange APIs (Free Alternatives)

### Bybit WebSocket (Best Free Option)

**Why Bybit?**
- Real-time liquidation stream
- Good data quality
- Free to use
- Low latency

**Setup**:
```python
from liquidation_data_sources import ExchangeLiquidationFetcher

fetcher = ExchangeLiquidationFetcher('bybit')

# WebSocket stream (real-time)
async def handle_liquidation(liquidation):
    print(f"Liquidation: {liquidation.price} {liquidation.side}")

await fetcher.watch_liquidations_websocket('BTCUSDT', handle_liquidation)

# Or fetch recent liquidations
liquidations = fetcher.fetch_liquidations('BTCUSDT', limit=1000)
```

**WebSocket Topic**: `liquidation.BTCUSDT`

**Limitations**:
- Only Bybit data
- May not capture all liquidations (1 per second limit)
- Requires WebSocket connection management

### Binance API

**Setup**:
```python
from liquidation_data_sources import ExchangeLiquidationFetcher

fetcher = ExchangeLiquidationFetcher('binance')

# Fetch liquidations (if supported)
liquidations = fetcher.fetch_liquidations('BTC/USDT:USDT', limit=1000)
```

**Limitations**:
- Limited liquidation data availability
- May require API key for some endpoints
- Update frequency varies

### OKX API

**Setup**:
```python
from liquidation_data_sources import ExchangeLiquidationFetcher

fetcher = ExchangeLiquidationFetcher('okx')

liquidations = fetcher.fetch_liquidations('BTC/USDT:USDT', limit=1000)
```

**Advantages**:
- Good liquidation data coverage
- Real-time WebSocket support
- Free API access

---

## 3. Order Book Estimation (Fallback)

When liquidation APIs aren't available, estimate liquidation levels from order book depth.

**How It Works**:
- Analyze order book for large orders at specific price levels
- Large orders below price = potential long liquidation zones
- Large orders above price = potential short liquidation zones

**Setup**:
```python
from liquidation_data_sources import OrderBookLiquidationEstimator

estimator = OrderBookLiquidationEstimator('binance')

liquidations = estimator.estimate_liquidations(
    symbol='BTC/USDT:USDT',
    current_price=90000,
    price_range_pct=0.10  # 10% range
)
```

**Limitations**:
- Less accurate than real liquidation data
- May miss actual liquidation clusters
- Good for testing/development only

---

## 4. Integration with Liquidation Hunter

### Recommended Setup

```python
from liquidation_hunter import LiquidationHunter
from liquidation_data_sources import LiquidationDataAggregator

# Initialize hunter
hunter = LiquidationHunter(
    initial_capital=10000.0,
    max_leverage=20.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.05
)

# Option 1: Use Coinglass (Best)
hunter.set_data_source(
    source='coinglass',
    coinglass_api_key='your_api_key'
)

# Option 2: Use Exchange API (Free)
hunter.set_data_source(
    source='exchange',
    exchange_name='bybit',
    api_key='optional',
    api_secret='optional'
)

# Option 3: Auto (tries Coinglass → Exchange → Orderbook)
hunter.set_data_source(
    source='auto',
    coinglass_api_key='your_key',  # If available
    exchange_name='bybit',
    api_key='optional'
)

# Now use hunter normally
signal, strength, cluster = hunter.generate_signal('BTC/USDT:USDT', 90000)
```

### Data Source Priority (Auto Mode)

When `source='auto'`, the aggregator tries sources in this order:

1. **Coinglass** (if API key provided) - Best quality
2. **Exchange API** (if exchange configured) - Good quality
3. **Order Book** (fallback) - Lower quality but always available

---

## 5. Real-Time Updates

### WebSocket Streaming

For real-time liquidation monitoring:

```python
import asyncio
from liquidation_data_sources import ExchangeLiquidationFetcher

async def monitor_liquidations():
    fetcher = ExchangeLiquidationFetcher('bybit')
    
    async def on_liquidation(liquidation):
        # Update your cluster analysis
        print(f"New liquidation: {liquidation.price} {liquidation.side}")
        # Trigger signal regeneration
        # hunter.generate_signal(symbol, current_price)
    
    await fetcher.watch_liquidations_websocket('BTCUSDT', on_liquidation)

asyncio.run(monitor_liquidations())
```

### Polling (REST API)

For periodic updates:

```python
import time
from liquidation_data_sources import LiquidationDataAggregator

aggregator = LiquidationDataAggregator(source='coinglass', coinglass_api_key='...')

while True:
    liquidations = aggregator.fetch('BTCUSDT', current_price=90000)
    # Process liquidations
    # Update clusters
    time.sleep(60)  # Update every minute
```

---

## 6. Data Quality Tips

### Improving Accuracy

1. **Use Multiple Sources**: Combine Coinglass + Exchange APIs
2. **Filter by Size**: Ignore small liquidations (< $10k)
3. **Time Decay**: Weight recent liquidations more heavily
4. **Exchange-Specific**: Use exchange API for that exchange's data

### Data Validation

```python
def validate_liquidation_data(liquidations):
    """Validate liquidation data quality"""
    if not liquidations:
        return False
    
    # Check for reasonable price range
    prices = [liq['price'] for liq in liquidations]
    price_range = (max(prices) - min(prices)) / min(prices)
    
    if price_range > 0.20:  # More than 20% range
        print("Warning: Unusual price range in liquidation data")
        return False
    
    # Check for sufficient data points
    if len(liquidations) < 10:
        print("Warning: Too few liquidation data points")
        return False
    
    return True
```

---

## 7. Cost-Benefit Analysis

### For Testing/Development
- **Use**: Exchange APIs (free) or Order Book estimation
- **Cost**: $0
- **Quality**: Good enough for testing

### For Paper Trading
- **Use**: Exchange APIs (Bybit WebSocket recommended)
- **Cost**: $0
- **Quality**: Good for validation

### For Live Trading
- **Use**: Coinglass API ($35/month)
- **Cost**: $35/month (~$1.17/day)
- **Quality**: Professional-grade, worth the cost
- **ROI**: If strategy makes $100+/month, easily pays for itself

---

## 8. Troubleshooting

### No Data Returned

**Check**:
1. API key valid (for Coinglass)
2. Exchange API working (test with simple call)
3. Symbol format correct (e.g., 'BTCUSDT' vs 'BTC/USDT:USDT')
4. Network connectivity

### Low Quality Data

**Solutions**:
1. Switch to Coinglass (better quality)
2. Filter small liquidations
3. Use multiple sources and aggregate
4. Increase time window for more data

### Rate Limits

**Solutions**:
1. Cache data (update every 1-5 minutes)
2. Use WebSocket instead of REST (no rate limits)
3. Rotate between multiple API keys
4. Reduce update frequency

---

## 9. Next Steps

1. ✅ **Choose Data Source**: Coinglass for production, Exchange API for testing
2. ✅ **Get API Key**: Sign up at coinglass.com/pricing
3. ✅ **Test Integration**: Run `example_liquidation_hunter.py`
4. ✅ **Validate Data**: Check data quality and update frequency
5. ✅ **Deploy**: Integrate with liquidation hunter agent

---

## Resources

- **Coinglass API Docs**: https://docs.coinglass.com
- **Coinglass Pricing**: https://coinglass.com/pricing
- **Bybit API Docs**: https://bybit-exchange.github.io/docs/v5
- **CCXT Documentation**: https://docs.ccxt.com

---

## Summary

**Best Setup for Production**:
- Primary: Coinglass API ($35/month)
- Fallback: Bybit WebSocket (free)
- Emergency: Order Book estimation (free)

**Best Setup for Testing**:
- Primary: Bybit WebSocket (free)
- Fallback: Order Book estimation (free)

The $35/month for Coinglass is a small investment that significantly improves data quality and strategy performance. If your strategy is profitable, it easily pays for itself.
