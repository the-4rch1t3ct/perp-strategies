#!/usr/bin/env python3
"""
Backtest Results Verification Script
Analyzes and verifies backtest results for accuracy and completeness
"""

import json
import os
import pandas as pd
import numpy as np
from pathlib import Path

def load_backtest_results(filepath):
    """Load backtest results from JSON file"""
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r') as f:
        return json.load(f)

def analyze_results(results, filename):
    """Analyze backtest results and identify issues"""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {filename}")
    print(f"{'='*80}")
    
    if not results:
        print("  ✗ File not found or empty")
        return
    
    symbols = list(results.keys())
    print(f"\nSymbols tested: {len(symbols)}")
    
    # Aggregate statistics
    all_returns = []
    all_sharpes = []
    all_trades = []
    all_win_rates = []
    all_drawdowns = []
    
    strategy_stats = {
        'mean_reversion': {'returns': [], 'trades': [], 'win_rates': []},
        'momentum': {'returns': [], 'trades': [], 'win_rates': []},
        'volatility_arb': {'returns': [], 'trades': [], 'win_rates': []}
    }
    
    issues = []
    
    for symbol, strategies in results.items():
        for strategy_name, strategy_results in strategies.items():
            if strategy_results is None:
                continue
            
            # Check for suspicious patterns
            if strategy_results.get('total_trades', 0) == 1:
                issues.append(f"⚠ {symbol} - {strategy_name}: Only 1 trade (likely error)")
            
            if strategy_results.get('win_rate', 0) == 0.0 and strategy_results.get('total_trades', 0) > 0:
                issues.append(f"⚠ {symbol} - {strategy_name}: 0% win rate with {strategy_results['total_trades']} trades")
            
            if strategy_results.get('total_return', 0) < -10:
                issues.append(f"⚠ {symbol} - {strategy_name}: Large loss ({strategy_results['total_return']:.2f}%)")
            
            # Collect statistics
            all_returns.append(strategy_results.get('total_return', 0))
            all_sharpes.append(strategy_results.get('sharpe_ratio', 0))
            all_trades.append(strategy_results.get('total_trades', 0))
            all_win_rates.append(strategy_results.get('win_rate', 0))
            all_drawdowns.append(strategy_results.get('max_drawdown', 0))
            
            if strategy_name in strategy_stats:
                strategy_stats[strategy_name]['returns'].append(strategy_results.get('total_return', 0))
                strategy_stats[strategy_name]['trades'].append(strategy_results.get('total_trades', 0))
                strategy_stats[strategy_name]['win_rates'].append(strategy_results.get('win_rate', 0))
    
    # Print summary statistics
    print(f"\n{'─'*80}")
    print("AGGREGATE STATISTICS")
    print(f"{'─'*80}")
    
    if all_returns:
        print(f"\nOverall Performance:")
        print(f"  Average Return: {np.mean(all_returns):.2f}%")
        print(f"  Median Return: {np.median(all_returns):.2f}%")
        print(f"  Best Return: {np.max(all_returns):.2f}%")
        print(f"  Worst Return: {np.min(all_returns):.2f}%")
        print(f"  Positive Returns: {sum(1 for r in all_returns if r > 0)} / {len(all_returns)} ({sum(1 for r in all_returns if r > 0)/len(all_returns)*100:.1f}%)")
        
        print(f"\nRisk Metrics:")
        print(f"  Average Sharpe: {np.mean(all_sharpes):.2f}")
        print(f"  Average Max DD: {np.mean(all_drawdowns):.2f}%")
        print(f"  Average Win Rate: {np.mean(all_win_rates)*100:.1f}%")
        
        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {sum(all_trades)}")
        print(f"  Average Trades per Strategy: {np.mean(all_trades):.1f}")
        print(f"  Strategies with <5 trades: {sum(1 for t in all_trades if t < 5)}")
    
    # Strategy-specific statistics
    print(f"\n{'─'*80}")
    print("STRATEGY-SPECIFIC STATISTICS")
    print(f"{'─'*80}")
    
    for strategy_name, stats in strategy_stats.items():
        if stats['returns']:
            print(f"\n{strategy_name.upper().replace('_', ' ')}:")
            print(f"  Average Return: {np.mean(stats['returns']):.2f}%")
            print(f"  Positive Returns: {sum(1 for r in stats['returns'] if r > 0)} / {len(stats['returns'])}")
            print(f"  Average Trades: {np.mean(stats['trades']):.1f}")
            print(f"  Average Win Rate: {np.mean(stats['win_rates'])*100:.1f}%")
    
    # Print issues
    if issues:
        print(f"\n{'─'*80}")
        print(f"ISSUES DETECTED ({len(issues)}):")
        print(f"{'─'*80}")
        for issue in issues[:20]:  # Limit to first 20
            print(f"  {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more issues")
    
    return {
        'total_strategies': len(all_returns),
        'avg_return': np.mean(all_returns) if all_returns else 0,
        'avg_sharpe': np.mean(all_sharpes) if all_sharpes else 0,
        'total_trades': sum(all_trades),
        'issues': len(issues)
    }

def compare_results(file1_results, file2_results):
    """Compare two backtest result files"""
    print(f"\n{'='*80}")
    print("COMPARING BACKTEST RESULTS")
    print(f"{'='*80}")
    
    if not file1_results or not file2_results:
        print("Cannot compare - one or both files missing")
        return
    
    # Find common symbols
    symbols1 = set(file1_results.keys())
    symbols2 = set(file2_results.keys())
    common_symbols = symbols1 & symbols2
    
    print(f"\nCommon symbols: {len(common_symbols)}")
    print(f"File 1 only: {len(symbols1 - symbols2)}")
    print(f"File 2 only: {len(symbols2 - symbols1)}")
    
    # Compare performance for common symbols
    differences = []
    for symbol in list(common_symbols)[:5]:  # Check first 5
        for strategy in ['mean_reversion', 'momentum', 'volatility_arb']:
            r1 = file1_results[symbol].get(strategy)
            r2 = file2_results[symbol].get(strategy)
            
            if r1 and r2:
                ret_diff = r2.get('total_return', 0) - r1.get('total_return', 0)
                trades_diff = r2.get('total_trades', 0) - r1.get('total_trades', 0)
                
                if abs(ret_diff) > 1 or abs(trades_diff) > 0:
                    differences.append({
                        'symbol': symbol,
                        'strategy': strategy,
                        'return_diff': ret_diff,
                        'trades_diff': trades_diff
                    })
    
    if differences:
        print(f"\nNotable differences found in {len(differences)} strategy-symbol pairs")
        for diff in differences[:5]:
            print(f"  {diff['symbol']} - {diff['strategy']}: "
                  f"Return diff: {diff['return_diff']:.2f}%, "
                  f"Trades diff: {diff['trades_diff']}")

def verify_data_quality():
    """Check data quality for backtesting"""
    print(f"\n{'='*80}")
    print("DATA QUALITY CHECK")
    print(f"{'='*80}")
    
    data_dir = Path(__file__).parent / 'data'
    csv_files = list(data_dir.glob('*_1h.csv'))
    
    print(f"\nFound {len(csv_files)} data files")
    
    issues = []
    stats = []
    
    for csv_file in csv_files[:10]:  # Check first 10
        try:
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            
            # Check data quality
            if len(df) < 100:
                issues.append(f"{csv_file.name}: Only {len(df)} rows (need at least 100)")
            
            if df['close'].isna().sum() > 0:
                issues.append(f"{csv_file.name}: {df['close'].isna().sum()} NaN values in close")
            
            if (df['close'] <= 0).any():
                issues.append(f"{csv_file.name}: Non-positive prices found")
            
            stats.append({
                'file': csv_file.name,
                'rows': len(df),
                'date_range': f"{df.index[0]} to {df.index[-1]}",
                'price_range': f"${df['close'].min():.6f} - ${df['close'].max():.6f}"
            })
            
        except Exception as e:
            issues.append(f"{csv_file.name}: Error reading - {e}")
    
    if stats:
        print(f"\nSample data files:")
        for stat in stats[:5]:
            print(f"  {stat['file']}: {stat['rows']} rows, {stat['date_range']}")
    
    if issues:
        print(f"\nData quality issues ({len(issues)}):")
        for issue in issues[:10]:
            print(f"  ⚠ {issue}")
    else:
        print(f"\n✓ No data quality issues detected")
    
    return len(issues) == 0

def main():
    """Main verification function"""
    print("="*80)
    print("BACKTEST RESULTS VERIFICATION")
    print("="*80)
    
    research_dir = Path(__file__).parent / 'research'
    
    # Load both result files
    results1 = load_backtest_results(research_dir / 'backtest_results.json')
    results2 = load_backtest_results(research_dir / 'backtest_results_corrected.json')
    
    # Analyze each file
    summary1 = analyze_results(results1, 'backtest_results.json')
    summary2 = analyze_results(results2, 'backtest_results_corrected.json')
    
    # Compare if both exist
    if results1 and results2:
        compare_results(results1, results2)
    
    # Verify data quality
    data_ok = verify_data_quality()
    
    # Final summary
    print(f"\n{'='*80}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*80}")
    
    if summary1:
        print(f"\nbacktest_results.json:")
        print(f"  Total strategies: {summary1['total_strategies']}")
        print(f"  Average return: {summary1['avg_return']:.2f}%")
        print(f"  Total trades: {summary1['total_trades']}")
        print(f"  Issues: {summary1['issues']}")
    
    if summary2:
        print(f"\nbacktest_results_corrected.json:")
        print(f"  Total strategies: {summary2['total_strategies']}")
        print(f"  Average return: {summary2['avg_return']:.2f}%")
        print(f"  Total trades: {summary2['total_trades']}")
        print(f"  Issues: {summary2['issues']}")
    
    print(f"\nData quality: {'✓ PASS' if data_ok else '⚠ ISSUES FOUND'}")
    
    # Recommendations
    print(f"\n{'─'*80}")
    print("RECOMMENDATIONS")
    print(f"{'─'*80}")
    
    if results1 and summary1['issues'] > 10:
        print("  ⚠ backtest_results.json shows many issues - likely incorrect")
        print("    → Use backtest_results_corrected.json instead")
    
    if summary2 and summary2['avg_return'] < 0:
        print("  ⚠ Average returns are negative - strategies may need optimization")
        print("    → Review strategy parameters")
        print("    → Check entry/exit logic")
        print("    → Consider different timeframes or filters")
    
    if summary2 and summary2['total_trades'] < 100:
        print("  ⚠ Low trade count - may need longer data period or different parameters")
        print("    → Fetch more historical data")
        print("    → Adjust signal thresholds")
    
    print("\n✓ Verification complete")

if __name__ == '__main__':
    main()
