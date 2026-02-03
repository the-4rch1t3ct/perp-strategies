# Memecoin Perpetual Futures Trading System - Summary

## 🎯 Objective

Build a quantitative trading system for memecoin perpetual futures that generates alpha while managing tail risks. The system targets aggressive compounding with robust risk controls.

## 📊 System Overview

### Portfolio Configuration
- **Initial Capital**: $10,000
- **Max Leverage**: 20x
- **Fee Rate**: 0.0001% (Privex)
- **Target Assets**: DOGE, SHIB, PEPE, WIF, BONK + 15+ other memecoins

### Core Components

1. **Data Module** (`data/`)
   - Fetches historical data from Binance Futures via CCXT
   - Supports OHLCV, funding rates, open interest
   - Stores data as CSV for easy access

2. **Analysis Module** (`analysis/`)
   - Volatility regime detection (low/normal/high/extreme)
   - Spike detection and decay pattern analysis
   - Correlation analysis across memecoins
   - Liquidation cascade estimation

3. **Strategy Module** (`strategies/`)
   - **Mean Reversion**: Z-score based entry/exit
   - **Momentum**: EMA crossover + RSI + momentum filters
   - **Volatility Arbitrage**: Volatility regime trading

4. **Backtesting Engine** (`backtesting/`)
   - Vectorized backtesting for speed
   - Realistic fees (0.0001%) and slippage (5 bps)
   - Comprehensive performance metrics

5. **Risk Management** (`risk_management.py`)
   - Dynamic position sizing (Kelly-adjusted)
   - Volatility-adjusted stops
   - Risk-of-ruin calculations
   - Portfolio-level risk limits

## 🚀 Quick Start

### Installation
```bash
cd /home/botadmin/memecoin-perp-strategies
pip install -r requirements.txt
```

### Run Examples
```bash
python quick_start.py
```

### Run Full Pipeline
```bash
python main.py
```

This will:
1. Fetch 90 days of 1h data for all memecoins
2. Analyze volatility regimes
3. Backtest all strategies
4. Generate research reports

## 📈 Strategy Performance Targets

| Strategy | Win Rate | Sharpe | Sortino | Max DD |
|----------|----------|--------|---------|--------|
| Mean Reversion | 40-45% | 1.5-2.0 | 2.0-2.5 | 15-25% |
| Momentum | 50-55% | 1.8-2.5 | 2.5-3.5 | 20-30% |
| Volatility Arb | 45-50% | 1.6-2.2 | 2.2-3.0 | 18-28% |
| **Portfolio** | **48-52%** | **1.8-2.3** | **2.5-3.5** | **25-30%** |

## 🛡️ Risk Controls

### Position Limits
- Max position size: 25% of capital
- Max total exposure: 20x leverage × capital
- Max concurrent positions: 4
- Max correlation: 0.7 between positions

### Drawdown Limits
- **Warning**: 20% → Reduce position sizes 50%
- **Hard Stop**: 30% → Close all positions, stop trading
- **Recovery Mode**: After drawdown, reduce risk to 1% per trade

### Stop Loss Logic
- Default: 5% (mean reversion), 3% (momentum)
- Volatility-adjusted: 2× ATR or 1.5× realized volatility
- Trailing stop: After 1:1 R:R, trail at breakeven

## 📚 Documentation

### Primary Documents
- **REFERENCE_INDEX.md**: Complete system reference (for AI agents)
- **STRATEGY_BLUEPRINT.md**: Detailed strategy documentation
- **README.md**: Project overview and setup

### Research Notes
- **VOLATILITY_ANALYSIS.md**: Volatility regime findings
- **CORRELATION_STUDY.md**: Cross-asset correlation analysis
- **BACKTEST_REPORT.md**: Generated backtest results (after running)

## 🔧 Key Files

### For Data Collection
- `data/fetch_data.py`: Main data fetcher
- `data/*.csv`: Historical OHLCV data

### For Strategy Development
- `strategies/base_strategy.py`: Base class + 3 implementations
- `risk_management.py`: Risk calculations

### For Backtesting
- `backtesting/engine.py`: Backtesting engine
- `main.py`: Full pipeline orchestrator

### For Analysis
- `analysis/volatility_regimes.py`: Volatility analysis
- `research/*.md`: Research findings

## 🎓 Usage Examples

### Fetch Data
```python
from data.fetch_data import MemecoinDataFetcher
fetcher = MemecoinDataFetcher()
data = fetcher.fetch_all_memecoins(timeframe='1h', days=90)
```

### Generate Signals
```python
from strategies.base_strategy import MeanReversionStrategy
strategy = MeanReversionStrategy()
signals = strategy.generate_signals(data)
```

### Run Backtest
```python
from backtesting.engine import BacktestEngine, BacktestConfig
config = BacktestConfig(initial_capital=10000.0, max_leverage=20.0)
engine = BacktestEngine(config)
results = engine.backtest_strategy(data, signals, symbol='DOGE/USDT:USDT')
```

### Risk Management
```python
from risk_management import RiskManager
risk_mgr = RiskManager(initial_capital=10000.0, max_leverage=20.0)
position_size, notional = risk_mgr.calculate_position_size(
    current_capital=10000,
    entry_price=0.10,
    stop_loss_price=0.095,
    signal_strength=0.8
)
```

## 📊 Expected Outputs

After running the full pipeline:

1. **Data Files** (`data/`)
   - `{SYMBOL}_1h.csv`: Historical OHLCV data
   - `metadata.json`: Fetch metadata

2. **Analysis Results** (`research/`)
   - `volatility_analysis.json`: Volatility statistics
   - `backtest_results.json`: Performance metrics
   - `BACKTEST_REPORT.md`: Formatted report

3. **Research Notes** (`research/`)
   - Updated with findings from analysis

## 🔍 For Clawdbot / AI Agents

See **REFERENCE_INDEX.md** for:
- Complete file structure
- All classes and methods
- Usage examples
- Data formats
- Key parameters

## ⚠️ Important Notes

1. **Data Requirements**: System needs historical data before backtesting
2. **API Limits**: CCXT respects rate limits automatically
3. **Fees**: All calculations use 0.0001% (Privex fee structure)
4. **Leverage**: System caps at 20x as specified
5. **Risk**: Always test strategies before live trading

## 🚧 Future Enhancements

- [ ] Funding rate arbitrage strategies
- [ ] Open interest analysis
- [ ] Sentiment analysis integration
- [ ] Multi-timeframe strategies
- [ ] Portfolio optimization
- [ ] Live trading integration
- [ ] Real-time monitoring dashboard

## 📞 System Status

✅ **Core Components**: Complete
✅ **Strategy Prototypes**: 3 strategies implemented
✅ **Backtesting Engine**: Functional with realistic assumptions
✅ **Risk Management**: Comprehensive risk controls
✅ **Documentation**: Complete reference materials

🔄 **Next Steps**:
1. Fetch historical data
2. Run initial backtests
3. Optimize strategy parameters
4. Validate in paper trading

---

**System Location**: `/home/botadmin/memecoin-perp-strategies/`

**Last Updated**: 2026-01-26
