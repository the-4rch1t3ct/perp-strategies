# Memecoin Perpetual Futures Trading System

## Overview
Quantitative trading system for memecoin perpetual futures on Binance/Privex with max 20x leverage.

**Equity**: $10,000  
**Max Leverage**: 20x  
**Fees**: 0.0001% (Privex)  
**Target Assets**: DOGE, SHIB, PEPE, WIF, BONK, and other high-volume memecoins

## Project Structure

```
memecoin-perp-strategies/
├── data/              # Historical data storage
├── strategies/        # Strategy implementations
├── backtesting/       # Backtesting engine
├── analysis/          # Volatility, correlation, regime analysis
├── research/          # Research notes and findings
├── notebooks/         # Jupyter notebooks for exploration
└── requirements.txt   # Python dependencies
```

## Key Components

1. **Data Module** (`data/`): Fetches historical price, volume, funding rates from Binance Futures via CCXT
2. **Analysis Module** (`analysis/`): Volatility regimes, correlations, liquidation patterns
3. **Backtesting Engine** (`backtesting/`): Vectorized backtesting with realistic fees and slippage
4. **Strategies** (`strategies/`): Mean-reversion, momentum, volatility-arb prototypes
5. **Risk Management**: Position sizing, stop-loss, drawdown limits, risk-of-ruin calculations

## Quick Start

```bash
pip install -r requirements.txt
python data/fetch_data.py
python analysis/volatility_regimes.py
python backtesting/run_backtest.py
```

## Strategy Blueprint

See `research/STRATEGY_BLUEPRINT.md` for detailed entry/exit signals, position sizing, and risk parameters.

## Research Notes

- `research/VOLATILITY_ANALYSIS.md`: Volatility regime identification
- `research/CORRELATION_STUDY.md`: Cross-asset correlations
- `research/BACKTEST_RESULTS.md`: Historical performance metrics
