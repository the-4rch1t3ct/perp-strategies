#!/usr/bin/env python3
"""
Backtest Final Optimized Momentum Strategy
- Improved win rate (tighter filters)
- Optimized leverage distribution
- Better execution rate
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from data.fetch_data import MemecoinDataFetcher
from strategies.final_optimized_momentum import FinalOptimizedMomentumStrategy
from backtesting.engine import BacktestEngine, BacktestConfig

ALL_MEMECOINS = [
    'DOGE/USDT:USDT', 'WIF/USDT:USDT', 'BRETT/USDT:USDT', 'TURBO/USDT:USDT',
    'MEW/USDT:USDT', 'BAN/USDT:USDT', 'PNUT/USDT:USDT', 'POPCAT/USDT:USDT',
    'MOODENG/USDT:USDT', 'MEME/USDT:USDT', 'NEIRO/USDT:USDT', 'PEOPLE/USDT:USDT',
    'BOME/USDT:USDT', 'DEGEN/USDT:USDT', 'GOAT/USDT:USDT', 'BANANA/USDT:USDT',
    'ACT/USDT:USDT', 'DOGS/USDT:USDT', 'CHILLGUY/USDT:USDT', 'HIPPO/USDT:USDT',
    '1000SHIB/USDT:USDT', '1000PEPE/USDT:USDT', '1000BONK/USDT:USDT',
    '1000FLOKI/USDT:USDT', '1000CHEEMS/USDT:USDT', '1000000MOG/USDT:USDT',
    '1000SATS/USDT:USDT', '1000CAT/USDT:USDT', '1MBABYDOGE/USDT:USDT',
    '1000WHY/USDT:USDT', 'KOMA/USDT:USDT',
]

def backtest_final(symbol, data, timeframe='5m'):
    """Backtest final optimized strategy"""
    if len(data) < 200:
        return None, f"Insufficient data: {len(data)} candles"
    
    try:
        strategy = FinalOptimizedMomentumStrategy(timeframe=timeframe)
        signals = strategy.generate_signals(data)
        
        long_entries = (signals['signal'] == 1).sum()
        short_entries = (signals['signal'] == -1).sum()
        total_signals = long_entries + short_entries
        
        if total_signals == 0:
            return None, "No signals generated"
        
        # Analyze leverage distribution
        leverage_dist = {}
        for lev in signals[signals['signal'] != 0]['leverage'].dropna():
            lev_key = f"{int(lev)}x"
            leverage_dist[lev_key] = leverage_dist.get(lev_key, 0) + 1
        
        config = BacktestConfig(
            initial_capital=10000.0,
            max_leverage=20.0,
            fee_rate=0.0001,
            slippage_bps=5.0,
            max_position_size_pct=0.25,
            stop_loss_pct=0.03,
            take_profit_pct=0.05,
            max_drawdown_pct=0.30,
        )
        
        engine = BacktestEngine(config)
        results = engine.backtest_strategy(data, signals, symbol=symbol)
        
        results['leverage_distribution'] = leverage_dist
        results['signal_count'] = total_signals
        
        return results, None
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def main():
    """Main backtest function"""
    print("="*80)
    print("FINAL OPTIMIZED MOMENTUM STRATEGY BACKTEST")
    print("="*80)
    print(f"\nStrategy: FinalOptimizedMomentumStrategy")
    print(f"Improvements:")
    print(f"  - Signal strength min: 0.25 (vs 0.15)")
    print(f"  - Filter requirement: 2 of 4 (vs 1 of 4)")
    print(f"  - RSI trend confirmation")
    print(f"  - Optimized leverage thresholds (target: 50% 10x, 35% 15x, 15% 20x)")
    print(f"  - Faster re-entry (no cooldown)")
    print(f"\nSymbols: {len(ALL_MEMECOINS)}")
    print(f"Timeframe: 5m")
    print(f"Capital: $10,000")
    
    fetcher = MemecoinDataFetcher()
    results_dict = {}
    summary_stats = {
        'total_tested': 0,
        'successful': 0,
        'failed': 0,
        'total_trades': 0,
        'total_signals': 0,
        'total_return_sum': 0,
        'total_sharpe_sum': 0,
        'total_win_rate_sum': 0,
        'total_drawdown_sum': 0,
        'leverage_counts': {'10x': 0, '15x': 0, '20x': 0},
    }
    
    print(f"\n{'='*80}")
    print("RUNNING BACKTESTS")
    print(f"{'='*80}\n")
    
    for i, symbol in enumerate(ALL_MEMECOINS, 1):
        print(f"[{i}/{len(ALL_MEMECOINS)}] {symbol}...", end=' ')
        
        try:
            df = fetcher.load_data(symbol, timeframe='5m')
            
            if df.empty:
                print("✗ No data")
                summary_stats['failed'] += 1
                continue
            
            results, error = backtest_final(symbol, df, timeframe='5m')
            
            if results:
                safe_name = symbol.replace('/', '_').replace(':', '_')
                results_dict[safe_name] = {
                    'symbol': symbol,
                    'total_return': results['total_return'],
                    'sharpe_ratio': results['sharpe_ratio'],
                    'sortino_ratio': results['sortino_ratio'],
                    'max_drawdown': results['max_drawdown'],
                    'win_rate': results['win_rate'],
                    'profit_factor': results['profit_factor'],
                    'total_trades': results['total_trades'],
                    'signal_count': results.get('signal_count', 0),
                    'execution_rate': (results['total_trades'] / results.get('signal_count', 1) * 100) if results.get('signal_count', 0) > 0 else 0,
                    'avg_win': results['avg_win'],
                    'avg_loss': results['avg_loss'],
                    'total_pnl': results['total_pnl'],
                    'total_fees': results['total_fees'],
                    'leverage_distribution': results.get('leverage_distribution', {}),
                    'data_points': len(df),
                    'date_range': f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}"
                }
                
                # Update summary
                summary_stats['successful'] += 1
                summary_stats['total_trades'] += results['total_trades']
                summary_stats['total_signals'] += results.get('signal_count', 0)
                summary_stats['total_return_sum'] += results['total_return']
                summary_stats['total_sharpe_sum'] += results['sharpe_ratio']
                summary_stats['total_win_rate_sum'] += results['win_rate']
                summary_stats['total_drawdown_sum'] += results['max_drawdown']
                
                # Count leverage
                lev_dist = results.get('leverage_distribution', {})
                for lev, count in lev_dist.items():
                    if lev in summary_stats['leverage_counts']:
                        summary_stats['leverage_counts'][lev] += count
                
                exec_rate = (results['total_trades'] / results.get('signal_count', 1) * 100) if results.get('signal_count', 0) > 0 else 0
                print(f"✓ Return: {results['total_return']:.2f}% | "
                      f"Trades: {results['total_trades']} | "
                      f"Win: {results['win_rate']*100:.1f}% | "
                      f"Exec: {exec_rate:.1f}% | "
                      f"Sharpe: {results['sharpe_ratio']:.2f}")
            else:
                print(f"✗ {error}")
                summary_stats['failed'] += 1
        
        except Exception as e:
            print(f"✗ Error: {str(e)[:50]}")
            summary_stats['failed'] += 1
        
        summary_stats['total_tested'] += 1
    
    # Save and print summary
    if results_dict:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = Path('research') / f'backtest_final_optimized_{timestamp}.json'
        
        if summary_stats['successful'] > 0:
            results_dict['_summary'] = {
                'timestamp': timestamp,
                'strategy': 'FinalOptimizedMomentumStrategy',
                'total_symbols_tested': summary_stats['total_tested'],
                'successful_backtests': summary_stats['successful'],
                'failed_backtests': summary_stats['failed'],
                'aggregate_stats': {
                    'total_trades': summary_stats['total_trades'],
                    'total_signals': summary_stats['total_signals'],
                    'execution_rate': (summary_stats['total_trades'] / summary_stats['total_signals'] * 100) if summary_stats['total_signals'] > 0 else 0,
                    'avg_return': summary_stats['total_return_sum'] / summary_stats['successful'],
                    'avg_sharpe': summary_stats['total_sharpe_sum'] / summary_stats['successful'],
                    'avg_win_rate': summary_stats['total_win_rate_sum'] / summary_stats['successful'],
                    'avg_max_drawdown': summary_stats['total_drawdown_sum'] / summary_stats['successful'],
                    'leverage_distribution': summary_stats['leverage_counts'],
                }
            }
        
        with open(results_file, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        # Detailed summary
        print(f"\n{'='*80}")
        print("FINAL SUMMARY")
        print(f"{'='*80}")
        
        if summary_stats['successful'] > 0:
            exec_rate = (summary_stats['total_trades'] / summary_stats['total_signals'] * 100) if summary_stats['total_signals'] > 0 else 0
            
            print(f"\nBacktest Results:")
            print(f"  Symbols Tested: {summary_stats['total_tested']}")
            print(f"  Successful: {summary_stats['successful']}")
            print(f"  Failed: {summary_stats['failed']}")
            
            print(f"\nTrade Statistics:")
            print(f"  Total Signals: {summary_stats['total_signals']}")
            print(f"  Total Trades: {summary_stats['total_trades']}")
            print(f"  Execution Rate: {exec_rate:.1f}%")
            print(f"  Avg Trades per Symbol: {summary_stats['total_trades']/summary_stats['successful']:.1f}")
            
            print(f"\nPerformance Metrics:")
            print(f"  Average Return: {summary_stats['total_return_sum'] / summary_stats['successful']:.2f}%")
            print(f"  Average Sharpe: {summary_stats['total_sharpe_sum'] / summary_stats['successful']:.2f}")
            print(f"  Average Win Rate: {summary_stats['total_win_rate_sum'] / summary_stats['successful'] * 100:.1f}%")
            print(f"  Average Max Drawdown: {summary_stats['total_drawdown_sum'] / summary_stats['successful']:.2f}%")
            
            print(f"\nLeverage Distribution:")
            total_lev = sum(summary_stats['leverage_counts'].values())
            for lev, count in summary_stats['leverage_counts'].items():
                pct = (count / total_lev * 100) if total_lev > 0 else 0
                print(f"  {lev}: {count} signals ({pct:.1f}%)")
            
            # Top performers
            sorted_results = sorted(
                [(k, v) for k, v in results_dict.items() if k != '_summary'],
                key=lambda x: x[1]['total_return'],
                reverse=True
            )
            
            print(f"\nTop 10 Performers:")
            for i, (key, result) in enumerate(sorted_results[:10], 1):
                print(f"  {i}. {result['symbol']}: {result['total_return']:.2f}% "
                      f"({result['total_trades']} trades, {result['win_rate']*100:.1f}% win, "
                      f"{result['execution_rate']:.1f}% exec)")
        
        print(f"\n✓ Results saved to: {results_file}")

if __name__ == '__main__':
    main()
