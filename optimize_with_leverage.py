#!/usr/bin/env python3
"""
Find optimal leverage with 20% allocation
Test different leverage levels and measure risk-adjusted returns
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

def test_leverage_config(data_dict, leverage, allocation=0.20):
    """
    Test a specific leverage configuration
    allocation = fraction of capital per coin
    leverage = multiplier on that allocation
    """
    
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30},
        '1000CHEEMS_USDT_USDT': {'fast_period': 5, 'slow_period': 24},
        '1000CAT_USDT_USDT': {'fast_period': 8, 'slow_period': 18}
    }
    
    results = []
    
    for symbol, params in portfolio.items():
        if symbol not in data_dict:
            continue
        
        data = data_dict[symbol]
        strategy = MomentumStrategy(params=params)
        signals = strategy.generate_signals(data)
        
        engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
        result = engine.backtest_strategy(data, signals, symbol=symbol)
        
        # Scale by effective leverage = allocation × max_leverage
        # If using 20% allocation and 5x leverage → 1x effective (20% × 5 = 1.0)
        effective_leverage = allocation * leverage
        
        # Scaled metrics
        scaled_return = result['total_return'] * effective_leverage
        scaled_drawdown = result['max_drawdown'] * effective_leverage
        
        # Sharpe is mostly independent of leverage (vol scales with leverage)
        # but we apply a small friction cost for higher leverage
        leverage_cost = 1.0 - (leverage * 0.005)  # 0.5% cost per leverage
        scaled_sharpe = result['sharpe_ratio'] * leverage_cost
        
        results.append({
            'symbol': symbol,
            'return': scaled_return,
            'sharpe': scaled_sharpe,
            'drawdown': scaled_drawdown,
            'trades': result['total_trades'],
            'win_rate': result['win_rate']
        })
    
    return results

def find_optimal_leverage(data_dict):
    """
    Test leverages 1x to 20x and find the one with best Sharpe
    """
    
    print("=" * 90)
    print("LEVERAGE OPTIMIZATION (20% allocation per coin)")
    print("=" * 90)
    
    leverage_levels = [1, 2, 3, 4, 5, 7, 10, 15, 20]
    
    print(f"\n{'Leverage':<12} | {'Avg Return':<12} | {'Avg Sharpe':<12} | {'Avg DD':<12} | {'R/R Ratio':<12}")
    print("-" * 90)
    
    results_by_leverage = {}
    
    for leverage in leverage_levels:
        results = test_leverage_config(data_dict, leverage, allocation=0.20)
        
        avg_return = np.mean([r['return'] for r in results])
        avg_sharpe = np.mean([r['sharpe'] for r in results])
        avg_dd = np.mean([r['drawdown'] for r in results])
        
        rr_ratio = avg_return / max(avg_dd, 0.01)  # Return/Drawdown ratio
        
        results_by_leverage[leverage] = {
            'return': avg_return,
            'sharpe': avg_sharpe,
            'drawdown': avg_dd,
            'rr_ratio': rr_ratio,
            'coin_results': results
        }
        
        print(f"{leverage}x         | {avg_return:>10.2f}% | {avg_sharpe:>10.2f}  | {avg_dd:>10.2f}% | {rr_ratio:>10.2f}")
    
    # Find best by Sharpe (risk-adjusted)
    best_sharpe = max(results_by_leverage.items(), key=lambda x: x[1]['sharpe'])
    
    # Find best by return/drawdown (reward-to-risk)
    best_rr = max(results_by_leverage.items(), key=lambda x: x[1]['rr_ratio'])
    
    print("\n" + "=" * 90)
    print("RECOMMENDATIONS")
    print("=" * 90)
    
    print(f"\n✓ Best Sharpe-Adjusted: {best_sharpe[0]}x leverage")
    print(f"  Return: {best_sharpe[1]['return']:.2f}% | Sharpe: {best_sharpe[1]['sharpe']:.2f} | DD: {best_sharpe[1]['drawdown']:.2f}%")
    
    print(f"\n✓ Best Return/Drawdown: {best_rr[0]}x leverage")
    print(f"  Return: {best_rr[1]['return']:.2f}% | Sharpe: {best_rr[1]['sharpe']:.2f} | DD: {best_rr[1]['drawdown']:.2f}%")
    
    # Show per-coin breakdown for best
    print(f"\nPer-coin breakdown (best by Sharpe = {best_sharpe[0]}x):")
    print(f"{'Symbol':<25} | {'Return':<10} | {'Sharpe':<8} | {'Trades':<8}")
    print("-" * 60)
    for coin in best_sharpe[1]['coin_results']:
        print(f"{coin['symbol']:<25} | {coin['return']:>8.2f}% | {coin['sharpe']:>6.2f}  | {coin['trades']:>6.0f}")
    
    return best_sharpe[0], best_sharpe[1], best_rr[0], best_rr[1], results_by_leverage

def main():
    data_dict = load_data()
    print(f"Loaded {len(data_dict)} coins\n")
    
    best_lev_sharpe, best_metrics_sharpe, best_lev_rr, best_metrics_rr, all_results = find_optimal_leverage(data_dict)
    
    # Summary
    print("\n" + "=" * 90)
    print("FINAL RECOMMENDATION")
    print("=" * 90)
    
    print(f"\n📊 Strategy Configuration:")
    print(f"  Allocation: 20% per coin (5 coins)")
    print(f"  Optimal Leverage: {best_lev_sharpe}x (Sharpe-based)")
    print(f"  Alternative: {best_lev_rr}x (Return/Drawdown-based)")
    
    print(f"\n💰 Expected Returns (90-day backtest):")
    print(f"  Return: {best_metrics_sharpe['return']:.2f}%")
    print(f"  Sharpe Ratio: {best_metrics_sharpe['sharpe']:.2f}")
    print(f"  Max Drawdown: {best_metrics_sharpe['drawdown']:.2f}%")
    
    print(f"\n⚠️  Risk Metrics:")
    print(f"  Return/Drawdown: {best_metrics_sharpe['rr_ratio']:.2f}x")
    print(f"  Daily Expected: ~{best_metrics_sharpe['return']/90:.2f}%")
    print(f"  Monthly Expected: ~{best_metrics_sharpe['return']*3.33:.2f}%")
    
    # Save
    output = {
        'optimal_leverage': best_lev_sharpe,
        'optimal_metrics': {
            'return': best_metrics_sharpe['return'],
            'sharpe': best_metrics_sharpe['sharpe'],
            'drawdown': best_metrics_sharpe['drawdown'],
            'rr_ratio': best_metrics_sharpe['rr_ratio']
        },
        'all_leverage_tests': {
            str(k): {
                'return': v['return'],
                'sharpe': v['sharpe'],
                'drawdown': v['drawdown'],
                'rr_ratio': v['rr_ratio']
            }
            for k, v in all_results.items()
        }
    }
    
    with open('research/leverage_final.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Full results saved to research/leverage_final.json")

if __name__ == '__main__':
    main()
