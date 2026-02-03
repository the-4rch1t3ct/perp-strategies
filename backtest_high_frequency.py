#!/usr/bin/env python3
"""
Backtest High-Frequency Momentum Strategy on 5m/15m timeframes
Optimized for high trade volume and improved performance
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
from strategies.high_frequency_momentum import HighFrequencyMomentumStrategy
from backtesting.engine import BacktestEngine, BacktestConfig

def fetch_5m_data(symbols=None, days=30):
    """Fetch 5-minute data for high-frequency trading"""
    fetcher = MemecoinDataFetcher()
    
    if symbols is None:
        # Top memecoins from Privex screenshots
        symbols = [
            'DOGE/USDT:USDT',
            '1000SHIB/USDT:USDT',
            '1000PEPE/USDT:USDT',
            'WIF/USDT:USDT',
            '1000BONK/USDT:USDT',
            '1000FLOKI/USDT:USDT',
            '1000CAT/USDT:USDT',
            'MEME/USDT:USDT',
            'BRETT/USDT:USDT',
            'POPCAT/USDT:USDT',
        ]
    
    results = {}
    for symbol in symbols:
        print(f"Fetching 5m data for {symbol}...")
        try:
            from datetime import timedelta
            since = datetime.now() - timedelta(days=days)
            df = fetcher.fetch_ohlcv(symbol, timeframe='5m', since=since, limit=2000)
            
            if not df.empty:
                safe_name = symbol.replace('/', '_').replace(':', '_')
                filepath = os.path.join('data', f"{safe_name}_5m.csv")
                df.to_csv(filepath)
                results[symbol] = df
                print(f"  ✓ {len(df)} candles saved")
            else:
                print(f"  ✗ No data")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    return results

def backtest_strategy_on_symbol(symbol, data, timeframe='5m'):
    """Backtest high-frequency momentum strategy on a single symbol"""
    print(f"\n{'='*60}")
    print(f"Backtesting {symbol} ({timeframe})")
    print(f"{'='*60}")
    
    if len(data) < 200:
        print(f"⚠ Insufficient data: {len(data)} candles")
        return None
    
    # Initialize strategy
    strategy = HighFrequencyMomentumStrategy(timeframe=timeframe)
    
    # Generate signals
    print("Generating signals...")
    signals = strategy.generate_signals(data)
    
    # Count signals
    long_entries = (signals['signal'] == 1).sum()
    short_entries = (signals['signal'] == -1).sum()
    exits = (signals['signal'] == 0).sum()
    
    print(f"  Long entries: {long_entries}")
    print(f"  Short entries: {short_entries}")
    print(f"  Total signals: {long_entries + short_entries}")
    
    if long_entries + short_entries == 0:
        print("  ⚠ No signals generated")
        return None
    
    # Backtest configuration (optimized for high frequency)
    config = BacktestConfig(
        initial_capital=10000.0,
        max_leverage=20.0,
        fee_rate=0.0001,  # Privex fees
        slippage_bps=5.0,  # 5 bps slippage
        max_position_size_pct=0.25,
        stop_loss_pct=0.03,  # Tighter stop (3%)
        take_profit_pct=0.05,  # 5% take profit
        max_drawdown_pct=0.30,
        commission_per_trade=0.0
    )
    
    # Run backtest
    print("Running backtest...")
    engine = BacktestEngine(config)
    results = engine.backtest_strategy(data, signals, symbol=symbol)
    
    # Print results
    print(f"\nResults:")
    print(f"  Total Return: {results['total_return']:.2f}%")
    print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {results['sortino_ratio']:.2f}")
    print(f"  Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"  Win Rate: {results['win_rate']*100:.1f}%")
    print(f"  Profit Factor: {results['profit_factor']:.2f}")
    print(f"  Total Trades: {results['total_trades']}")
    print(f"  Avg Win: ${results['avg_win']:.2f}")
    print(f"  Avg Loss: ${results['avg_loss']:.2f}")
    print(f"  Total P&L: ${results['total_pnl']:.2f}")
    print(f"  Total Fees: ${results['total_fees']:.2f}")
    
    return results

def main():
    """Main backtest function"""
    print("="*80)
    print("HIGH-FREQUENCY MOMENTUM STRATEGY BACKTEST")
    print("="*80)
    
    # Check if 5m data exists, if not fetch it
    data_dir = Path('data')
    existing_5m = list(data_dir.glob('*_5m.csv'))
    
    if len(existing_5m) == 0:
        print("\nNo 5m data found. Fetching...")
        fetch_5m_data(days=30)
    else:
        print(f"\nFound {len(existing_5m)} existing 5m data files")
    
    # Load data and backtest
    fetcher = MemecoinDataFetcher()
    results_dict = {}
    
    # Test symbols
    test_symbols = [
        'DOGE/USDT:USDT',
        '1000PEPE/USDT:USDT',
        '1000CAT/USDT:USDT',
        'WIF/USDT:USDT',
        'MEME/USDT:USDT',
    ]
    
    for symbol in test_symbols:
        try:
            # Try loading 5m data
            df = fetcher.load_data(symbol, timeframe='5m')
            
            if df.empty:
                print(f"\n⚠ No 5m data for {symbol}, skipping...")
                continue
            
            results = backtest_strategy_on_symbol(symbol, df, timeframe='5m')
            
            if results:
                safe_name = symbol.replace('/', '_').replace(':', '_')
                results_dict[safe_name] = {
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
                }
        
        except Exception as e:
            print(f"\n✗ Error processing {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save results
    if results_dict:
        results_file = Path('research') / 'backtest_high_frequency_5m.json'
        with open(results_file, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        
        total_trades = sum(r['total_trades'] for r in results_dict.values())
        avg_return = np.mean([r['total_return'] for r in results_dict.values()])
        avg_sharpe = np.mean([r['sharpe_ratio'] for r in results_dict.values()])
        avg_win_rate = np.mean([r['win_rate'] for r in results_dict.values()])
        avg_drawdown = np.mean([r['max_drawdown'] for r in results_dict.values()])
        
        print(f"\nAggregate Statistics:")
        print(f"  Symbols tested: {len(results_dict)}")
        print(f"  Total trades: {total_trades}")
        print(f"  Average return: {avg_return:.2f}%")
        print(f"  Average Sharpe: {avg_sharpe:.2f}")
        print(f"  Average win rate: {avg_win_rate*100:.1f}%")
        print(f"  Average max drawdown: {avg_drawdown:.2f}%")
        
        print(f"\n✓ Results saved to: {results_file}")

if __name__ == '__main__':
    main()
