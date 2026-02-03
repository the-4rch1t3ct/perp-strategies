#!/usr/bin/env python3
"""
Quick backtest runner with corrected symbol handling and signal generation
Tests strategies on actual memecoin data with fixed path handling
"""

import os
import glob
import pandas as pd
import numpy as np
import json
from datetime import datetime
from pathlib import Path

# Add to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simple_engine import SimpleBacktestEngine, BacktestConfig
from strategies.base_strategy import MeanReversionStrategy, MomentumStrategy, VolatilityArbitrageStrategy

def load_memecoin_data(data_dir='data'):
    """Load all available memecoin data"""
    csv_files = glob.glob(os.path.join(data_dir, '*_1h.csv'))
    data_dict = {}
    
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        # Extract symbol from filename (e.g., DOGE_USDT_USDT -> DOGE/USDT:USDT)
        parts = filename.replace('_1h.csv', '').split('_')
        
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            if len(df) >= 100:  # Need at least 100 candles
                symbol_key = filename.replace('_1h.csv', '')
                data_dict[symbol_key] = df
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    
    return data_dict

def run_backtest(symbol_key, data, strategy_name, strategy):
    """Run backtest for single strategy-symbol pair"""
    config = BacktestConfig(
        initial_capital=10000.0,
        max_leverage=20.0,
        fee_rate=0.0001,
        slippage_bps=5.0,
        max_position_size_pct=0.25
    )
    
    try:
        engine = SimpleBacktestEngine(config)
        signals = strategy.generate_signals(data)
        
        # Debug: check signals
        if 'signal' not in signals.columns:
            print(f"  ✗ {strategy_name}: No signal column generated")
            return None
        
        signal_counts = (signals['signal'] != 0).sum()
        if signal_counts == 0:
            print(f"  - {strategy_name}: No signals generated (lookback window too large?)")
            return None
        
        results = engine.backtest_strategy(data, signals, symbol=symbol_key)
        return results
    except Exception as e:
        print(f"  ✗ {strategy_name}: Error - {str(e)[:50]}")
        return None

def main():
    print("=" * 70)
    print("MEMECOIN BACKTEST - CORRECTED VERSION")
    print("=" * 70)
    
    # Load all data
    print("\nLoading memecoin data...")
    data_dict = load_memecoin_data('data')
    print(f"✓ Loaded {len(data_dict)} symbols")
    
    # Initialize strategies
    strategies = {
        'mean_reversion': MeanReversionStrategy(params={'lookback': 12}),  # Reduced from 24
        'momentum': MomentumStrategy(params={'fast_period': 6, 'slow_period': 24}),
        'volatility_arb': VolatilityArbitrageStrategy(params={'vol_lookback': 48})
    }
    
    # Run backtests
    all_results = {}
    
    for symbol_key in sorted(data_dict.keys())[:8]:  # First 8 coins
        print(f"\nTesting {symbol_key}...")
        symbol_results = {}
        
        df = data_dict[symbol_key]
        print(f"  Data: {len(df)} candles, {df.index[0]} to {df.index[-1]}")
        
        for strategy_name, strategy in strategies.items():
            results = run_backtest(symbol_key, df, strategy_name, strategy)
            
            if results:
                symbol_results[strategy_name] = {
                    'total_return': float(results['total_return']),
                    'sharpe_ratio': float(results['sharpe_ratio']),
                    'sortino_ratio': float(results['sortino_ratio']),
                    'max_drawdown': float(results['max_drawdown']),
                    'win_rate': float(results['win_rate']),
                    'profit_factor': float(results['profit_factor']),
                    'total_trades': int(results['total_trades'])
                }
                print(f"  ✓ {strategy_name}: {results['total_trades']} trades, "
                      f"Return: {results['total_return']:.2f}%, "
                      f"Sharpe: {results['sharpe_ratio']:.2f}")
            else:
                symbol_results[strategy_name] = None
        
        all_results[symbol_key] = symbol_results
    
    # Save results
    os.makedirs('research', exist_ok=True)
    results_file = 'research/backtest_results_corrected.json'
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print("\n" + "=" * 70)
    print(f"✓ Results saved to {results_file}")
    print("=" * 70)
    
    # Print summary
    print("\nSummary Statistics:")
    total_trades = sum(
        r.get('total_trades', 0) for sym in all_results.values() 
        for r in sym.values() if r
    )
    profitable = sum(
        1 for sym in all_results.values() 
        for r in sym.values() if r and r.get('total_return', 0) > 0
    )
    total_tests = sum(1 for sym in all_results.values() for r in sym.values() if r)
    
    print(f"  Total tests: {total_tests}")
    print(f"  Profitable: {profitable} ({profitable/total_tests*100:.1f}%)")
    print(f"  Total trades: {total_trades}")
    
    return all_results

if __name__ == '__main__':
    main()
