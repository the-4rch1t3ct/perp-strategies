# Prompt for Clawdbot

Copy and paste this prompt to get started with the memecoin perpetual futures trading system:

---

**I need help with the memecoin perpetual futures trading system located at `/home/botadmin/memecoin-perp-strategies/`.**

**System Overview:**
This is a quantitative trading system for memecoin perpetual futures (DOGE, SHIB, PEPE, WIF, BONK, etc.) with:
- Initial capital: $10,000
- Max leverage: 20x
- Fee rate: 0.0001% (Privex)
- Three strategy prototypes: Mean Reversion, Momentum, Volatility Arbitrage

**Key Documentation:**
- `REFERENCE_INDEX.md` - Complete system reference with all classes, methods, and usage examples
- `STRATEGY_BLUEPRINT.md` - Detailed strategy documentation with entry/exit signals
- `SYSTEM_SUMMARY.md` - Quick overview and usage examples
- `README.md` - Project setup and structure

**Current Status:**
The system is fully built with:
- Data fetching module (CCXT → Binance Futures)
- Volatility analysis tools
- 3 strategy implementations
- Backtesting engine with realistic fees/slippage
- Risk management module

**What I need:**
1. First, read `REFERENCE_INDEX.md` to understand the system architecture
2. Then help me:
   - Fetch historical data for memecoins (90 days, 1h candles)
   - Run initial backtests on the strategies
   - Analyze the results and suggest optimizations
   - Generate performance reports

**Start by:**
1. Reading the reference documentation to understand the system
2. Checking if data has been fetched (look in `data/` directory)
3. If no data exists, help me fetch it using the data module
4. Then run backtests and analyze results

Please start by reading `REFERENCE_INDEX.md` and `SYSTEM_SUMMARY.md` to get familiar with the system, then guide me through the next steps.

---
