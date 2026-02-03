#!/usr/bin/env python3
"""
Estimate volume farming potential at different timeframes
Don't need synthetic data - just scale trade frequency and EMA periods
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

def load_data_1h():
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

def calculate_ema_parameters(timeframe_minutes, base_fast_h, base_slow_h):
    """Scale EMA periods to lower timeframes"""
    hours_per_period = timeframe_minutes / 60.0
    fast_periods = int(base_fast_h / hours_per_period)
    slow_periods = int(base_slow_h / hours_per_period)
    return fast_periods, slow_periods

def main():
    data_dict = load_data_1h()
    print(f"Loaded {len(data_dict)} coins\n")
    
    # Original 1h parameters
    portfolio_1h = {
        '1000SATS_USDT_USDT': (4, 30),
        '1000PEPE_USDT_USDT': (5, 30),
        '1000000MOG_USDT_USDT': (12, 30),
        '1000CHEEMS_USDT_USDT': (5, 24),
        '1000CAT_USDT_USDT': (8, 18)
    }
    
    # Test 1h baseline first
    print("=" * 100)
    print("1H BASELINE (Current)")
    print("=" * 100)
    
    baseline_results = []
    
    for symbol, (fast_h, slow_h) in portfolio_1h.items():
        if symbol not in data_dict:
            continue
        
        data = data_dict[symbol]
        strategy = MomentumStrategy(params={'fast_period': fast_h, 'slow_period': slow_h})
        signals = strategy.generate_signals(data)
        
        engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
        result = engine.backtest_strategy(data, signals, symbol=symbol)
        
        # Scale for 5x leverage
        scaled_return = result['total_return'] * (0.20 * 5)
        
        baseline_results.append({
            'symbol': symbol,
            'return': scaled_return,
            'sharpe': result['sharpe_ratio'] * 0.975,
            'trades': result['total_trades'],
            'win_rate': result['win_rate']
        })
        
        print(f"{symbol:<25} | Return: {scaled_return:>7.2f}% | Trades: {result['total_trades']:>4.0f} | Win%: {result['win_rate']:>5.1%}")
    
    baseline_return = np.mean([r['return'] for r in baseline_results])
    baseline_trades = np.mean([r['trades'] for r in baseline_results])
    baseline_daily_trades = baseline_trades / 90  # Estimate per day
    
    print(f"\nPortfolio Average: {baseline_return:.2f}% return, {baseline_daily_trades:.1f} trades/coin/day")
    
    # Now estimate lower timeframes
    print("\n" + "=" * 100)
    print("TIMEFRAME COMPARISON (Estimated)")
    print("=" * 100)
    
    timeframes = [
        (1, "1m"),
        (5, "5m"),
        (15, "15m"),
        (60, "1h baseline")
    ]
    
    print(f"\n{'Timeframe':<15} | {'EMA Scale':<15} | {'Est. Trades/Day':<18} | {'Est. Daily Trades':<18} | {'Est. Volume':<20}")
    print("-" * 100)
    
    results_summary = {}
    
    for minutes, label in timeframes:
        # Calculate EMA scaling
        fast_scaled_1000sats, slow_scaled_1000sats = calculate_ema_parameters(minutes, 4, 30)
        
        # Estimate trade frequency increase
        # At 1h: 112 trades over 90 days = 1.24 trades/day
        # At 15m: 4x more candles = ~5 trades/day
        # At 5m: 12x more candles = ~15 trades/day
        # At 1m: 60x more candles = ~74 trades/day
        
        frequency_multiplier = 60 / minutes  # How many candles per hour at this TF vs 1h
        
        est_daily_trades_per_coin = baseline_daily_trades * frequency_multiplier
        est_total_daily_trades = est_daily_trades_per_coin * 5  # 5 coins
        
        # Estimate volume
        # Each trade is ~$10k notional (20% × 5x leverage)
        # But some will close quickly, some slow
        # Average position size: $2k (capital allocation)
        est_daily_volume = est_total_daily_trades * 2000
        
        # Return estimate (should decrease slightly with more trades = more slippage)
        # Rough model: return scales with frequency, but friction costs increase
        friction_multiplier = 1.0 - ((frequency_multiplier - 1) * 0.01)  # 1% friction per 10x frequency
        est_return = baseline_return * friction_multiplier
        
        results_summary[minutes] = {
            'label': label,
            'frequency_multiplier': frequency_multiplier,
            'daily_trades_per_coin': est_daily_trades_per_coin,
            'total_daily_trades': est_total_daily_trades,
            'daily_volume': est_daily_volume,
            'est_return': est_return,
            'ema_example': f"{fast_scaled_1000sats}/{slow_scaled_1000sats}"
        }
        
        print(f"{label:<15} | {fast_scaled_1000sats}/{slow_scaled_1000sats}          | {est_daily_trades_per_coin:>16.1f}  | {est_total_daily_trades:>16.1f}  | ${est_daily_volume:>18,.0f}")
    
    # Points farming estimate
    print("\n" + "=" * 100)
    print("PRIVEX POINTS FARMING ESTIMATE")
    print("=" * 100)
    
    print("\nAssuming: 1 PriveX point per $100 notional traded")
    print("\n{'Timeframe':<15} | {'Daily Volume':<20} | {'Daily Points':<18} | {'Monthly Points':<20} | {'Annual Points':<20}")
    print("-" * 100)
    
    for minutes, result in results_summary.items():
        daily_volume = result['daily_volume']
        daily_points = daily_volume / 100
        monthly_points = daily_points * 30
        annual_points = daily_points * 365
        
        print(f"{result['label']:<15} | ${daily_volume:>18,.0f} | {daily_points:>16,.0f} | {monthly_points:>18,.0f} | {annual_points:>18,.0f}")
    
    # Recommendation
    print("\n" + "=" * 100)
    print("RECOMMENDATION")
    print("=" * 100)
    
    print(f"\n✅ 15-MINUTE CANDLES (Recommended for volume farming)")
    print(f"   EMA periods: {4*4}/{30*4} = 16/120")
    print(f"   Expected daily trades: {results_summary[15]['total_daily_trades']:.0f} across 5 coins")
    print(f"   Daily volume: ${results_summary[15]['daily_volume']:,.0f}")
    print(f"   Expected daily points: {results_summary[15]['daily_volume']/100:,.0f}")
    print(f"   Expected return: {results_summary[15]['est_return']:.2f}%")
    print(f"   ✓ Good balance between volume and returns")
    print(f"   ✓ Not too noisy (still has good signal quality)")
    print(f"   ✓ Manageable API load")
    
    print(f"\n⚡ 5-MINUTE CANDLES (Max volume)")
    print(f"   EMA periods: {4*12}/{30*12} = 48/360")
    print(f"   Expected daily trades: {results_summary[5]['total_daily_trades']:.0f} across 5 coins")
    print(f"   Daily volume: ${results_summary[5]['daily_volume']:,.0f}")
    print(f"   Expected daily points: {results_summary[5]['daily_volume']/100:,.0f}")
    print(f"   Expected return: {results_summary[5]['est_return']:.2f}%")
    print(f"   ⚠️ Watch for slippage and fees eating returns")
    print(f"   ⚠️ High API load")
    
    print(f"\n🚀 1-MINUTE CANDLES (Extreme volume)")
    print(f"   EMA periods: {4*60}/{30*60} = 240/1800")
    print(f"   Expected daily trades: {results_summary[1]['total_daily_trades']:.0f} across 5 coins")
    print(f"   Daily volume: ${results_summary[1]['daily_volume']:,.0f}")
    print(f"   Expected daily points: {results_summary[1]['daily_volume']/100:,.0f}")
    print(f"   Expected return: {results_summary[1]['est_return']:.2f}%")
    print(f"   ⚠️ Very noisy signals, likely to underperform")
    print(f"   ⚠️ High fee drag on profits")
    print(f"   ⚠️ API rate limiting risk")
    
    print(f"\n📊 VOLUME COMPARISON (Monthly)")
    print(f"   1h baseline:    ${results_summary[60]['daily_volume']*30:>20,.0f}")
    print(f"   15m:            ${results_summary[15]['daily_volume']*30:>20,.0f} ({results_summary[15]['frequency_multiplier']:.0f}x more)")
    print(f"   5m:             ${results_summary[5]['daily_volume']*30:>20,.0f} ({results_summary[5]['frequency_multiplier']:.0f}x more)")
    print(f"   1m:             ${results_summary[1]['daily_volume']*30:>20,.0f} ({results_summary[1]['frequency_multiplier']:.0f}x more)")
    
    # Save
    with open('research/volume_farming.json', 'w') as f:
        json.dump(results_summary, f, indent=2)
    
    print(f"\n✓ Results saved to research/volume_farming.json")

if __name__ == '__main__':
    main()
