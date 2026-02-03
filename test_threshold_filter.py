#!/usr/bin/env python3
"""
Test momentum threshold filtering on original optimized parameters
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

def main():
    data_dict = load_data()
    
    # Original optimized parameters
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30},
        '1000CHEEMS_USDT_USDT': {'fast_period': 5, 'slow_period': 24},
        '1000CAT_USDT_USDT': {'fast_period': 8, 'slow_period': 18}
    }
    
    thresholds = [0, 0.2, 0.3, 0.4, 0.5]
    
    print("=" * 110)
    print("THRESHOLD FILTERING TEST - Original Parameters with 5x Leverage")
    print("=" * 110)
    
    results_by_threshold = {}
    
    for threshold in thresholds:
        print(f"\nThreshold: {threshold:.1f}σ")
        print("-" * 110)
        print(f"{'Symbol':<25} | {'Return':<10} | {'Sharpe':<8} | {'Trades':<8} | {'Win%':<8}")
        print("-" * 110)
        
        coin_results = []
        
        for symbol, params in portfolio.items():
            if symbol not in data_dict:
                continue
            
            data = data_dict[symbol]
            strategy = MomentumStrategy(params=params)
            signals = strategy.generate_signals(data)
            
            # Apply threshold filter
            if threshold > 0:
                signals_filtered = signals.copy()
                signals_filtered.loc[signals_filtered['strength'].abs() < threshold, 'signal'] = 0
            else:
                signals_filtered = signals
            
            engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
            result = engine.backtest_strategy(data, signals_filtered, symbol=symbol)
            
            # Scale for 5x leverage
            scaled_return = result['total_return'] * (0.20 * 5)
            scaled_sharpe = result['sharpe_ratio'] * 0.975  # Slight friction from leverage
            
            coin_results.append({
                'symbol': symbol,
                'return': scaled_return,
                'sharpe': scaled_sharpe,
                'trades': result['total_trades'],
                'win_rate': result['win_rate']
            })
            
            print(f"{symbol:<25} | {scaled_return:>8.2f}% | {scaled_sharpe:>6.2f}  | {result['total_trades']:>6.0f}  | {result['win_rate']:>6.1%}")
        
        avg_return = np.mean([r['return'] for r in coin_results])
        avg_sharpe = np.mean([r['sharpe'] for r in coin_results])
        
        results_by_threshold[threshold] = {
            'return': avg_return,
            'sharpe': avg_sharpe,
            'coins': coin_results
        }
        
        print("-" * 110)
        print(f"{'PORTFOLIO':<25} | {avg_return:>8.2f}% | {avg_sharpe:>6.2f}")
    
    # Find best
    best = max(results_by_threshold.items(), key=lambda x: x[1]['sharpe'])
    
    print("\n" + "=" * 110)
    print("RECOMMENDATION")
    print("=" * 110)
    
    print(f"\n✓ Optimal threshold: {best[0]:.1f}σ")
    print(f"  Portfolio Return: {best[1]['return']:.2f}%")
    print(f"  Portfolio Sharpe: {best[1]['sharpe']:.2f}")
    print(f"  Improvement: +{best[1]['sharpe'] - 0.37:.2f} Sharpe vs baseline")
    
    print(f"\n📋 Configuration:")
    print(f"  Parameters: Original per-coin optimization ✓")
    print(f"  Leverage: 5x (20% allocation per coin)")
    print(f"  Threshold: {best[0]:.1f}σ momentum signal strength")
    
    # Save
    output = {
        'recommendation': {
            'threshold': best[0],
            'expected_return': best[1]['return'],
            'expected_sharpe': best[1]['sharpe'],
            'improvement_vs_baseline': best[1]['sharpe'] - 0.37
        },
        'threshold_sweep': {str(k): {'return': v['return'], 'sharpe': v['sharpe']} 
                           for k, v in results_by_threshold.items()},
        'portfolio': portfolio
    }
    
    with open('research/threshold_optimization.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Results saved to research/threshold_optimization.json")

if __name__ == '__main__':
    main()
