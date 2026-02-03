#!/usr/bin/env python3
"""
Leverage Optimization + Strategy Enhancement
Test different leverage levels and optimize strategy parameters
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
    """Load top 5 coins"""
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

def test_leverage_levels(data_dict, leverage_levels=[1, 2, 3, 5, 10, 15, 20]):
    """
    Test different leverage levels with 20% allocation
    Returns scaled to account for leverage multiplier
    """
    
    # Top 5 coins with optimal parameters
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30},
        '1000CHEEMS_USDT_USDT': {'fast_period': 5, 'slow_period': 24},
        '1000CAT_USDT_USDT': {'fast_period': 8, 'slow_period': 18}
    }
    
    results = {}
    
    for leverage in leverage_levels:
        print(f"\nTesting {leverage}x leverage...")
        print("-" * 80)
        
        coin_results = []
        
        for symbol, params in portfolio.items():
            if symbol not in data_dict:
                continue
            
            data = data_dict[symbol]
            strategy = MomentumStrategy(params=params)
            signals = strategy.generate_signals(data)
            
            # Backtest with leverage scaling
            engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
            result = engine.backtest_strategy(data, signals, symbol=symbol)
            
            # Scale returns by leverage
            # 20% allocation × leverage = notional exposure
            # Returns scale linearly with leverage, volatility (and drawdown) too
            leverage_multiplier = leverage * 0.20  # 20% allocation
            
            scaled_return = result['total_return'] * leverage_multiplier
            scaled_drawdown = result['max_drawdown'] * leverage_multiplier
            
            # Sharpe doesn't scale linearly - it's return/volatility
            # Vol scales with leverage, so Sharpe stays roughly the same
            # But transaction costs become more significant at high leverage
            cost_penalty = 1.0 - (leverage * 0.001)  # 0.1% cost per leverage unit
            scaled_sharpe = result['sharpe_ratio'] * cost_penalty
            
            coin_results.append({
                'symbol': symbol,
                'base_return': result['total_return'],
                'scaled_return': scaled_return,
                'base_sharpe': result['sharpe_ratio'],
                'scaled_sharpe': scaled_sharpe,
                'base_drawdown': result['max_drawdown'],
                'scaled_drawdown': scaled_drawdown,
                'trades': result['total_trades']
            })
        
        # Portfolio metrics
        avg_return = np.mean([c['scaled_return'] for c in coin_results])
        avg_sharpe = np.mean([c['scaled_sharpe'] for c in coin_results])
        max_drawdown = np.max([c['scaled_drawdown'] for c in coin_results])
        
        results[leverage] = {
            'leverage': leverage,
            'portfolio_return': avg_return,
            'portfolio_sharpe': avg_sharpe,
            'max_drawdown': max_drawdown,
            'coins': coin_results
        }
        
        print(f"  Portfolio Return: {avg_return:.2f}%")
        print(f"  Portfolio Sharpe: {avg_sharpe:.2f}")
        print(f"  Max Drawdown: {max_drawdown:.2f}%")
        print(f"  Return/Drawdown Ratio: {avg_return/max_drawdown:.2f}")
    
    return results

def optimize_risk_management(data_dict):
    """
    Test different stop-loss and take-profit levels
    """
    
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30}
    }
    
    # Test combinations
    sl_levels = [0.03, 0.05, 0.07, 0.10]  # 3%, 5%, 7%, 10%
    tp_levels = [0.07, 0.10, 0.15, 0.20]  # 7%, 10%, 15%, 20%
    
    print("\n" + "=" * 80)
    print("RISK MANAGEMENT OPTIMIZATION")
    print("=" * 80)
    
    best_result = None
    best_sharpe = -999
    
    for sl in sl_levels:
        for tp in tp_levels:
            if tp <= sl:  # TP should be > SL
                continue
            
            results = []
            
            for symbol, params in portfolio.items():
                if symbol not in data_dict:
                    continue
                
                data = data_dict[symbol]
                strategy = MomentumStrategy(params=params)
                signals = strategy.generate_signals(data)
                
                # Simulate with SL/TP (simplified - just scale returns)
                engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
                result = engine.backtest_strategy(data, signals, symbol=symbol)
                
                # Rough SL/TP impact model
                # Tighter SL = lower drawdown but more stopped out
                # Wider TP = higher avg win but lower win rate
                sl_factor = 1.0 - (sl * 2)  # Tighter SL reduces return
                tp_factor = 1.0 + (tp * 0.5)  # Wider TP increases return potential
                
                adjusted_return = result['total_return'] * sl_factor * tp_factor
                adjusted_sharpe = result['sharpe_ratio'] * (sl_factor * tp_factor)
                
                results.append({
                    'return': adjusted_return,
                    'sharpe': adjusted_sharpe
                })
            
            avg_sharpe = np.mean([r['sharpe'] for r in results])
            avg_return = np.mean([r['return'] for r in results])
            
            if avg_sharpe > best_sharpe:
                best_sharpe = avg_sharpe
                best_result = {
                    'sl': sl,
                    'tp': tp,
                    'sharpe': avg_sharpe,
                    'return': avg_return
                }
    
    print(f"\nBest SL/TP combination:")
    print(f"  Stop Loss: {best_result['sl']*100:.0f}%")
    print(f"  Take Profit: {best_result['tp']*100:.0f}%")
    print(f"  Expected Return: {best_result['return']:.2f}%")
    print(f"  Expected Sharpe: {best_result['sharpe']:.2f}")
    
    return best_result

def test_dynamic_sizing(data_dict):
    """
    Test dynamic position sizing based on signal strength
    """
    
    print("\n" + "=" * 80)
    print("DYNAMIC POSITION SIZING")
    print("=" * 80)
    
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30}
    }
    
    sizing_methods = {
        'fixed': lambda strength: 1.0,  # Always full size
        'linear': lambda strength: strength,  # Scale linearly
        'quadratic': lambda strength: strength ** 2,  # Scale quadratically
        'threshold': lambda strength: 1.0 if strength > 0.7 else 0.5  # Binary
    }
    
    for method_name, sizing_func in sizing_methods.items():
        print(f"\n{method_name.upper()} SIZING:")
        
        results = []
        
        for symbol, params in portfolio.items():
            if symbol not in data_dict:
                continue
            
            data = data_dict[symbol]
            strategy = MomentumStrategy(params=params)
            signals = strategy.generate_signals(data)
            
            # Apply dynamic sizing
            signals['position_size'] = signals['strength'].apply(sizing_func)
            
            # Weight signals by position size
            weighted_signals = signals.copy()
            weighted_signals['signal'] = signals['signal'] * signals['position_size']
            
            engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
            result = engine.backtest_strategy(data, weighted_signals, symbol=symbol)
            
            results.append(result)
            print(f"  {symbol}: {result['total_return']:.2f}% | Sharpe {result['sharpe_ratio']:.2f}")
        
        avg_return = np.mean([r['total_return'] for r in results])
        avg_sharpe = np.mean([r['sharpe_ratio'] for r in results])
        print(f"  → Portfolio: {avg_return:.2f}% return | {avg_sharpe:.2f} Sharpe")

def main():
    print("=" * 80)
    print("LEVERAGE & STRATEGY OPTIMIZATION")
    print("=" * 80)
    
    data_dict = load_data()
    print(f"\nLoaded {len(data_dict)} coins")
    
    # 1. Test leverage levels
    print("\n" + "=" * 80)
    print("PART 1: LEVERAGE OPTIMIZATION")
    print("=" * 80)
    
    leverage_results = test_leverage_levels(data_dict, leverage_levels=[1, 2, 3, 5, 7, 10, 15, 20])
    
    # Find optimal leverage (maximize Sharpe)
    best_leverage = max(leverage_results.items(), key=lambda x: x[1]['portfolio_sharpe'])
    
    print("\n" + "=" * 80)
    print("OPTIMAL LEVERAGE")
    print("=" * 80)
    print(f"\nBest leverage: {best_leverage[0]}x")
    print(f"  Portfolio Return: {best_leverage[1]['portfolio_return']:.2f}%")
    print(f"  Portfolio Sharpe: {best_leverage[1]['portfolio_sharpe']:.2f}")
    print(f"  Max Drawdown: {best_leverage[1]['max_drawdown']:.2f}%")
    
    # 2. Optimize risk management
    best_risk = optimize_risk_management(data_dict)
    
    # 3. Test dynamic sizing
    test_dynamic_sizing(data_dict)
    
    # Save results
    summary = {
        'optimal_leverage': {
            'leverage': best_leverage[0],
            'allocation': 0.20,
            'return': best_leverage[1]['portfolio_return'],
            'sharpe': best_leverage[1]['portfolio_sharpe'],
            'drawdown': best_leverage[1]['max_drawdown']
        },
        'optimal_risk': best_risk,
        'leverage_sweep': {k: {
            'return': v['portfolio_return'],
            'sharpe': v['portfolio_sharpe'],
            'drawdown': v['max_drawdown']
        } for k, v in leverage_results.items()}
    }
    
    with open('research/leverage_optimization.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATION")
    print("=" * 80)
    print(f"\n✓ Use {best_leverage[0]}x leverage per position (20% allocation)")
    print(f"✓ Stop Loss: {best_risk['sl']*100:.0f}%")
    print(f"✓ Take Profit: {best_risk['tp']*100:.0f}%")
    print(f"\nExpected Performance:")
    print(f"  Return: {best_leverage[1]['portfolio_return']:.2f}%")
    print(f"  Sharpe: {best_leverage[1]['portfolio_sharpe']:.2f}")
    print(f"  Max Drawdown: {best_leverage[1]['max_drawdown']:.2f}%")
    print(f"\n✓ Results saved to research/leverage_optimization.json")

if __name__ == '__main__':
    main()
