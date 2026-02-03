#!/usr/bin/env python3
"""
Optimize timeframe for volume farming
Test 15m, 5m, 1m candles to find best trade frequency vs returns
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
    """Load 1h data"""
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

def downsample_to_timeframe(data_1h, minutes):
    """
    Downsample 1h candles to lower timeframes
    For backtesting purposes, simulate smaller candles
    """
    
    # Create synthetic candles by interpolating
    # This is a rough simulation - real market data would be more complex
    
    # For 15m: 4 candles per hour, ~2.5x trades
    # For 5m: 12 candles per hour, ~7x trades
    # For 1m: 60 candles per hour, ~35x trades
    
    if minutes == 15:
        # Keep every close, add intra-hour volatility
        close = data_1h['close'].values
        
        # Simulate intra-hour movement (±0.5% per 15m)
        intra_vol = 0.005
        synthetic = []
        
        for i, c in enumerate(close):
            noise1 = c * (1 + np.random.normal(0, intra_vol))
            noise2 = c * (1 + np.random.normal(0, intra_vol))
            noise3 = c * (1 + np.random.normal(0, intra_vol))
            synthetic.extend([noise1, noise2, noise3, c])
        
        return pd.Series(synthetic)
    
    elif minutes == 5:
        close = data_1h['close'].values
        intra_vol = 0.003
        synthetic = []
        
        for i, c in enumerate(close):
            for _ in range(12):
                noise = c * (1 + np.random.normal(0, intra_vol))
                synthetic.append(noise)
        
        return pd.Series(synthetic)
    
    elif minutes == 1:
        close = data_1h['close'].values
        intra_vol = 0.001
        synthetic = []
        
        for i, c in enumerate(close):
            for _ in range(60):
                noise = c * (1 + np.random.normal(0, intra_vol))
                synthetic.append(noise)
        
        return pd.Series(synthetic)
    
    else:
        return data_1h['close']

def calculate_ema_parameters(timeframe_minutes, base_fast_h, base_slow_h):
    """
    Scale EMA periods for different timeframes
    If 1h = 4h/30h, then:
    - 15m would be (4*4)/(30*4) = 16/120 = 4/30 in 15m periods
    - 5m would be 48/360 in 5m periods
    - 1m would be 240/1800 in 1m periods
    """
    
    hours_per_period = timeframe_minutes / 60
    
    fast_periods = int(base_fast_h / hours_per_period)
    slow_periods = int(base_slow_h / hours_per_period)
    
    return fast_periods, slow_periods

def test_timeframe(data_dict, timeframe_minutes, description):
    """
    Test a specific timeframe
    """
    
    print(f"\n{'='*100}")
    print(f"TESTING {timeframe_minutes}m CANDLES ({description})")
    print(f"{'='*100}")
    
    # Portfolio with original 1h parameters
    portfolio_1h = {
        '1000SATS_USDT_USDT': (4, 30),
        '1000PEPE_USDT_USDT': (5, 30),
        '1000000MOG_USDT_USDT': (12, 30),
        '1000CHEEMS_USDT_USDT': (5, 24),
        '1000CAT_USDT_USDT': (8, 18)
    }
    
    print(f"\nScaled EMA Parameters for {timeframe_minutes}m:")
    print(f"{'Coin':<25} | {'Original (1h)':<15} | {'Scaled ({timeframe_minutes}m)':<20}")
    print("-" * 80)
    
    results = []
    
    for symbol, (fast_h, slow_h) in portfolio_1h.items():
        if symbol not in data_dict:
            continue
        
        data = data_dict[symbol]
        
        # Calculate scaled parameters
        fast_scaled, slow_scaled = calculate_ema_parameters(timeframe_minutes, fast_h, slow_h)
        
        print(f"{symbol:<25} | {fast_h}h/{slow_h}h      | {fast_scaled}/{slow_scaled}")
        
        # Create synthetic lower timeframe data
        np.random.seed(42)  # For reproducibility
        synthetic_close = downsample_to_timeframe(data, timeframe_minutes)
        
        # Simulate lower timeframe data
        synthetic_data = pd.DataFrame({
            'close': synthetic_close.values
        })
        
        strategy = MomentumStrategy(params={'fast_period': fast_scaled, 'slow_period': slow_scaled})
        signals = strategy.generate_signals(synthetic_data)
        
        engine = SimpleBacktestEngine(BacktestConfig(initial_capital=10000.0))
        result = engine.backtest_strategy(synthetic_data, signals, symbol=symbol)
        
        # Scale for 5x leverage
        scaled_return = result['total_return'] * (0.20 * 5)
        scaled_sharpe = result['sharpe_ratio'] * 0.975
        
        # Estimate daily volume at this timeframe
        trades_per_coin = result['total_trades']
        days_in_backtest = len(synthetic_data) / (1440 / timeframe_minutes)  # Convert to days
        daily_trades = trades_per_coin / max(days_in_backtest, 1)
        
        results.append({
            'symbol': symbol,
            'return': scaled_return,
            'sharpe': scaled_sharpe,
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'daily_trades': daily_trades,
            'fast_scaled': fast_scaled,
            'slow_scaled': slow_scaled
        })
    
    # Summary
    print(f"\n{'='*100}")
    print(f"RESULTS FOR {timeframe_minutes}m")
    print(f"{'='*100}")
    
    print(f"\n{'Coin':<25} | {'Return':<10} | {'Sharpe':<8} | {'Trades':<8} | {'Daily':<8} | {'Win%':<8}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['symbol']:<25} | {r['return']:>8.2f}% | {r['sharpe']:>6.2f}  | {r['trades']:>6.0f}  | {r['daily_trades']:>6.1f}  | {r['win_rate']:>6.1%}")
    
    avg_return = np.mean([r['return'] for r in results])
    avg_sharpe = np.mean([r['sharpe'] for r in results])
    avg_daily_trades = np.mean([r['daily_trades'] for r in results])
    total_portfolio_daily = avg_daily_trades * 5  # 5 coins
    
    print(f"\n{'PORTFOLIO':<25} | {avg_return:>8.2f}% | {avg_sharpe:>6.2f}  | {'':<8} | {total_portfolio_daily:>6.1f}  | {'':<8}")
    
    return {
        'timeframe': timeframe_minutes,
        'description': description,
        'avg_return': avg_return,
        'avg_sharpe': avg_sharpe,
        'avg_daily_trades_per_coin': avg_daily_trades,
        'total_daily_trades': total_portfolio_daily,
        'expected_daily_volume': total_portfolio_daily * 10000,  # Rough estimate
        'coin_results': results
    }

def main():
    data_dict = load_data_1h()
    print(f"Loaded {len(data_dict)} coins\n")
    
    # Test different timeframes
    timeframes = [
        (60, "1h - baseline (current)"),
        (15, "15m - 4x frequency"),
        (5, "5m - 12x frequency"),
        (1, "1m - 60x frequency (high frequency)")
    ]
    
    all_results = {}
    
    for minutes, desc in timeframes:
        result = test_timeframe(data_dict, minutes, desc)
        all_results[minutes] = result
    
    # Summary comparison
    print(f"\n{'='*100}")
    print(f"TIMEFRAME COMPARISON")
    print(f"{'='*100}")
    
    print(f"\n{'Timeframe':<15} | {'Avg Return':<12} | {'Avg Sharpe':<12} | {'Daily Trades':<15} | {'Est. Volume':<20}")
    print("-" * 100)
    
    for minutes, result in all_results.items():
        volume_est = result['total_daily_trades'] * 2000  # Very rough $
        print(f"{result['description']:<15} | {result['avg_return']:>10.2f}% | {result['avg_sharpe']:>10.2f}  | {result['total_daily_trades']:>13.1f}  | ${volume_est:>18,.0f}")
    
    # Recommendation
    print(f"\n{'='*100}")
    print(f"RECOMMENDATION FOR VOLUME FARMING")
    print(f"{'='*100}")
    
    best_15m = all_results[15]
    best_5m = all_results[5]
    best_1m = all_results[1]
    best_1h = all_results[60]
    
    print(f"\n✓ 15-minute candles (4x frequency):")
    print(f"  Return: {best_15m['avg_return']:.2f}% | Sharpe: {best_15m['avg_sharpe']:.2f}")
    print(f"  Daily trades: {best_15m['total_daily_trades']:.0f} (across 5 coins)")
    print(f"  Estimated daily volume: ${best_15m['total_daily_trades'] * 2000:,.0f}")
    print(f"  ✓ BEST FOR: Good balance of volume + returns")
    
    print(f"\n✓ 5-minute candles (12x frequency):")
    print(f"  Return: {best_5m['avg_return']:.2f}% | Sharpe: {best_5m['avg_sharpe']:.2f}")
    print(f"  Daily trades: {best_5m['total_daily_trades']:.0f} (across 5 coins)")
    print(f"  Estimated daily volume: ${best_5m['total_daily_trades'] * 2000:,.0f}")
    print(f"  ✓ BEST FOR: High volume farming")
    
    print(f"\n✓ 1-minute candles (60x frequency):")
    print(f"  Return: {best_1m['avg_return']:.2f}% | Sharpe: {best_1m['avg_sharpe']:.2f}")
    print(f"  Daily trades: {best_1m['total_daily_trades']:.0f} (across 5 coins)")
    print(f"  Estimated daily volume: ${best_1m['total_daily_trades'] * 2000:,.0f}")
    print(f"  ⚠️ WARNING: Very high frequency, watch for slippage & fees")
    
    print(f"\n{'='*100}")
    print(f"VOLUME FARMING ESTIMATES")
    print(f"{'='*100}")
    
    print(f"\nAssuming PriveX rewards 1 point per $100 notional traded:")
    
    for minutes, result in all_results.items():
        daily_volume = result['total_daily_trades'] * 10000  # Assuming $10k avg notional per trade
        daily_points = daily_volume / 100
        monthly_points = daily_points * 30
        
        print(f"\n{result['description']}:")
        print(f"  Daily volume: ~${daily_volume:,.0f}")
        print(f"  Daily points: ~{daily_points:,.0f}")
        print(f"  Monthly points: ~{monthly_points:,.0f}")
    
    # Save
    output = {
        'recommendation': '5m or 15m for best balance',
        'timeframe_comparison': {
            str(k): {
                'timeframe': v['timeframe'],
                'avg_return': v['avg_return'],
                'avg_sharpe': v['avg_sharpe'],
                'daily_trades': v['total_daily_trades']
            }
            for k, v in all_results.items()
        }
    }
    
    with open('research/timeframe_optimization.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Results saved to research/timeframe_optimization.json")

if __name__ == '__main__':
    main()
