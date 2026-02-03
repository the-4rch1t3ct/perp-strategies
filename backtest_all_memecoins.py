#!/usr/bin/env python3
"""
Backtest High-Frequency Momentum Strategy on ALL Privex Memecoins
Fetches most recent data and runs comprehensive backtests
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from data.fetch_data import MemecoinDataFetcher
from strategies.high_frequency_momentum import HighFrequencyMomentumStrategy
from backtesting.engine import BacktestEngine, BacktestConfig

# All memecoins from Privex screenshots
ALL_MEMECOINS = [
    # First screenshot
    'DOGE/USDT:USDT',
    'WIF/USDT:USDT',
    'BRETT/USDT:USDT',
    'TURBO/USDT:USDT',
    'MEW/USDT:USDT',
    'BAN/USDT:USDT',
    'PNUT/USDT:USDT',
    'POPCAT/USDT:USDT',
    'MOODENG/USDT:USDT',
    'MEME/USDT:USDT',
    'NEIRO/USDT:USDT',
    'PEOPLE/USDT:USDT',
    'BOME/USDT:USDT',
    'DEGEN/USDT:USDT',
    'GOAT/USDT:USDT',
    'BANANA/USDT:USDT',
    'ACT/USDT:USDT',
    
    # Second screenshot
    'DOGS/USDT:USDT',
    'CHILLGUY/USDT:USDT',
    'HIPPO/USDT:USDT',
    '1000SHIB/USDT:USDT',
    '1000PEPE/USDT:USDT',
    '1000BONK/USDT:USDT',
    '1000FLOKI/USDT:USDT',
    '1000CHEEMS/USDT:USDT',
    '1000000MOG/USDT:USDT',
    '1000SATS/USDT:USDT',
    '1000CAT/USDT:USDT',
    '1MBABYDOGE/USDT:USDT',
    '1000WHY/USDT:USDT',
    'KOMA/USDT:USDT',
]

def fetch_recent_data(symbols, timeframe='5m', days=30):
    """Fetch most recent data for all symbols"""
    fetcher = MemecoinDataFetcher()
    results = {}
    failed = []
    
    print(f"\n{'='*80}")
    print(f"FETCHING MOST RECENT DATA ({timeframe}, last {days} days)")
    print(f"{'='*80}\n")
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] Fetching {symbol}...", end=' ')
        try:
            since = datetime.now() - timedelta(days=days)
            df = fetcher.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=2000)
            
            if not df.empty:
                safe_name = symbol.replace('/', '_').replace(':', '_')
                filepath = os.path.join('data', f"{safe_name}_{timeframe}.csv")
                df.to_csv(filepath)
                results[symbol] = df
                print(f"✓ {len(df)} candles ({df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')})")
            else:
                print("✗ No data")
                failed.append(symbol)
        except Exception as e:
            print(f"✗ Error: {str(e)[:50]}")
            failed.append(symbol)
    
    print(f"\n✓ Successfully fetched: {len(results)}/{len(symbols)}")
    if failed:
        print(f"✗ Failed: {len(failed)} symbols")
        print(f"  {', '.join(failed[:5])}{'...' if len(failed) > 5 else ''}")
    
    return results

def backtest_strategy_on_symbol(symbol, data, timeframe='5m', config=None):
    """Backtest high-frequency momentum strategy on a single symbol"""
    if len(data) < 200:
        return None, f"Insufficient data: {len(data)} candles"
    
    try:
        # Initialize strategy
        strategy = HighFrequencyMomentumStrategy(timeframe=timeframe)
        
        # Generate signals
        signals = strategy.generate_signals(data)
        
        # Count signals
        long_entries = (signals['signal'] == 1).sum()
        short_entries = (signals['signal'] == -1).sum()
        total_signals = long_entries + short_entries
        
        if total_signals == 0:
            return None, "No signals generated"
        
        # Backtest configuration
        if config is None:
            config = BacktestConfig(
                initial_capital=10000.0,
                max_leverage=20.0,
                fee_rate=0.0001,  # Privex fees
                slippage_bps=5.0,
                max_position_size_pct=0.25,
                stop_loss_pct=0.03,
                take_profit_pct=0.05,
                max_drawdown_pct=0.30,
            )
        
        # Run backtest
        engine = BacktestEngine(config)
        results = engine.backtest_strategy(data, signals, symbol=symbol)
        
        return results, None
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def main():
    """Main backtest function"""
    print("="*80)
    print("COMPREHENSIVE MEMECOIN BACKTEST - HIGH-FREQUENCY MOMENTUM")
    print("="*80)
    print(f"\nSymbols to test: {len(ALL_MEMECOINS)}")
    print(f"Timeframe: 5m (high frequency)")
    print(f"Strategy: HighFrequencyMomentumStrategy")
    print(f"Capital: $10,000")
    print(f"Max Leverage: 20x")
    print(f"Fees: 0.0001% (Privex)")
    
    # Fetch most recent data
    data_dict = fetch_recent_data(ALL_MEMECOINS, timeframe='5m', days=30)
    
    if not data_dict:
        print("\n✗ No data available. Exiting.")
        return
    
    # Backtest configuration
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
    
    # Run backtests
    print(f"\n{'='*80}")
    print("RUNNING BACKTESTS")
    print(f"{'='*80}\n")
    
    results_dict = {}
    summary_stats = {
        'total_tested': 0,
        'successful': 0,
        'failed': 0,
        'total_trades': 0,
        'total_return_sum': 0,
        'total_sharpe_sum': 0,
        'total_win_rate_sum': 0,
        'total_drawdown_sum': 0,
    }
    
    for i, (symbol, data) in enumerate(data_dict.items(), 1):
        print(f"[{i}/{len(data_dict)}] {symbol}...", end=' ')
        
        results, error = backtest_strategy_on_symbol(symbol, data, timeframe='5m', config=config)
        
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
                'avg_win': results['avg_win'],
                'avg_loss': results['avg_loss'],
                'total_pnl': results['total_pnl'],
                'total_fees': results['total_fees'],
                'data_points': len(data),
                'date_range': f"{data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}"
            }
            
            # Update summary
            summary_stats['successful'] += 1
            summary_stats['total_trades'] += results['total_trades']
            summary_stats['total_return_sum'] += results['total_return']
            summary_stats['total_sharpe_sum'] += results['sharpe_ratio']
            summary_stats['total_win_rate_sum'] += results['win_rate']
            summary_stats['total_drawdown_sum'] += results['max_drawdown']
            
            print(f"✓ Return: {results['total_return']:.2f}% | "
                  f"Trades: {results['total_trades']} | "
                  f"Win: {results['win_rate']*100:.1f}% | "
                  f"Sharpe: {results['sharpe_ratio']:.2f}")
        else:
            print(f"✗ {error}")
            summary_stats['failed'] += 1
        
        summary_stats['total_tested'] += 1
    
    # Save results
    if results_dict:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = Path('research') / f'backtest_all_memecoins_5m_{timestamp}.json'
        
        # Add summary to results
        if summary_stats['successful'] > 0:
            results_dict['_summary'] = {
                'timestamp': timestamp,
                'total_symbols_tested': summary_stats['total_tested'],
                'successful_backtests': summary_stats['successful'],
                'failed_backtests': summary_stats['failed'],
                'aggregate_stats': {
                    'total_trades': summary_stats['total_trades'],
                    'avg_return': summary_stats['total_return_sum'] / summary_stats['successful'],
                    'avg_sharpe': summary_stats['total_sharpe_sum'] / summary_stats['successful'],
                    'avg_win_rate': summary_stats['total_win_rate_sum'] / summary_stats['successful'],
                    'avg_max_drawdown': summary_stats['total_drawdown_sum'] / summary_stats['successful'],
                }
            }
        
        with open(results_file, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        # Print summary
        print(f"\n{'='*80}")
        print("BACKTEST SUMMARY")
        print(f"{'='*80}")
        
        if summary_stats['successful'] > 0:
            print(f"\nSymbols Tested: {summary_stats['total_tested']}")
            print(f"Successful: {summary_stats['successful']}")
            print(f"Failed: {summary_stats['failed']}")
            print(f"\nAggregate Statistics:")
            print(f"  Total Trades: {summary_stats['total_trades']}")
            print(f"  Average Return: {summary_stats['total_return_sum'] / summary_stats['successful']:.2f}%")
            print(f"  Average Sharpe: {summary_stats['total_sharpe_sum'] / summary_stats['successful']:.2f}")
            print(f"  Average Win Rate: {summary_stats['total_win_rate_sum'] / summary_stats['successful'] * 100:.1f}%")
            print(f"  Average Max Drawdown: {summary_stats['total_drawdown_sum'] / summary_stats['successful']:.2f}%")
            
            # Top performers
            sorted_results = sorted(
                [(k, v) for k, v in results_dict.items() if k != '_summary'],
                key=lambda x: x[1]['total_return'],
                reverse=True
            )
            
            print(f"\nTop 5 Performers:")
            for i, (key, result) in enumerate(sorted_results[:5], 1):
                print(f"  {i}. {result['symbol']}: {result['total_return']:.2f}% "
                      f"({result['total_trades']} trades, {result['win_rate']*100:.1f}% win rate)")
            
            print(f"\nBottom 5 Performers:")
            for i, (key, result) in enumerate(sorted_results[-5:], 1):
                print(f"  {i}. {result['symbol']}: {result['total_return']:.2f}% "
                      f"({result['total_trades']} trades, {result['win_rate']*100:.1f}% win rate)")
        
        print(f"\n✓ Results saved to: {results_file}")
        
        # Generate markdown report
        report_file = Path('research') / f'BACKTEST_REPORT_ALL_{timestamp}.md'
        generate_markdown_report(results_dict, report_file, summary_stats)
        print(f"✓ Report saved to: {report_file}")

def generate_markdown_report(results_dict, report_file, summary_stats):
    """Generate markdown report from results"""
    with open(report_file, 'w') as f:
        f.write("# Comprehensive Memecoin Backtest Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        
        if summary_stats['successful'] > 0:
            f.write(f"- **Symbols Tested**: {summary_stats['total_tested']}\n")
            f.write(f"- **Successful Backtests**: {summary_stats['successful']}\n")
            f.write(f"- **Failed Backtests**: {summary_stats['failed']}\n")
            f.write(f"- **Total Trades**: {summary_stats['total_trades']}\n")
            f.write(f"- **Average Return**: {summary_stats['total_return_sum'] / summary_stats['successful']:.2f}%\n")
            f.write(f"- **Average Sharpe**: {summary_stats['total_sharpe_sum'] / summary_stats['successful']:.2f}\n")
            f.write(f"- **Average Win Rate**: {summary_stats['total_win_rate_sum'] / summary_stats['successful'] * 100:.1f}%\n")
            f.write(f"- **Average Max Drawdown**: {summary_stats['total_drawdown_sum'] / summary_stats['successful']:.2f}%\n\n")
        
        f.write("## Detailed Results\n\n")
        f.write("| Symbol | Return % | Sharpe | Sortino | Max DD % | Win Rate | Trades | Profit Factor |\n")
        f.write("|--------|----------|--------|---------|----------|----------|--------|--------------|\n")
        
        sorted_results = sorted(
            [(k, v) for k, v in results_dict.items() if k != '_summary'],
            key=lambda x: x[1]['total_return'],
            reverse=True
        )
        
        for key, result in sorted_results:
            f.write(f"| {result['symbol']} | "
                  f"{result['total_return']:.2f} | "
                  f"{result['sharpe_ratio']:.2f} | "
                  f"{result['sortino_ratio']:.2f} | "
                  f"{result['max_drawdown']:.2f} | "
                  f"{result['win_rate']*100:.1f} | "
                  f"{result['total_trades']} | "
                  f"{result['profit_factor']:.2f} |\n")
        
        f.write("\n## Notes\n\n")
        f.write("- Strategy: HighFrequencyMomentumStrategy (5m timeframe)\n")
        f.write("- Initial Capital: $10,000\n")
        f.write("- Max Leverage: 20x\n")
        f.write("- Fees: 0.0001% (Privex)\n")
        f.write("- Slippage: 5 bps\n")

if __name__ == '__main__':
    main()
