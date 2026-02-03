# High-Frequency Momentum Strategy Optimization

## Overview

Optimized momentum strategy for **5m/15m timeframes** to generate high trading volume for Privex point farming while improving win rate, reducing drawdowns, and increasing returns.

## Key Improvements

### 1. Lower Timeframe Support
- **5m timeframe**: Fast EMA = 12 periods (1h), Slow EMA = 36 periods (3h)
- **15m timeframe**: Fast EMA = 8 periods (2h), Slow EMA = 24 periods (6h)
- **Shorter hold times**: 30min-6h (5m) vs 1h-12h (15m)

### 2. Enhanced Entry Filters (Improve Win Rate)

**Volume Confirmation:**
- Volume must be 20% above average (`volume_multiplier: 1.2`)
- Volume percentile > 30% (avoid low liquidity periods)

**Trend Strength Filter:**
- Minimum trend strength: 0.3 (EMAs must be sufficiently separated)
- Avoids choppy/consolidation markets

**RSI Optimization:**
- Tighter range: 35-65 (vs 30-70)
- Neutral zone: 45-55 (avoids extreme readings)
- Long: RSI 45-65 (not oversold, not overbought)
- Short: RSI 35-55 (not overbought, not oversold)

**MACD Confirmation:**
- Long: MACD histogram > 0 (bullish momentum)
- Short: MACD histogram < 0 (bearish momentum)

**Price Position Filter:**
- Long: Price position > 30% (not at bottom of range)
- Short: Price position < 70% (not at top of range)

**Signal Strength Threshold:**
- Minimum 0.3 strength required (combines momentum, volume, trend)
- Prevents weak signals

### 3. Dynamic Risk Management (Reduce Drawdowns)

**ATR-Based Stops:**
- Stop loss: 1.5× ATR (dynamic, adapts to volatility)
- Take profit: 2.5× ATR (1.67:1 risk-reward ratio)
- Tighter stops in low volatility, wider in high volatility

**Trailing Stop:**
- Activates after 1.0× ATR profit
- Trails at 0.8× ATR distance
- Locks in profits while allowing continuation

**Quick Exit on Reversal:**
- Exit if EMA crossover (trend reversal)
- Exit if MACD histogram flips (momentum exhaustion)
- Prevents holding losing positions

### 4. High Trade Frequency (Volume Farming)

**Optimized Parameters:**
- Lower momentum threshold: 0.5% (vs 2% for 1h)
- Faster EMAs for quicker signals
- Shorter max hold times (6h for 5m, 12h for 15m)
- Multiple confirmation filters (but not too restrictive)

**Expected Trade Frequency:**
- **5m timeframe**: 50-150 trades per symbol per month
- **15m timeframe**: 30-80 trades per symbol per month
- **Portfolio (10 symbols)**: 500-1500 trades/month (5m) or 300-800 trades/month (15m)

## Strategy Parameters

### 5m Timeframe
```python
{
    'fast_period': 12,      # 1 hour
    'slow_period': 36,      # 3 hours
    'momentum_threshold': 0.005,  # 0.5%
    'min_hold_periods': 6,  # 30 minutes
    'max_hold_periods': 72, # 6 hours
}
```

### 15m Timeframe
```python
{
    'fast_period': 8,       # 2 hours
    'slow_period': 24,     # 6 hours
    'momentum_threshold': 0.005,  # 0.5%
    'min_hold_periods': 4,  # 1 hour
    'max_hold_periods': 48, # 12 hours
}
```

## Expected Performance Improvements

### Win Rate
- **Target**: 55-60% (vs current 49.7%)
- **Methods**: 
  - Volume confirmation (filters false breakouts)
  - Trend strength filter (avoids choppy markets)
  - RSI neutral zone (avoids extremes)
  - MACD confirmation (momentum alignment)

### Drawdowns
- **Target**: <5% average (vs current 6-15%)
- **Methods**:
  - ATR-based stops (tighter, volatility-adjusted)
  - Trailing stops (lock profits)
  - Quick exit on reversal (cut losses fast)
  - Trend strength filter (avoid weak trends)

### Returns
- **Target**: 15-25% monthly (vs current 1.7% average)
- **Methods**:
  - Higher trade frequency (more opportunities)
  - Better entry filters (higher quality trades)
  - Trailing stops (let winners run)
  - Dynamic position sizing (based on signal strength)

### Trade Volume
- **Target**: 500-1500 trades/month (5m) or 300-800 trades/month (15m)
- **Methods**:
  - Lower timeframe (5m/15m vs 1h)
  - Lower momentum threshold (0.5% vs 2%)
  - Faster EMAs
  - Shorter hold times

## Risk Management

### Position Sizing
- Base: 25% of capital per position
- Adjusted by signal strength (0.3-1.0)
- Volatility-adjusted (reduce in high vol)

### Stop Loss
- Dynamic: 1.5× ATR (typically 1-3%)
- Tighter than fixed 3-5% stops
- Adapts to market conditions

### Take Profit
- Dynamic: 2.5× ATR (typically 2-5%)
- Risk-reward: 1.67:1 minimum
- Trailing stop after 1× ATR profit

### Portfolio Limits
- Max 4 concurrent positions
- Max correlation: 0.7
- Max drawdown: 30% (hard stop)

## Implementation

### Usage
```python
from strategies.high_frequency_momentum import HighFrequencyMomentumStrategy

# 5m timeframe
strategy_5m = HighFrequencyMomentumStrategy(timeframe='5m')

# 15m timeframe
strategy_15m = HighFrequencyMomentumStrategy(timeframe='15m')

# Generate signals
signals = strategy_5m.generate_signals(data)
```

### Backtesting
```bash
python backtest_high_frequency.py
```

This will:
1. Fetch 5m data (if not exists)
2. Backtest on multiple symbols
3. Generate performance report
4. Save results to `research/backtest_high_frequency_5m.json`

## Next Steps

1. **Backtest on 5m data** - Validate improvements
2. **Parameter optimization** - Grid search for best parameters
3. **Symbol selection** - Identify best-performing memecoins
4. **Portfolio construction** - Combine top symbols
5. **Paper trading** - Validate in live environment
6. **Volume monitoring** - Track Privex point accumulation

## Notes

- **Fees**: 0.0001% per trade (Privex) = $0.01 per $10k trade
- **Slippage**: 5 bps modeled
- **Leverage**: Max 20x (capped)
- **Capital**: $10,000 initial

With 1000 trades/month at $10k notional each:
- Total volume: $10M/month
- Fees: $10/month (very low!)
- Privex points: Significant accumulation

---

*Strategy optimized for high-frequency trading and Privex point farming*
