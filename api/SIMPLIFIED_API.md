# Simplified API Response

## Overview

The API now returns only core trading data needed to open and close positions. All calculations (indicators, entry conditions, signal strength, leverage, stop loss, take profit) are done in the backend.

## Response Structure

### Single Symbol Response
```json
{
  "success": true,
  "data": {
    "symbol": "DOGE/USDT:USDT",
    "price": 0.12214,
    "entry_signal": "LONG" | "SHORT" | null,
    "signal_strength": 0.65,
    "leverage": 20.0,
    "stop_loss_price": 0.12050,
    "take_profit_price": 0.12500,
    "exit_signal": "CLOSE_LONG" | "CLOSE_SHORT" | null,
    "data_age_seconds": 45.2
  },
  "timestamp": "2026-01-27T00:00:00",
  "latency_ms": 75.4
}
```

### All Symbols Response
```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "price": 0.12214,
      "entry_signal": "LONG",
      "signal_strength": 0.65,
      "leverage": 20.0,
      "stop_loss_price": 0.12050,
      "take_profit_price": 0.12500,
      "exit_signal": null,
      "data_age_seconds": 45.2
    },
    ...
  ],
  "timestamp": "2026-01-27T00:00:00",
  "latency_ms": 81.4
}
```

## Field Descriptions

- **symbol**: Trading symbol (e.g., "DOGE/USDT:USDT")
- **price**: Current market price
- **entry_signal**: 
  - `"LONG"`: All entry conditions met for long position
  - `"SHORT"`: All entry conditions met for short position
  - `null`: No entry signal (conditions not met)
- **signal_strength**: Confidence level (0.0-1.0), only present if entry_signal exists
- **leverage**: Recommended leverage (10x, 15x, or 20x), only present if entry_signal exists
- **stop_loss_price**: Pre-calculated stop loss level (1.5×ATR from entry price), only present if entry_signal exists
- **take_profit_price**: Pre-calculated take profit level (2.5×ATR from entry price), only present if entry_signal exists
- **exit_signal**: 
  - `"CLOSE_LONG"`: Trend reversal detected - close any LONG positions
  - `"CLOSE_SHORT"`: Trend reversal detected - close any SHORT positions
  - `null`: No exit signal
- **data_age_seconds**: How old the latest candle is (reject if > 120 seconds)

## Backend Calculations

All of the following are calculated in the backend:

1. **Indicators**: EMA fast/slow, RSI, Momentum, ATR, Volume indicators, MACD, Trend Strength, Price Position
2. **Entry Conditions**: All 7 conditions checked (EMA crossover, momentum, RSI, volume, filters, signal strength)
3. **Signal Strength**: Calculated from momentum, volume, trend, RSI (weighted formula)
4. **Leverage Assignment**: Based on signal strength (≥0.65: 20x, 0.35-0.65: 15x, 0.25-0.35: 10x)
5. **Stop Loss**: 1.5×ATR from entry price
6. **Take Profit**: 2.5×ATR from entry price
7. **Exit Signals**: Trend reversal detection (EMA crossover or MACD histogram flip)

## Agent Usage

The trading agent should:
1. Fetch `/indicators` endpoint every 3 minutes
2. Filter symbols where `data_age_seconds` < 120
3. For entries: Use symbols where `entry_signal` is not null
4. Use provided `leverage`, `stop_loss_price`, `take_profit_price` directly
5. Calculate position size: 25% of capital × `signal_strength`
6. For exits: Check `exit_signal` and close matching positions
7. Monitor stop loss/take profit levels from API

## Benefits

- **Simplified**: Agent doesn't need to calculate indicators or check entry conditions
- **Consistent**: All calculations done in one place (backend)
- **Faster**: Less processing on agent side
- **Reliable**: Pre-validated signals reduce errors
- **Maintainable**: Strategy changes only need backend updates

---

**Last Updated**: 2026-01-27
