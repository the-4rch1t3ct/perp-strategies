# Backtest: Liquidation Cluster Strategy (Stalker)

**Date**: 2026-01-29T15:43:17.920981

**Strategy**: AI_TRADING_AGENT_PROMPT.md (runway, exhaustion, anti-whipsaw)

## Fee comparison

| Metric | 0.03% fee | 0.0001% fee |
|--------|-----------|-------------|
| Total Trades | 36 | 36 |
| Win Rate | 69.44% | 69.44% |
| Total PnL | $-0.72 | $1.38 |
| Total Fees | $2.11 | $0.01 |
| Final Capital | $9999.28 | $10001.38 |
| Return | -0.01% | 0.01% |
| Profit Factor | 0.97 | 1.07 |
| Max Drawdown | -5.29% | -5.28% |

## Note

Signals are synthetic (support/resistance from rolling high/low) because historical
batch API cluster data is not available. Entry/exit rules match the prompt.
