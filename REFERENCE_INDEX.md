# Memecoin Perpetual Futures Strategy System - Reference Index

**For Clawdbot and AI Agents**

This document provides a comprehensive index of all components, data, and research in the memecoin trading system.

## Project Structure

```
memecoin-perp-strategies/
├── README.md                    # Project overview and quick start
├── requirements.txt             # Python dependencies
├── main.py                      # Main orchestrator script
├── risk_management.py           # Risk management module
│
├── data/                        # Data collection and storage
│   ├── fetch_data.py           # CCXT-based data fetcher
│   └── *.csv                   # Historical OHLCV data (symbol_timeframe.csv)
│
├── analysis/                    # Market analysis modules
│   └── volatility_regimes.py   # Volatility regime detection and analysis
│
├── strategies/                  # Trading strategy implementations
│   └── base_strategy.py        # Base class + 3 strategy prototypes:
│                               #   - MeanReversionStrategy
│                               #   - MomentumStrategy
│                               #   - VolatilityArbitrageStrategy
│
├── backtesting/                # Backtesting framework
│   └── engine.py               # Vectorized backtesting engine
│
└── research/                    # Research notes and results
    ├── STRATEGY_BLUEPRINT.md   # Complete strategy documentation
    ├── VOLATILITY_ANALYSIS.md  # Volatility regime findings
    ├── CORRELATION_STUDY.md    # Cross-asset correlation analysis
    ├── BACKTEST_REPORT.md      # Generated backtest results
    ├── volatility_analysis.json # Volatility statistics (JSON)
    └── backtest_results.json   # Backtest performance metrics (JSON)
```

## Key Components

### 1. Data Module (`data/fetch_data.py`)

**Purpose**: Fetch historical memecoin perpetual futures data from Binance Futures

**Key Classes**:
- `MemecoinDataFetcher`: Main data fetcher using CCXT

**Key Methods**:
- `fetch_ohlcv()`: Fetch OHLCV candles
- `fetch_funding_rate()`: Fetch funding rate history
- `fetch_open_interest()`: Fetch open interest data
- `fetch_all_memecoins()`: Batch fetch all memecoins
- `load_data()`: Load previously fetched data

**Usage**:
```python
from data.fetch_data import MemecoinDataFetcher
fetcher = MemecoinDataFetcher()
data = fetcher.fetch_all_memecoins(timeframe='1h', days=90)
```

**Data Format**: CSV files named `{SYMBOL}_{TIMEFRAME}.csv` with columns: timestamp, open, high, low, close, volume

---

### 2. Analysis Module (`analysis/volatility_regimes.py`)

**Purpose**: Analyze volatility regimes, spikes, and decay patterns

**Key Classes**:
- `VolatilityRegimeAnalyzer`: Main analyzer

**Key Methods**:
- `identify_volatility_regimes()`: Classify volatility into low/normal/high/extreme
- `detect_volatility_spikes()`: Identify sudden volatility spikes
- `analyze_decay_patterns()`: Analyze post-spike decay
- `calculate_correlations()`: Calculate correlation matrix
- `analyze_liquidation_cascades()`: Estimate liquidation pressure

**Usage**:
```python
from analysis.volatility_regimes import VolatilityRegimeAnalyzer
analyzer = VolatilityRegimeAnalyzer()
regime_df = analyzer.identify_volatility_regimes(df)
```

---

### 3. Strategy Module (`strategies/base_strategy.py`)

**Purpose**: Implement trading strategies

**Base Class**: `BaseStrategy`
- Abstract method: `generate_signals()` - must return DataFrame with 'signal' and 'strength' columns

**Implemented Strategies**:

1. **MeanReversionStrategy**
   - Entry: Z-score < -2.0 (long) or > +2.0 (short)
   - Exit: Z-score returns to ±0.5
   - Parameters: lookback=24h, entry_threshold=2.0, exit_threshold=0.5

2. **MomentumStrategy**
   - Entry: EMA crossover + momentum + RSI filter
   - Exit: EMA reversal or RSI extreme
   - Parameters: fast_period=12h, slow_period=48h, momentum_threshold=0.02

3. **VolatilityArbitrageStrategy**
   - Entry: Volatility z-score > 2.0 (short) or < -2.0 (long)
   - Exit: Volatility returns to normal
   - Parameters: vol_lookback=168h, vol_spike_threshold=2.0

**Usage**:
```python
from strategies.base_strategy import MeanReversionStrategy
strategy = MeanReversionStrategy(params={'lookback': 24})
signals = strategy.generate_signals(data)
```

---

### 4. Backtesting Engine (`backtesting/engine.py`)

**Purpose**: Vectorized backtesting with realistic fees and slippage

**Key Classes**:
- `BacktestEngine`: Main backtesting engine
- `BacktestConfig`: Configuration dataclass
- `Trade`: Trade record dataclass

**Key Methods**:
- `backtest_strategy()`: Run backtest on strategy signals
- `_calculate_metrics()`: Calculate performance metrics

**Configuration**:
- Initial Capital: $10,000
- Max Leverage: 20x
- Fee Rate: 0.0001% (Privex)
- Slippage: 5 basis points
- Stop Loss: 5% default
- Max Drawdown: 30%

**Usage**:
```python
from backtesting.engine import BacktestEngine, BacktestConfig
config = BacktestConfig(initial_capital=10000.0, max_leverage=20.0)
engine = BacktestEngine(config)
results = engine.backtest_strategy(data, signals, symbol='DOGE/USDT:USDT')
```

**Output Metrics**:
- total_return, sharpe_ratio, sortino_ratio
- max_drawdown, win_rate, profit_factor
- total_trades, avg_win, avg_loss

---

### 5. Risk Management (`risk_management.py`)

**Purpose**: Position sizing, stop-loss, drawdown limits, risk-of-ruin

**Key Classes**:
- `RiskManager`: Main risk manager

**Key Methods**:
- `calculate_position_size()`: Optimal position sizing
- `calculate_stop_loss()`: Dynamic stop loss calculation
- `calculate_take_profit()`: Risk-reward based take profit
- `calculate_risk_of_ruin()`: Probability of ruin calculation
- `calculate_max_drawdown()`: Drawdown statistics
- `check_portfolio_limits()`: Portfolio-level risk checks

**Usage**:
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

---

### 6. Main Orchestrator (`main.py`)

**Purpose**: Run complete analysis pipeline

**Key Classes**:
- `MemecoinStrategySystem`: Main system orchestrator

**Key Methods**:
- `fetch_data()`: Phase 1 - Data collection
- `analyze_volatility()`: Phase 2 - Volatility analysis
- `run_full_backtest()`: Phase 3 - Strategy backtesting
- `generate_report()`: Phase 4 - Report generation
- `run_full_pipeline()`: Run all phases

**Usage**:
```python
from main import MemecoinStrategySystem
system = MemecoinStrategySystem()
system.run_full_pipeline()
```

---

## Research Documents

### STRATEGY_BLUEPRINT.md
Complete strategy documentation including:
- Entry/exit signals for each strategy
- Position sizing formulas
- Risk-of-ruin guardrails
- Expected performance metrics
- Implementation checklist

### VOLATILITY_ANALYSIS.md
Volatility regime findings:
- Regime classification methodology
- Spike detection and decay patterns
- Trading implications

### CORRELATION_STUDY.md
Cross-asset correlation analysis:
- Correlation clusters
- Dynamic correlation patterns
- Portfolio construction rules

### BACKTEST_REPORT.md (Generated)
Backtest results summary with:
- Performance metrics per strategy per symbol
- Aggregate statistics
- Detailed trade-by-trade analysis

---

## Data Files

### Historical Data (`data/*.csv`)
Format: `{SYMBOL}_{TIMEFRAME}.csv`
- Columns: timestamp, open, high, low, close, volume
- Index: timestamp (datetime)

### Metadata (`data/metadata.json`)
- Fetched symbols
- Timestamp
- Timeframe
- Success/failure status

### Analysis Results (`research/*.json`)
- `volatility_analysis.json`: Volatility statistics per symbol
- `backtest_results.json`: Backtest performance metrics

---

## Quick Reference: Key Parameters

**Portfolio**:
- Initial Capital: $10,000
- Max Leverage: 20x
- Fee Rate: 0.0001% (Privex)
- Max Position Size: 25% of capital
- Max Portfolio Risk: 2% per trade

**Risk Limits**:
- Max Drawdown: 30%
- Stop Loss: 5% (mean reversion), 3% (momentum)
- Take Profit: 2:1 risk-reward minimum

**Target Assets**:
- Primary: DOGE, SHIB, PEPE, WIF, BONK
- Extended: FLOKI, BOME, MEME, BRETT, TURBO, etc.

---

## Usage Examples

### Fetch Data
```bash
python data/fetch_data.py
```

### Analyze Volatility
```bash
python analysis/volatility_regimes.py
```

### Run Full Pipeline
```bash
python main.py
```

### Run Custom Backtest
```python
from main import MemecoinStrategySystem
from strategies.base_strategy import MeanReversionStrategy

system = MemecoinStrategySystem()
data = system.fetcher.load_data('DOGE/USDT:USDT')
strategy = MeanReversionStrategy()
results = system.backtest_strategy(strategy, 'DOGE/USDT:USDT', data)
print(f"Return: {results['total_return']:.2f}%")
print(f"Sharpe: {results['sharpe_ratio']:.2f}")
```

---

## Notes for AI Agents

1. **Data Access**: All data is stored in `data/` directory as CSV files
2. **Strategy Extension**: Inherit from `BaseStrategy` and implement `generate_signals()`
3. **Backtesting**: Use `BacktestEngine` with `BacktestConfig` for consistent testing
4. **Risk Management**: Always use `RiskManager` for position sizing and risk checks
5. **Research Updates**: Research documents are updated as analysis runs

---

*Last Updated: 2026-01-26*
