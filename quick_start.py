#!/usr/bin/env python3
"""
Quick Start Script
Demonstrates basic usage of the memecoin trading system
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from data.fetch_data import MemecoinDataFetcher
from strategies.base_strategy import MeanReversionStrategy, MomentumStrategy
from backtesting.engine import BacktestEngine, BacktestConfig
from risk_management import RiskManager

def example_data_fetch():
    """Example: Fetch data for a single memecoin"""
    print("Example 1: Fetching data for DOGE/USDT:USDT")
    print("-" * 60)
    
    fetcher = MemecoinDataFetcher()
    
    # Fetch 30 days of 1h data
    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(days=30)
    
    df = fetcher.fetch_ohlcv('DOGE/USDT:USDT', timeframe='1h', since=since)
    
    if not df.empty:
        print(f"✓ Fetched {len(df)} candles")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  Price range: ${df['close'].min():.4f} - ${df['close'].max():.4f}")
    else:
        print("✗ Failed to fetch data")
    
    return df

def example_strategy_signals():
    """Example: Generate trading signals"""
    print("\nExample 2: Generating mean reversion signals")
    print("-" * 60)
    
    fetcher = MemecoinDataFetcher()
    df = fetcher.load_data('DOGE/USDT:USDT', timeframe='1h')
    
    if df.empty:
        print("⚠ No data found. Run data fetch first.")
        return None
    
    strategy = MeanReversionStrategy(params={
        'lookback': 24,
        'entry_threshold': 2.0,
        'exit_threshold': 0.5
    })
    
    signals = strategy.generate_signals(df)
    
    long_signals = (signals['signal'] == 1).sum()
    short_signals = (signals['signal'] == -1).sum()
    
    print(f"✓ Generated signals:")
    print(f"  Long entries: {long_signals}")
    print(f"  Short entries: {short_signals}")
    print(f"  Total signals: {long_signals + short_signals}")
    
    return signals

def example_backtest():
    """Example: Run a backtest"""
    print("\nExample 3: Running backtest")
    print("-" * 60)
    
    fetcher = MemecoinDataFetcher()
    df = fetcher.load_data('DOGE/USDT:USDT', timeframe='1h')
    
    if df.empty:
        print("⚠ No data found. Run data fetch first.")
        return None
    
    strategy = MomentumStrategy()
    signals = strategy.generate_signals(df)
    
    config = BacktestConfig(
        initial_capital=10000.0,
        max_leverage=20.0,
        fee_rate=0.0001,
        slippage_bps=5.0,
        stop_loss_pct=0.05,
        max_drawdown_pct=0.30
    )
    
    engine = BacktestEngine(config)
    results = engine.backtest_strategy(df, signals, symbol='DOGE/USDT:USDT')
    
    print(f"✓ Backtest complete:")
    print(f"  Total Return: {results['total_return']:.2f}%")
    print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {results['sortino_ratio']:.2f}")
    print(f"  Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"  Win Rate: {results['win_rate']*100:.1f}%")
    print(f"  Total Trades: {results['total_trades']}")
    
    return results

def example_risk_management():
    """Example: Risk management calculations"""
    print("\nExample 4: Risk management")
    print("-" * 60)
    
    risk_mgr = RiskManager(
        initial_capital=10000.0,
        max_leverage=20.0,
        max_position_size_pct=0.25
    )
    
    # Calculate position size
    position_size, notional = risk_mgr.calculate_position_size(
        current_capital=10000.0,
        entry_price=0.10,
        stop_loss_price=0.095,  # 5% stop loss
        signal_strength=0.8
    )
    
    print(f"✓ Position sizing:")
    print(f"  Entry Price: $0.10")
    print(f"  Stop Loss: $0.095 (5%)")
    print(f"  Position Size: {position_size:,.0f} units")
    print(f"  Notional Value: ${notional:,.2f}")
    print(f"  Required Margin: ${notional/20:,.2f}")
    
    # Calculate stop loss
    stop_loss = risk_mgr.calculate_stop_loss(
        entry_price=0.10,
        side='long',
        volatility=0.60  # 60% annual vol
    )
    
    print(f"\n  Dynamic Stop Loss: ${stop_loss:.4f}")
    
    return risk_mgr

if __name__ == '__main__':
    print("=" * 60)
    print("MEMECOIN PERPETUAL FUTURES - QUICK START EXAMPLES")
    print("=" * 60)
    
    # Run examples
    try:
        example_data_fetch()
        example_strategy_signals()
        example_backtest()
        example_risk_management()
        
        print("\n" + "=" * 60)
        print("✓ All examples completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Run 'python main.py' for full pipeline")
        print("2. Check 'research/STRATEGY_BLUEPRINT.md' for strategy details")
        print("3. Review 'REFERENCE_INDEX.md' for complete documentation")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
