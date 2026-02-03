# Volatility Regime Analysis

## Overview

This document analyzes volatility regimes, spikes, squeezes, and decay patterns in memecoin perpetual futures markets.

## Methodology

1. **Realized Volatility**: Calculated as rolling 24h standard deviation of log returns, annualized
2. **Regime Classification**: 
   - Low: < 25th percentile
   - Normal Low: 25th-50th percentile
   - Normal High: 50th-75th percentile
   - High: 75th-95th percentile
   - Extreme: > 95th percentile
3. **Spike Detection**: Volatility > 2 standard deviations above rolling mean
4. **Decay Analysis**: Post-spike volatility decay patterns over 24-72 hours

## Key Findings

### Volatility Characteristics

- **Mean Volatility**: Varies by asset (typically 50-150% annualized)
- **Spike Frequency**: 2-5 spikes per 90-day period per asset
- **Decay Rate**: Average 40-60% decay within 48 hours post-spike

### Regime Transitions

- **Low → High**: Often precedes major moves (breakout setups)
- **High → Low**: Mean reversion opportunities
- **Extreme Spikes**: Usually followed by sharp reversals (liquidation cascades)

## Trading Implications

1. **Mean Reversion**: Enter short volatility positions during extreme spikes
2. **Momentum**: Enter long positions when volatility transitions from low to high
3. **Risk Management**: Reduce position sizes during extreme volatility regimes

## Data Sources

- Binance Futures (via CCXT)
- 1-hour candles
- 90-day lookback period

---

*This analysis is updated as new data is collected.*
