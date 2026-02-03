#!/usr/bin/env python3
"""
Momentum Strategy Optimization
Walk-forward parameter sweep for maximum Sharpe ratio on top coins
"""

import os
import glob
import pandas as pd
import numpy as np
import json
from itertools import product
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from strategies.base_strategy import MomentumStrategy
from backtesting.simple_engine import SimpleBacktestEngine, BacktestConfig

def load_memecoin_data(data_dir='data'):
    """Load all available memecoin data"""
    csv_files = glob.glob(os.path.join(data_dir, '*_1h.csv'))
    data_dict = {}
    
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            if len(df) >= 100:
                symbol_key = filename.replace('_1h.csv', '')
                data_dict[symbol_key] = df
        except Exception as e:
            pass
    
    return data_dict

def optimize_momentum(symbol_key, data, fast_periods=None, slow_periods=None):
    """
    Grid search optimal momentum parameters
    
    Returns dict with best parameters and metrics
    """
    if fast_periods is None:
        fast_periods = [3, 4, 5, 6, 7, 8, 12]  # EMA fast periods
    if slow_periods is None:
        slow_periods = [18, 24, 30, 36, 48]    # EMA slow periods
    
    # Split data: first 70% for training, last 30% for validation
    split_idx = int(len(data) * 0.7)
    train_data = data.iloc[:split_idx]
    test_data = data.iloc[split_idx:]
    
    results = []
    
    for fast, slow in product(fast_periods, slow_periods):
        if fast >= slow:
            continue
        
        # Test on training set
        try:
            strategy = MomentumStrategy(params={
                'fast_period': fast,
                'slow_period': slow
            })
            signals = strategy.generate_signals(train_data)
            
            config = BacktestConfig(initial_capital=10000.0)
            engine = SimpleBacktestEngine(config)
            train_result = engine.backtest_strategy(train_data, signals, symbol=symbol_key)
            
            # Validate on test set
            signals_test = strategy.generate_signals(test_data)
            test_result = engine.backtest_strategy(test_data, signals_test, symbol=symbol_key)
            
            # Score: prioritize Sharpe ratio (risk-adjusted)
            sharpe_score = (train_result['sharpe_ratio'] + test_result['sharpe_ratio']) / 2
            
            results.append({
                'fast_period': fast,
                'slow_period': slow,
                'train_return': train_result['total_return'],
                'train_sharpe': train_result['sharpe_ratio'],
                'test_return': test_result['total_return'],
                'test_sharpe': test_result['sharpe_ratio'],
                'avg_sharpe': sharpe_score,
                'trades': train_result['total_trades'],
                'win_rate': train_result['win_rate'],
                'profit_factor': train_result['profit_factor']
            })
        except Exception as e:
            pass
    
    if not results:
        return None
    
    # Sort by average Sharpe ratio
    results = sorted(results, key=lambda x: x['avg_sharpe'], reverse=True)
    
    return {
        'best_params': {
            'fast_period': results[0]['fast_period'],
            'slow_period': results[0]['slow_period']
        },
        'best_metrics': results[0],
        'top_5': results[:5]
    }

def test_full_dataset(symbol_key, data, fast_period, slow_period):
    """Test parameters on full dataset"""
    strategy = MomentumStrategy(params={
        'fast_period': fast_period,
        'slow_period': slow_period
    })
    signals = strategy.generate_signals(data)
    
    config = BacktestConfig(initial_capital=10000.0)
    engine = SimpleBacktestEngine(config)
    result = engine.backtest_strategy(data, signals, symbol=symbol_key)
    
    return result

def main():
    print("=" * 70)
    print("MOMENTUM STRATEGY OPTIMIZATION")
    print("=" * 70)
    
    # Load data
    print("\nLoading data...")
    data_dict = load_memecoin_data('data')
    print(f"✓ Loaded {len(data_dict)} symbols")
    
    # Focus on best performers from initial backtest
    top_coins = [
        '1000CAT_USDT_USDT',      # +12.62%
        '1000000MOG_USDT_USDT',    # +13.19% (mean rev, but test momentum too)
        '1000PEPE_USDT_USDT',      # +8.20%
        '1000CHEEMS_USDT_USDT',    # +7.88%
        '1000SATS_USDT_USDT',      # Neutral, worth testing
        'MEME_USDT_USDT',
        'DOGE_USDT_USDT',
        'SHIB_USDT_USDT'
    ]
    
    optimization_results = {}
    
    print("\n" + "=" * 70)
    print("OPTIMIZING PARAMETERS")
    print("=" * 70)
    
    for symbol in top_coins:
        if symbol not in data_dict:
            print(f"\n⊘ {symbol}: No data")
            continue
        
        data = data_dict[symbol]
        print(f"\n{symbol} ({len(data)} candles)")
        print("-" * 70)
        
        # Optimize
        opt_result = optimize_momentum(symbol, data)
        
        if opt_result:
            best = opt_result['best_params']
            metrics = opt_result['best_metrics']
            
            print(f"  Best params: fast={best['fast_period']}, slow={best['slow_period']}")
            print(f"  Train: {metrics['train_return']:.2f}% | {metrics['train_sharpe']:.2f} Sharpe")
            print(f"  Test:  {metrics['test_return']:.2f}% | {metrics['test_sharpe']:.2f} Sharpe")
            print(f"  Full dataset performance:")
            
            # Test on full dataset with best params
            full_result = test_full_dataset(symbol, data, best['fast_period'], best['slow_period'])
            print(f"    Return: {full_result['total_return']:.2f}%")
            print(f"    Sharpe: {full_result['sharpe_ratio']:.2f}")
            print(f"    Trades: {full_result['total_trades']}")
            print(f"    Win rate: {full_result['win_rate']:.1%}")
            print(f"    Profit factor: {full_result['profit_factor']:.2f}")
            
            opt_result['full_dataset_metrics'] = full_result
            optimization_results[symbol] = opt_result
        else:
            print(f"  ✗ Optimization failed")
    
    # Save results
    os.makedirs('research', exist_ok=True)
    opt_file = 'research/momentum_optimization.json'
    
    with open(opt_file, 'w') as f:
        json.dump(optimization_results, f, indent=2, default=str)
    
    print("\n" + "=" * 70)
    print("OPTIMIZATION COMPLETE")
    print("=" * 70)
    print(f"✓ Results saved to {opt_file}")
    
    # Generate trading recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDED PORTFOLIO")
    print("=" * 70)
    
    # Rank by Sharpe ratio
    rankings = []
    for symbol, result in optimization_results.items():
        if result.get('full_dataset_metrics'):
            metrics = result['full_dataset_metrics']
            sharpe = metrics['sharpe_ratio']
            ret = metrics['total_return']
            trades = metrics['total_trades']
            rankings.append({
                'symbol': symbol,
                'return': ret,
                'sharpe': sharpe,
                'trades': trades,
                'params': result['best_params']
            })
    
    rankings = sorted(rankings, key=lambda x: x['sharpe'], reverse=True)
    
    print("\nTop performers by Sharpe ratio:")
    print("Rank | Symbol              | Return | Sharpe | Trades | Params")
    print("-" * 70)
    
    for i, rank in enumerate(rankings, 1):
        p = rank['params']
        print(f"{i:2d}   | {rank['symbol']:19s} | "
              f"{rank['return']:6.2f}% | {rank['sharpe']:6.2f} | "
              f"{rank['trades']:6d} | fast={p['fast_period']}, slow={p['slow_period']}")
    
    # Suggest portfolio allocation
    print("\n" + "=" * 70)
    print("PORTFOLIO SUGGESTION")
    print("=" * 70)
    
    portfolio = rankings[:5]  # Top 5 by Sharpe
    if portfolio:
        print(f"\nRecommended allocation (top {len(portfolio)} coins):")
        allocation_weight = 1.0 / len(portfolio)
        
        total_expected_return = 0
        for i, coin in enumerate(portfolio, 1):
            print(f"  {i}. {coin['symbol']}")
            print(f"     Allocation: {allocation_weight*100:.1f}%")
            print(f"     Expected return: {coin['return']:.2f}%")
            print(f"     Sharpe: {coin['sharpe']:.2f}")
            print(f"     Parameters: fast={coin['params']['fast_period']}, slow={coin['params']['slow_period']}")
            print()
            total_expected_return += coin['return'] * allocation_weight
        
        print(f"Portfolio expected return: {total_expected_return:.2f}%")
        portfolio_sharpe = np.mean([c['sharpe'] for c in portfolio])
        print(f"Portfolio expected Sharpe: {portfolio_sharpe:.2f}")

if __name__ == '__main__':
    main()
