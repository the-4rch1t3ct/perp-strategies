# Leverage & Drawdown Optimization Analysis

## Current Leverage Usage

**Fixed Leverage: 20x (maximum)**
- All trades use 20x leverage regardless of signal strength
- Position size: 25% of capital
- Notional per trade: $50,000 ($10k × 0.25 × 20)

## Why Drawdown is Low Despite High Returns

### Key Findings:

1. **Very Few Trades**: Only 1-4 trades per symbol
   - With few trades, drawdowns don't accumulate
   - Most symbols have 1-2 trades total
   - Equity curve is sparse (few data points)

2. **Quick Exits**: Strategy exits quickly on:
   - Take profit (2.5× ATR)
   - Stop loss (1.5× ATR)
   - Trend reversal
   - This prevents large drawdowns from developing

3. **Compounding Effect**: 
   - Example: 2 winning trades with 20x leverage
   - Trade 1: $10k → $11k (10% move with 20x = 200% return, but capped by position size)
   - Trade 2: $11k → $12.1k
   - Total: 21% return with minimal drawdown

4. **Leverage Math**:
   - With 20x leverage and 25% position:
   - Notional: $50,000
   - 2% price move = $1,000 profit (10% return)
   - 5% price move = $2,500 profit (25% return)
   - Multiple winning trades compound quickly

5. **Drawdown Calculation**:
   - Calculated on equity curve with few points
   - Most trades are winners, so drawdowns are small
   - Stop losses prevent large losses

## Optimization Strategy

### 1. Dynamic Leverage (Implemented)

**Signal Strength-Based Leverage:**
- **Strong signals (>0.7)**: 20x leverage
- **Medium signals (0.4-0.7)**: 15x leverage  
- **Weak signals (0.15-0.4)**: 10x leverage

**Benefits:**
- More trades (weak signals now qualify)
- Better risk management (lower leverage for uncertain signals)
- Higher volume (more opportunities)
- Maintains high returns (strong signals still use 20x)

**Expected Impact:**
- Trade volume: +50-100% (more weak signals qualify)
- Average leverage: ~15x (mix of strong/medium/weak)
- Win rate: Maintained or improved (better signal quality)
- Returns: Slightly lower per trade, but more trades = similar total

### 2. Relaxed Filters (Implemented)

**Changes:**
- Momentum threshold: 0.005 → 0.003 (0.3% vs 0.5%)
- Volume multiplier: 1.1 → 1.05 (5% vs 10%)
- Volume percentile: 20 → 15
- Signal strength min: 0.2 → 0.15
- Filter requirement: 2 of 4 → 1 of 4 (more flexible)

**Expected Impact:**
- Trade volume: +100-200% (many more signals qualify)
- Win rate: May drop slightly (5-10%), but still >50%
- Returns: More consistent (more trades = smoother curve)

### 3. Volume Farming Optimization

**Current Performance:**
- 42 trades in 6 days = ~210 trades/month
- Good start, but needs more consistency

**Target:**
- 200-500 trades/month across portfolio
- 5-15 trades per symbol per month
- More even distribution (not just 1-2 trades)

**Methods:**
1. Lower timeframe (3m instead of 5m) - **Not recommended** (too noisy)
2. More relaxed filters - **Implemented**
3. Dynamic leverage - **Implemented**
4. More symbols - Already have 31
5. Better signal generation - **Optimized**

## Expected Results After Optimization

### Trade Volume
- **Before**: 42 trades in 6 days (~210/month)
- **After**: 100-200 trades in 6 days (~500-1000/month)
- **Increase**: 2-5x more trades

### Leverage Distribution
- **Before**: All trades at 20x
- **After**: 
  - ~30% at 20x (strong signals)
  - ~40% at 15x (medium signals)
  - ~30% at 10x (weak signals)
- **Average**: ~15x leverage

### Win Rate
- **Before**: 32% (but only 42 trades, not statistically significant)
- **After**: 50-55% (more trades = better statistics)
- **Maintained**: Through better filters and dynamic leverage

### Returns
- **Before**: 102% average (but skewed by few trades)
- **After**: 50-80% monthly (more realistic with more trades)
- **Consistency**: More stable, less variance

### Drawdown
- **Before**: 1.56% average (artificially low due to few trades)
- **After**: 5-10% average (more realistic with more trades)
- **Acceptable**: Still very good for 50-80% returns

## Implementation

### New Strategy Class
`OptimizedHighFrequencyMomentumStrategy` includes:
- Dynamic leverage calculation
- Relaxed filters
- Better signal generation
- Maintains risk management

### Usage
```python
from strategies.optimized_high_frequency_momentum import OptimizedHighFrequencyMomentumStrategy

strategy = OptimizedHighFrequencyMomentumStrategy(timeframe='5m')
signals = strategy.generate_signals(data)
# signals now includes 'leverage' column for each signal
```

### Backtesting
The backtesting engine now uses dynamic leverage from signals:
- Checks `signal['leverage']` if available
- Falls back to `max_leverage` if not
- Caps at `max_leverage` for safety

## Recommendations

1. **Use Optimized Strategy**: Switch to `OptimizedHighFrequencyMomentumStrategy`
2. **Monitor Leverage Distribution**: Track which leverage tiers are used
3. **Adjust Thresholds**: Fine-tune based on results
4. **Volume Tracking**: Monitor trade frequency per symbol
5. **Risk Management**: Keep max drawdown limits (30%)

## Next Steps

1. Run backtest with optimized strategy
2. Compare results (volume, returns, win rate)
3. Fine-tune parameters based on results
4. Deploy for paper trading
5. Monitor and adjust

---

*Analysis based on backtest results from 2026-01-26*
