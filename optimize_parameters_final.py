#!/usr/bin/env python3
"""
Final Parameter Optimization
Test momentum threshold, EMA combinations, and entry/exit triggers
Find the best signal quality tuning
"""

import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent))

from strategies.base_strategy import MomentumStrategy
from backtesting.simple_engine import SimpleBacktestEngine, BacktestConfig

def load_data():
    csv_files = glob.glob('data/*_1h.csv')
    data_dict = {}
    
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            if len(df) >= 100:
                symbol_key = os.path.basename(filepath).replace('_1h.csv', '')
                data_dict[symbol_key] = df
        except:
            pass
    
    return data_dict

def optimize_momentum_threshold(data_dict):
    """
    Test different momentum signal thresholds
    Higher threshold = fewer, higher-quality signals
    """
    
    print("\n" + "=" * 90)
    print("MOMENTUM THRESHOLD OPTIMIZATION")
    print("=" * 90)
    
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30}
    }
    
    thresholds = [0.3, 0.5, 0.7, 1.0, 1.2, 1.5, 2.0]
    
    print(f"\n{'Threshold':<12} | {'Avg Return':<12} | {'Avg Sharpe':<12} | {'Avg Trades':<12} | {'Win Rate':<12}")
    print("-" * 90)
    
    results = {}
    
    for threshold in thresholds:
        coin_results = []
        
        for symbol, params in portfolio.items():
            if symbol not in data_dict:
                continue
            
            data = data_dict[symbol]
            strategy = MomentumStrategy(params=params)
            signals = strategy.generate_signals(data)
            
            # Filter signals by threshold
            signals_filtered = signals.copy()
            signals_filtered.loc[signals_filtered['strength'].abs() < threshold, 'signal'] = 0
            
            engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
            result = engine.backtest_strategy(data, signals_filtered, symbol=symbol)
            
            # Scale for 5x leverage
            scaled_return = result['total_return'] * (0.20 * 5)
            scaled_sharpe = result['sharpe_ratio'] * 0.975
            
            coin_results.append({
                'return': scaled_return,
                'sharpe': scaled_sharpe,
                'trades': result['total_trades'],
                'win_rate': result['win_rate']
            })
        
        avg_return = np.mean([r['return'] for r in coin_results])
        avg_sharpe = np.mean([r['sharpe'] for r in coin_results])
        avg_trades = np.mean([r['trades'] for r in coin_results])
        avg_wr = np.mean([r['win_rate'] for r in coin_results])
        
        results[threshold] = {
            'return': avg_return,
            'sharpe': avg_sharpe,
            'trades': avg_trades,
            'win_rate': avg_wr
        }
        
        print(f"{threshold:<12.1f} | {avg_return:>10.2f}% | {avg_sharpe:>10.2f}  | {avg_trades:>10.0f}  | {avg_wr:>10.1%}")
    
    # Find best by Sharpe
    best = max(results.items(), key=lambda x: x[1]['sharpe'])
    
    print(f"\n✓ Best threshold: {best[0]} (Sharpe {best[1]['sharpe']:.2f})")
    
    return best[0], results

def optimize_ema_periods(data_dict):
    """
    Test different EMA period combinations
    Look for faster/slower momentum capture
    """
    
    print("\n" + "=" * 90)
    print("EMA PERIOD OPTIMIZATION (for each coin)")
    print("=" * 90)
    
    symbol = '1000SATS_USDT_USDT'  # Test on best performer
    
    if symbol not in data_dict:
        print("Data not available")
        return
    
    data = data_dict[symbol]
    
    fast_periods = [2, 3, 4, 5, 6, 8]
    slow_periods = [20, 24, 30, 36, 48]
    
    print(f"\nTesting on {symbol}")
    print(f"\n{'Fast':<6} | {'Slow':<6} | {'Return':<10} | {'Sharpe':<8} | {'Trades':<8} | {'Win%':<8}")
    print("-" * 70)
    
    best_result = None
    best_sharpe = -999
    
    for fast in fast_periods:
        for slow in slow_periods:
            if fast >= slow:
                continue
            
            strategy = MomentumStrategy(params={'fast_period': fast, 'slow_period': slow})
            signals = strategy.generate_signals(data)
            
            engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
            result = engine.backtest_strategy(data, signals, symbol=symbol)
            
            # Scale for 5x leverage
            scaled_return = result['total_return'] * (0.20 * 5)
            scaled_sharpe = result['sharpe_ratio'] * 0.975
            
            if scaled_sharpe > best_sharpe:
                best_sharpe = scaled_sharpe
                best_result = (fast, slow, result)
            
            print(f"{fast:<6} | {slow:<6} | {scaled_return:>8.2f}% | {scaled_sharpe:>6.2f}  | {result['total_trades']:>6.0f}  | {result['win_rate']:>6.1%}")
    
    print(f"\n✓ Best EMA: fast={best_result[0]}, slow={best_result[1]} (Sharpe {best_sharpe:.2f})")
    
    return best_result[0], best_result[1], best_result[2]

def test_combined_optimization(data_dict, best_threshold, best_fast, best_slow):
    """
    Test the best combined parameters on all 5 portfolio coins
    """
    
    print("\n" + "=" * 90)
    print("COMBINED OPTIMIZATION TEST")
    print("=" * 90)
    
    portfolio = {
        '1000SATS_USDT_USDT': (best_fast, best_slow),
        '1000PEPE_USDT_USDT': (best_fast, best_slow),
        '1000000MOG_USDT_USDT': (best_fast, best_slow),
        '1000CHEEMS_USDT_USDT': (best_fast, best_slow),
        '1000CAT_USDT_USDT': (best_fast, best_slow)
    }
    
    print(f"\nUsing threshold: {best_threshold}")
    print(f"Using EMA periods: fast={best_fast}, slow={best_slow}")
    
    results = []
    
    for symbol, (fast, slow) in portfolio.items():
        if symbol not in data_dict:
            continue
        
        data = data_dict[symbol]
        strategy = MomentumStrategy(params={'fast_period': fast, 'slow_period': slow})
        signals = strategy.generate_signals(data)
        
        # Apply threshold filter
        signals_filtered = signals.copy()
        signals_filtered.loc[signals_filtered['strength'].abs() < best_threshold, 'signal'] = 0
        
        engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
        result = engine.backtest_strategy(data, signals_filtered, symbol=symbol)
        
        # Scale for 5x leverage
        scaled_return = result['total_return'] * (0.20 * 5)
        scaled_sharpe = result['sharpe_ratio'] * 0.975
        
        results.append({
            'symbol': symbol,
            'return': scaled_return,
            'sharpe': scaled_sharpe,
            'trades': result['total_trades'],
            'win_rate': result['win_rate']
        })
        
        print(f"{symbol:<25} | {scaled_return:>8.2f}% | {scaled_sharpe:>6.2f}  | {result['total_trades']:>6.0f}  | {result['win_rate']:>6.1%}")
    
    avg_return = np.mean([r['return'] for r in results])
    avg_sharpe = np.mean([r['sharpe'] for r in results])
    
    print(f"\n{'Portfolio Total':<25} | {avg_return:>8.2f}% | {avg_sharpe:>6.2f}")
    
    return results, avg_return, avg_sharpe

def main():
    data_dict = load_data()
    print(f"Loaded {len(data_dict)} coins")
    
    # 1. Find optimal threshold
    best_threshold, threshold_results = optimize_momentum_threshold(data_dict)
    
    # 2. Find optimal EMA periods
    best_fast, best_slow, ema_result = optimize_ema_periods(data_dict)
    
    # 3. Test combined
    combined_results, combined_return, combined_sharpe = test_combined_optimization(
        data_dict, best_threshold, best_fast, best_slow
    )
    
    # Summary
    print("\n" + "=" * 90)
    print("FINAL OPTIMIZED CONFIGURATION")
    print("=" * 90)
    
    print(f"\n📊 Signal Generation:")
    print(f"  Fast EMA period: {best_fast}h")
    print(f"  Slow EMA period: {best_slow}h")
    print(f"  Momentum threshold: {best_threshold:.1f}σ")
    
    print(f"\n💰 Expected Performance (with 5x leverage):")
    print(f"  Portfolio Return: {combined_return:.2f}%")
    print(f"  Sharpe Ratio: {combined_sharpe:.2f}")
    
    # Save
    output = {
        'optimal_config': {
            'fast_ema': best_fast,
            'slow_ema': best_slow,
            'momentum_threshold': best_threshold,
            'leverage': 5,
            'allocation_per_coin': 0.20
        },
        'expected_performance': {
            'return': combined_return,
            'sharpe': combined_sharpe
        },
        'threshold_sweep': {str(k): v for k, v in threshold_results.items()},
        'per_coin_results': [
            {
                'symbol': r['symbol'],
                'return': r['return'],
                'sharpe': r['sharpe'],
                'trades': r['trades']
            }
            for r in combined_results
        ]
    }
    
    with open('research/optimized_config.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Full results saved to research/optimized_config.json")

if __name__ == '__main__':
    main()
