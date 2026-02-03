#!/usr/bin/env python3
"""
Analyze bidirectional trading performance
Compare LONG-only vs SHORT-only vs LONG+SHORT
"""

import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from strategies.base_strategy import MomentumStrategy
from backtesting.simple_engine import SimpleBacktestEngine, BacktestConfig

def analyze_coin(symbol_key, data):
    """
    Test a coin with:
    1. Long-only strategy
    2. Short-only strategy
    3. Bidirectional strategy
    """
    
    # Optimal parameters from latest optimization
    if symbol_key == '1000SATS_USDT_USDT':
        params = {'fast_period': 4, 'slow_period': 30}
    elif symbol_key == '1000PEPE_USDT_USDT':
        params = {'fast_period': 5, 'slow_period': 30}
    elif symbol_key == '1000000MOG_USDT_USDT':
        params = {'fast_period': 12, 'slow_period': 30}
    elif symbol_key == '1000CHEEMS_USDT_USDT':
        params = {'fast_period': 5, 'slow_period': 24}
    elif symbol_key == '1000CAT_USDT_USDT':
        params = {'fast_period': 8, 'slow_period': 18}
    else:
        return None
    
    strategy = MomentumStrategy(params=params)
    signals = strategy.generate_signals(data)
    
    # Test bidirectional (original)
    engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
    bi_result = engine.backtest_strategy(data, signals, symbol=symbol_key)
    
    # Test LONG-ONLY: Convert all shorts to no signal
    signals_long_only = signals.copy()
    signals_long_only.loc[signals_long_only['signal'] == -1, 'signal'] = 0
    long_result = engine.backtest_strategy(data, signals_long_only, symbol=symbol_key)
    
    # Test SHORT-ONLY: Convert all longs to no signal
    signals_short_only = signals.copy()
    signals_short_only.loc[signals_short_only['signal'] == 1, 'signal'] = 0
    short_result = engine.backtest_strategy(data, signals_short_only, symbol=symbol_key)
    
    # Extract breakdown
    long_trades = bi_result.get('long_trades', 0)
    short_trades = bi_result.get('short_trades', 0)
    total_trades = bi_result.get('total_trades', 0)
    
    return {
        'symbol': symbol_key,
        'params': params,
        'bidirectional': bi_result,
        'long_only': long_result,
        'short_only': short_result,
        'long_trades': long_trades,
        'short_trades': short_trades,
        'total_trades': total_trades
    }

def main():
    # Load data
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
    
    # Top 5 coins to analyze
    coins = [
        '1000SATS_USDT_USDT',
        '1000PEPE_USDT_USDT',
        '1000000MOG_USDT_USDT',
        '1000CHEEMS_USDT_USDT',
        '1000CAT_USDT_USDT'
    ]
    
    print("=" * 100)
    print("DIRECTIONAL ANALYSIS: LONG vs SHORT vs BIDIRECTIONAL")
    print("=" * 100)
    
    results = []
    
    for coin in coins:
        if coin not in data_dict:
            continue
        
        print(f"\n{coin}")
        print("-" * 100)
        
        result = analyze_coin(coin, data_dict[coin])
        if result is None:
            print("  ✗ No parameters defined")
            continue
        
        results.append(result)
        
        # Unpack results
        bi = result['bidirectional']
        lo = result['long_only']
        so = result['short_only']
        
        print(f"Parameters: fast={result['params']['fast_period']}, slow={result['params']['slow_period']}")
        print(f"Total trades: {result['total_trades']} (Longs: {result['long_trades']}, Shorts: {result['short_trades']})")
        print()
        print(f"{'Mode':<20} | {'Return':<10} | {'Sharpe':<8} | {'Win%':<8} | {'PF':<6}")
        print("-" * 100)
        print(f"{'LONG-ONLY':<20} | {lo['total_return']:>8.2f}% | {lo['sharpe_ratio']:>7.2f} | {lo['win_rate']*100:>7.1f}% | {lo['profit_factor']:>5.2f}")
        print(f"{'SHORT-ONLY':<20} | {so['total_return']:>8.2f}% | {so['sharpe_ratio']:>7.2f} | {so['win_rate']*100:>7.1f}% | {so['profit_factor']:>5.2f}")
        print(f"{'BIDIRECTIONAL':<20} | {bi['total_return']:>8.2f}% | {bi['sharpe_ratio']:>7.2f} | {bi['win_rate']*100:>7.1f}% | {bi['profit_factor']:>5.2f}")
        print()
        
        # Analysis
        if lo['total_return'] > so['total_return']:
            print(f"✓ LONGS are stronger (+{lo['total_return']-so['total_return']:.2f}%)")
            print(f"  → Recommendation: LONG-ONLY strategy")
        else:
            print(f"✓ SHORTS are stronger (+{so['total_return']-lo['total_return']:.2f}%)")
            print(f"  → Recommendation: SHORT-ONLY strategy")
        
        if bi['total_return'] > max(lo['total_return'], so['total_return']):
            print(f"✓ Bidirectional works best (combines both)")
        else:
            print(f"⚠ Bidirectional underperforms (use directional-only)")
    
    # Summary
    print("\n" + "=" * 100)
    print("PORTFOLIO RECOMMENDATION")
    print("=" * 100)
    
    total_long_return = sum(r['long_only']['total_return'] for r in results) / len(results)
    total_short_return = sum(r['short_only']['total_return'] for r in results) / len(results)
    total_bi_return = sum(r['bidirectional']['total_return'] for r in results) / len(results)
    
    total_long_sharpe = sum(r['long_only']['sharpe_ratio'] for r in results) / len(results)
    total_short_sharpe = sum(r['short_only']['sharpe_ratio'] for r in results) / len(results)
    total_bi_sharpe = sum(r['bidirectional']['sharpe_ratio'] for r in results) / len(results)
    
    print(f"\nAverage across {len(results)} coins:")
    print(f"  LONG-ONLY:       {total_long_return:>7.2f}% return, {total_long_sharpe:>6.2f} Sharpe")
    print(f"  SHORT-ONLY:      {total_short_return:>7.2f}% return, {total_short_sharpe:>6.2f} Sharpe")
    print(f"  BIDIRECTIONAL:   {total_bi_return:>7.2f}% return, {total_bi_sharpe:>6.2f} Sharpe")
    print()
    
    if total_long_return > total_short_return and total_long_return > total_bi_return:
        print("FINAL RECOMMENDATION: Deploy LONG-ONLY momentum strategy")
        print(f"Expected return: +{total_long_return:.2f}%")
        print(f"Expected Sharpe: {total_long_sharpe:.2f}")
    elif total_short_return > total_long_return and total_short_return > total_bi_return:
        print("FINAL RECOMMENDATION: Deploy SHORT-ONLY momentum strategy")
        print(f"Expected return: +{total_short_return:.2f}%")
        print(f"Expected Sharpe: {total_short_sharpe:.2f}")
    else:
        print("FINAL RECOMMENDATION: Deploy BIDIRECTIONAL momentum strategy")
        print(f"Expected return: +{total_bi_return:.2f}%")
        print(f"Expected Sharpe: {total_bi_sharpe:.2f}")
        print("(Shorts add diversification despite lower average win rate)")

if __name__ == '__main__':
    main()
