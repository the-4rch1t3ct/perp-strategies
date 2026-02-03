#!/usr/bin/env python3
"""
Realistic SL/TP Optimization
Test actual exit logic instead of scaling
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

def backtest_with_exits(data, signals, initial_capital=10000, sl_pct=0.05, tp_pct=0.10, leverage=5):
    """
    Realistic backtest with SL/TP logic
    Tracks actual position entries/exits
    """
    
    positions = []  # List of open positions
    closed_trades = []
    capital = initial_capital
    equity_curve = []
    
    for i in range(1, len(data)):
        current_price = data['close'].iloc[i]
        signal = signals['signal'].iloc[i]
        
        # Check exits on existing positions
        for pos in positions[:]:  # Copy to avoid modification during iteration
            pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']
            
            if pos['side'] == 1:  # Long
                pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']
            else:  # Short
                pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price']
            
            # Check SL/TP
            hit_tp = pnl_pct >= tp_pct
            hit_sl = pnl_pct <= -sl_pct
            
            if hit_tp or hit_sl:
                # Close position
                pnl = pos['size'] * pnl_pct
                closed_trades.append({
                    'entry': pos['entry_price'],
                    'exit': current_price,
                    'side': pos['side'],
                    'pnl_pct': pnl_pct,
                    'pnl': pnl
                })
                capital += pnl
                positions.remove(pos)
        
        # Check for new signals (only if no position)
        if signal != 0 and len(positions) == 0:
            # Open position
            position_size = (capital * 0.20 * leverage) / current_price  # 20% allocation × leverage
            positions.append({
                'entry_price': current_price,
                'size': position_size,
                'side': int(signal),
                'entry_time': i
            })
        
        # Calculate equity
        unrealized = sum(
            pos['size'] * (current_price - pos['entry_price']) if pos['side'] == 1 
            else pos['size'] * (pos['entry_price'] - current_price)
            for pos in positions
        )
        total_equity = capital + unrealized
        equity_curve.append(total_equity)
    
    # Metrics
    if len(closed_trades) == 0:
        return None
    
    trades_df = pd.DataFrame(closed_trades)
    
    total_return = ((equity_curve[-1] - initial_capital) / initial_capital) * 100
    winning_trades = (trades_df['pnl'] > 0).sum()
    win_rate = winning_trades / len(trades_df)
    
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / max(gross_loss, 1e-8)
    
    # Sharpe
    returns = np.array(equity_curve)
    returns = np.diff(returns) / returns[:-1]
    sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
    
    # Max drawdown
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (np.array(equity_curve) - peak) / peak
    max_dd = abs(np.min(drawdown))
    
    return {
        'total_return': total_return,
        'sharpe': sharpe,
        'max_drawdown': max_dd * 100,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'num_trades': len(trades_df),
        'final_equity': equity_curve[-1]
    }

def optimize_sl_tp(data_dict):
    """Test different SL/TP combinations"""
    
    portfolio = {
        '1000SATS_USDT_USDT': {'fast_period': 4, 'slow_period': 30},
        '1000PEPE_USDT_USDT': {'fast_period': 5, 'slow_period': 30},
        '1000000MOG_USDT_USDT': {'fast_period': 12, 'slow_period': 30}
    }
    
    sl_levels = [0.02, 0.03, 0.05, 0.07, 0.10]
    tp_levels = [0.05, 0.07, 0.10, 0.15, 0.20]
    leverage_levels = [1, 2, 3, 5]
    
    print("=" * 100)
    print("SL/TP OPTIMIZATION (with realistic position tracking)")
    print("=" * 100)
    
    best_result = None
    best_sharpe = -999
    results_grid = {}
    
    for leverage in leverage_levels:
        print(f"\n{'LEVERAGE':<10} | {'SL':<6} | {'TP':<6} | {'Return':<10} | {'Sharpe':<8} | {'DD':<8} | {'WR':<6}")
        print("-" * 100)
        
        for sl in sl_levels:
            for tp in tp_levels:
                if tp <= sl:
                    continue
                
                coin_results = []
                
                for symbol, params in portfolio.items():
                    if symbol not in data_dict:
                        continue
                    
                    data = data_dict[symbol]
                    strategy = MomentumStrategy(params=params)
                    signals = strategy.generate_signals(data)
                    
                    result = backtest_with_exits(
                        data, signals,
                        initial_capital=10000,
                        sl_pct=sl,
                        tp_pct=tp,
                        leverage=leverage
                    )
                    
                    if result:
                        coin_results.append(result)
                
                if not coin_results:
                    continue
                
                # Portfolio average
                avg_return = np.mean([r['total_return'] for r in coin_results])
                avg_sharpe = np.mean([r['sharpe'] for r in coin_results])
                avg_dd = np.mean([r['max_drawdown'] for r in coin_results])
                avg_wr = np.mean([r['win_rate'] for r in coin_results])
                
                key = f"{leverage}x_{sl:.0%}_{tp:.0%}"
                results_grid[key] = {
                    'leverage': leverage,
                    'sl': sl,
                    'tp': tp,
                    'return': avg_return,
                    'sharpe': avg_sharpe,
                    'drawdown': avg_dd,
                    'win_rate': avg_wr
                }
                
                if avg_sharpe > best_sharpe:
                    best_sharpe = avg_sharpe
                    best_result = results_grid[key]
                
                print(f"{leverage}x         | {sl:.0%}    | {tp:.0%}    | {avg_return:>8.2f}% | {avg_sharpe:>7.2f} | {avg_dd:>7.2f}% | {avg_wr:>5.1%}")
    
    return best_result, results_grid

def main():
    data_dict = load_data()
    print(f"Loaded {len(data_dict)} coins\n")
    
    best, grid = optimize_sl_tp(data_dict)
    
    print("\n" + "=" * 100)
    print("OPTIMAL CONFIGURATION")
    print("=" * 100)
    
    print(f"\n✓ Leverage: {best['leverage']}x")
    print(f"✓ Stop Loss: {best['sl']:.1%}")
    print(f"✓ Take Profit: {best['tp']:.1%}")
    print(f"\nExpected Performance:")
    print(f"  Return: {best['return']:.2f}%")
    print(f"  Sharpe: {best['sharpe']:.2f}")
    print(f"  Max Drawdown: {best['drawdown']:.2f}%")
    print(f"  Win Rate: {best['win_rate']:.1%}")
    
    # Save results
    with open('research/sl_tp_optimization.json', 'w') as f:
        json.dump({'optimal': best, 'grid': grid}, f, indent=2)

if __name__ == '__main__':
    main()
