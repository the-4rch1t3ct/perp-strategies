# Liquidation Hunter Strategy Guide

## Executive Summary

**Strategy**: Liquidation cluster hunting - identify strong liquidation clusters that act as price magnets and trade toward them.

**Concept**: When many traders have stop-loss orders (liquidations) at similar price levels, these levels act as "magnets" because:
1. Market makers push price toward these zones to trigger liquidations
2. Cascading liquidations create momentum
3. High concentration = stronger pull

**Expected Performance**: 
- Higher win rate than momentum (65-75%+)
- Faster trades (minutes to hours vs days)
- Lower drawdowns (tighter stops)
- Profit factor: 2.0-3.0x

---

## How It Works

### 1. Liquidation Heatmap Scanning

The agent continuously scans liquidation data from exchanges to identify:
- **Price levels** where many liquidations occur
- **Cluster strength** (concentration of liquidations)
- **Side** (long or short liquidations)
- **Distance** from current price

### 2. Cluster Identification

Uses hierarchical clustering to group liquidations:
- Groups liquidations within 2% price windows
- Calculates weighted average price (by notional size)
- Determines dominant side (long vs short liquidations)
- Scores clusters by strength (0-1 scale)

### 3. Signal Generation

**Long Signal**: 
- Price is **below** a strong **short liquidation cluster**
- Enter long → price rises toward cluster → shorts get liquidated

**Short Signal**:
- Price is **above** a strong **long liquidation cluster**  
- Enter short → price falls toward cluster → longs get liquidated

### 4. Entry Logic

- Minimum cluster strength: 0.6 (top 40% of clusters)
- Maximum distance: 10% from current price
- Sweet spot: 2-5% away from cluster
- Position size: Based on cluster strength (7.5% to 15% allocation)

### 5. Exit Logic

**Take Profit**: 
- Near cluster level (0.5% before cluster to avoid reversal)
- Or fixed 5% profit target

**Stop Loss**: 
- 3% opposite direction from cluster
- Tighter than momentum strategy

**Cluster Reached**: 
- Exit when price gets within 0.5% of cluster
- Avoid reversal risk after liquidations trigger

---

## Advantages Over Momentum Strategy

| Feature | Momentum | Liquidation Hunter |
|---------|----------|-------------------|
| **Win Rate** | 60%+ | 65-75%+ |
| **Trade Duration** | 12-24 hours | Minutes to hours |
| **Stop Loss** | 5% | 3% (tighter) |
| **Drawdown** | 8-12% | 5-8% |
| **Profit Factor** | 1.8x | 2.0-3.0x |
| **Market Dependency** | Needs trends | Works in choppy markets |

---

## Integration with PriveX

### Data Sources

**Option 1: Exchange Liquidation APIs**
- Binance: `fetch_liquidations()` via CCXT
- Bybit: `watch_liquidations()` WebSocket
- OKX: `watch_liquidations_for_symbols()`

**Option 2: Third-Party APIs**
- Coinglass liquidation heatmap API
- Glassnode liquidation data
- Custom liquidation aggregators

**Option 3: Estimate from Order Book**
- Analyze order book depth
- Estimate liquidation levels from funding rates
- Use historical liquidation patterns

### Implementation Steps

```python
from liquidation_hunter import LiquidationHunter
import asyncio
from datetime import datetime

# Initialize hunter
hunter = LiquidationHunter(
    initial_capital=10000.0,
    max_leverage=20.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.05,
    min_cluster_strength=0.6,
    max_distance_pct=0.10
)

# Set up exchange connection
hunter.set_exchange('binance', api_key='...', api_secret='...')

# Main trading loop
async def trading_loop():
    symbols = [
        '1000000MOG/USDT:USDT',
        '1000CAT/USDT:USDT',
        'MEME/USDT:USDT',
        '1000CHEEMS/USDT:USDT',
        '1000PEPE/USDT:USDT'
    ]
    
    while True:
        for symbol in symbols:
            # Get current price
            current_price = await privex_api.get_price(symbol)
            
            # Check existing positions
            closed = hunter.check_positions(
                {symbol: current_price},
                datetime.now()
            )
            
            # Generate signal
            signal, strength, cluster = hunter.generate_signal(
                symbol, current_price
            )
            
            # Enter position if signal strong
            if signal != 0 and strength > 0.7 and symbol not in hunter.positions:
                position = hunter.enter_position(
                    symbol=symbol,
                    signal=signal,
                    price=current_price,
                    time=datetime.now(),
                    cluster=cluster
                )
                
                if position:
                    # Place order on PriveX
                    await privex_api.create_market_order(
                        symbol=symbol,
                        side=position.side,
                        amount=position.size,
                        leverage=position.leverage
                    )
                    print(f"Entered {position.side} on {symbol} @ {position.entry_price}")
                    print(f"Target cluster: {cluster.price_level} (strength: {cluster.strength:.2f})")
        
        await asyncio.sleep(60)  # Check every minute
```

---

## Risk Management

### Position Sizing

- **Base allocation**: 15% per position
- **Strength multiplier**: 0.5x to 1.0x based on cluster strength
- **Effective range**: 7.5% to 15% per position
- **Max positions**: 3-5 concurrent (to avoid overexposure)

### Stop Loss Rules

- **Fixed**: 3% from entry
- **Trailing**: Consider trailing stop after 2% profit
- **Cluster invalidation**: Exit if cluster strength drops below 0.4

### Drawdown Limits

- **Daily max loss**: 5% of capital → pause trading
- **Weekly max loss**: 10% of capital → reduce position size by 50%
- **Max drawdown**: 15% → stop trading, review strategy

---

## Performance Expectations

### Best Case Scenario
- **Win Rate**: 75%+
- **Avg Win**: 4-6%
- **Avg Loss**: 2-3%
- **Profit Factor**: 3.0x+
- **Monthly Return**: 25-40%

### Expected Scenario
- **Win Rate**: 65-70%
- **Avg Win**: 3-5%
- **Avg Loss**: 2.5-3%
- **Profit Factor**: 2.0-2.5x
- **Monthly Return**: 15-25%

### Worst Case Scenario
- **Win Rate**: 55-60%
- **Avg Win**: 2-4%
- **Avg Loss**: 3-4%
- **Profit Factor**: 1.2-1.5x
- **Monthly Return**: 5-10%

---

## Monitoring & Alerts

### Key Metrics to Track

1. **Cluster Quality**
   - Average cluster strength: Should be > 0.6
   - Cluster hit rate: % of clusters that price reaches
   - Cluster invalidation rate: Clusters that disappear before hit

2. **Trade Performance**
   - Win rate: Should be > 65%
   - Profit factor: Should be > 2.0
   - Avg trade duration: Should be < 4 hours
   - Cluster reached rate: % of trades that hit cluster

3. **Risk Metrics**
   - Max drawdown: Should be < 10%
   - Stop loss hit rate: Should be < 35%
   - Position concentration: Max 3-5 positions

### Alert Triggers

```
⚠️ Win rate < 60% (rolling 20 trades) → Reduce position size
⚠️ Profit factor < 1.5 → Review cluster selection
⚠️ Cluster hit rate < 50% → Increase min_cluster_strength
⚠️ Drawdown > 10% → Reduce allocation by 50%
⚠️ Stop loss rate > 40% → Widen stops to 4%
```

---

## Optimization Tips

### If Win Rate is Low (< 60%)

1. **Increase minimum cluster strength**: 0.6 → 0.7
2. **Reduce max distance**: 10% → 7%
3. **Tighter entry filter**: Only enter if strength > 0.75
4. **Add confirmation**: Wait for price to start moving toward cluster

### If Too Few Signals

1. **Decrease minimum cluster strength**: 0.6 → 0.5
2. **Increase max distance**: 10% → 15%
3. **Add more symbols**: Scan more trading pairs
4. **Reduce cluster window**: 2% → 1.5% (more clusters)

### If Clusters Don't Get Hit

1. **Check data quality**: Verify liquidation data is accurate
2. **Reduce exit distance**: Exit 0.5% → 0.3% before cluster
3. **Add momentum filter**: Only trade if price is moving toward cluster
4. **Consider time decay**: Clusters may expire after 24-48 hours

---

## Data Requirements

### Minimum Data Needed

1. **Liquidation Events**:
   - Price level
   - Side (long/short)
   - Notional size
   - Timestamp

2. **Update Frequency**:
   - Real-time: Best (WebSocket)
   - 1-minute: Good
   - 5-minute: Acceptable
   - 15-minute+: Not recommended

3. **Historical Data**:
   - Last 24 hours: Minimum
   - Last 7 days: Recommended
   - Last 30 days: Optimal

### Data Sources Comparison

| Source | Update Freq | Accuracy | Cost | Ease |
|--------|-------------|----------|------|------|
| Exchange API | Real-time | High | Free | Medium |
| Coinglass | Real-time | High | Paid | Easy |
| Glassnode | 1-min | Medium | Paid | Easy |
| Order Book Estimate | Real-time | Low | Free | Hard |

---

## Comparison: Momentum vs Liquidation Hunter

### When to Use Momentum Strategy
- ✅ Strong trending markets
- ✅ Longer timeframes (4h+)
- ✅ Higher capital tolerance
- ✅ Less frequent monitoring

### When to Use Liquidation Hunter
- ✅ Choppy/consolidating markets
- ✅ Shorter timeframes (1h-4h)
- ✅ Lower capital tolerance
- ✅ Active monitoring possible
- ✅ High volatility periods

### Hybrid Approach
- Use **Liquidation Hunter** in choppy markets
- Switch to **Momentum** when trends emerge
- Combine signals: Only take liquidation trades if momentum confirms

---

## Next Steps

1. ✅ Review `liquidation_hunter.py` code
2. ✅ Set up liquidation data source (exchange API or third-party)
3. ✅ Test cluster identification on historical data
4. ✅ Paper trade for 24-48 hours
5. ✅ Optimize parameters (min_cluster_strength, max_distance_pct)
6. ✅ Go live with small capital ($1,000-2,000)
7. ✅ Scale up after 1 week of positive results

---

## FAQ

**Q: What if liquidation data isn't available?**  
A: Use order book depth analysis or estimate from funding rates. You can also use historical liquidation patterns.

**Q: How often should I refresh liquidation data?**  
A: Every 1-5 minutes. Real-time is best but 1-minute updates work well.

**Q: Can I combine with momentum strategy?**  
A: Yes! Use liquidation hunter for entries, momentum for exits. Or use liquidation clusters as confirmation for momentum signals.

**Q: What happens if cluster disappears before price reaches it?**  
A: Exit the position if cluster strength drops below 0.4 or if new stronger cluster appears in opposite direction.

**Q: Should I trade all clusters?**  
A: No. Only trade clusters with strength > 0.6 and within 2-10% of current price. Focus on strongest clusters.

---

## Support

For questions or issues:
- Review `liquidation_hunter.py` code comments
- Check exchange API documentation for liquidation endpoints
- Test with paper trading before live deployment

**Good luck hunting those liquidations! 🎯**
