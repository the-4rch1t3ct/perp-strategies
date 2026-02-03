"""
Main Runner for Memecoin Perpetual Futures Strategy System
Orchestrates data fetching, analysis, strategy backtesting, and reporting
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from data.fetch_data import MemecoinDataFetcher
from analysis.volatility_regimes import VolatilityRegimeAnalyzer, analyze_all_memecoins
from backtesting.engine import BacktestEngine, BacktestConfig
from strategies.base_strategy import MeanReversionStrategy, MomentumStrategy, VolatilityArbitrageStrategy
from risk_management import RiskManager

class MemecoinStrategySystem:
    """Main system orchestrator"""
    
    def __init__(self, data_dir='data', research_dir='research'):
        self.data_dir = data_dir
        self.research_dir = research_dir
        self.fetcher = MemecoinDataFetcher(data_dir=data_dir)
        self.analyzer = VolatilityRegimeAnalyzer()
        self.risk_manager = RiskManager(
            initial_capital=10000.0,
            max_leverage=20.0,
            max_position_size_pct=0.25,
            max_portfolio_risk_pct=0.02
        )
        
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(research_dir, exist_ok=True)
    
    def fetch_data(self, timeframe='1h', days=90):
        """Fetch historical data for all memecoins"""
        print("=" * 60)
        print("PHASE 1: DATA COLLECTION")
        print("=" * 60)
        
        data = self.fetcher.fetch_all_memecoins(timeframe=timeframe, days=days)
        
        print(f"\n✓ Fetched data for {len(data)} symbols")
        return data
    
    def analyze_volatility(self):
        """Analyze volatility regimes"""
        print("\n" + "=" * 60)
        print("PHASE 2: VOLATILITY ANALYSIS")
        print("=" * 60)
        
        results = analyze_all_memecoins(self.data_dir)
        
        # Save analysis results
        analysis_file = os.path.join(self.research_dir, 'volatility_analysis.json')
        analysis_summary = {}
        
        for symbol, data in results.items():
            stats = data['stats']
            analysis_summary[symbol] = {
                'mean_vol': float(stats['mean_vol']),
                'max_vol': float(stats['max_vol']),
                'spike_count': int(stats['spike_count'])
            }
        
        with open(analysis_file, 'w') as f:
            json.dump(analysis_summary, f, indent=2)
        
        print(f"\n✓ Analysis complete. Results saved to {analysis_file}")
        return results
    
    def backtest_strategy(self, strategy, symbol, data, config=None):
        """Backtest a single strategy on a single symbol"""
        if config is None:
            config = BacktestConfig(
                initial_capital=10000.0,
                max_leverage=20.0,
                fee_rate=0.0001,
                slippage_bps=5.0,
                max_position_size_pct=0.25,
                stop_loss_pct=0.05,
                max_drawdown_pct=0.30
            )
        
        engine = BacktestEngine(config)
        signals = strategy.generate_signals(data)
        
        results = engine.backtest_strategy(data, signals, symbol=symbol)
        return results
    
    def run_full_backtest(self, symbols=None, strategies=None):
        """Run backtests for all strategies on all symbols"""
        print("\n" + "=" * 60)
        print("PHASE 3: STRATEGY BACKTESTING")
        print("=" * 60)
        
        if symbols is None:
            # Load available data
            import glob
            csv_files = glob.glob(os.path.join(self.data_dir, '*_1h.csv'))
            symbols = [os.path.basename(f).replace('_1h.csv', '').replace('_', '/') 
                      for f in csv_files]
        
        if strategies is None:
            strategies = {
                'mean_reversion': MeanReversionStrategy(),
                'momentum': MomentumStrategy(),
                'volatility_arb': VolatilityArbitrageStrategy()
            }
        
        config = BacktestConfig(
            initial_capital=10000.0,
            max_leverage=20.0,
            fee_rate=0.0001,
            slippage_bps=5.0,
            max_position_size_pct=0.25,
            stop_loss_pct=0.05,
            max_drawdown_pct=0.30
        )
        
        all_results = {}
        
        for symbol in symbols[:10]:  # Limit to top 10 for initial run
            print(f"\nBacktesting {symbol}...")
            symbol_results = {}
            
            try:
                df = self.fetcher.load_data(symbol, timeframe='1h')
                if df.empty or len(df) < 100:
                    print(f"  ⚠ Insufficient data for {symbol}")
                    continue
                
                for strategy_name, strategy in strategies.items():
                    print(f"  Testing {strategy_name}...")
                    try:
                        results = self.backtest_strategy(strategy, symbol, df, config)
                        symbol_results[strategy_name] = {
                            'total_return': results['total_return'],
                            'sharpe_ratio': results['sharpe_ratio'],
                            'sortino_ratio': results['sortino_ratio'],
                            'max_drawdown': results['max_drawdown'],
                            'win_rate': results['win_rate'],
                            'profit_factor': results['profit_factor'],
                            'total_trades': results['total_trades']
                        }
                        print(f"    Return: {results['total_return']:.2f}% | "
                              f"Sharpe: {results['sharpe_ratio']:.2f} | "
                              f"Trades: {results['total_trades']}")
                    except Exception as e:
                        print(f"    ✗ Error: {e}")
                        symbol_results[strategy_name] = None
                
                all_results[symbol] = symbol_results
                
            except Exception as e:
                print(f"  ✗ Error loading {symbol}: {e}")
        
        # Save results
        results_file = os.path.join(self.research_dir, 'backtest_results.json')
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n✓ Backtest complete. Results saved to {results_file}")
        return all_results
    
    def generate_report(self, backtest_results=None):
        """Generate comprehensive research report"""
        print("\n" + "=" * 60)
        print("PHASE 4: REPORT GENERATION")
        print("=" * 60)
        
        report_file = os.path.join(self.research_dir, 'BACKTEST_REPORT.md')
        
        with open(report_file, 'w') as f:
            f.write("# Memecoin Perpetual Futures - Backtest Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Summary\n\n")
            
            if backtest_results:
                # Aggregate statistics
                all_returns = []
                all_sharpes = []
                all_trades = []
                
                for symbol, strategies in backtest_results.items():
                    for strategy_name, results in strategies.items():
                        if results:
                            all_returns.append(results['total_return'])
                            all_sharpes.append(results['sharpe_ratio'])
                            all_trades.append(results['total_trades'])
                
                if all_returns:
                    f.write(f"- **Average Return**: {np.mean(all_returns):.2f}%\n")
                    f.write(f"- **Average Sharpe**: {np.mean(all_sharpes):.2f}\n")
                    f.write(f"- **Total Trades**: {sum(all_trades)}\n\n")
                
                f.write("## Detailed Results\n\n")
                f.write("| Symbol | Strategy | Return % | Sharpe | Sortino | Max DD % | Win Rate | Trades |\n")
                f.write("|--------|----------|----------|--------|---------|----------|----------|--------|\n")
                
                for symbol, strategies in backtest_results.items():
                    for strategy_name, results in strategies.items():
                        if results:
                            f.write(f"| {symbol} | {strategy_name} | "
                                  f"{results['total_return']:.2f} | "
                                  f"{results['sharpe_ratio']:.2f} | "
                                  f"{results['sortino_ratio']:.2f} | "
                                  f"{results['max_drawdown']:.2f} | "
                                  f"{results['win_rate']*100:.1f} | "
                                  f"{results['total_trades']} |\n")
        
        print(f"✓ Report generated: {report_file}")
    
    def run_full_pipeline(self):
        """Run complete analysis pipeline"""
        print("\n" + "=" * 80)
        print("MEMECOIN PERPETUAL FUTURES STRATEGY SYSTEM")
        print("=" * 80)
        
        # Phase 1: Data Collection
        data = self.fetch_data(timeframe='1h', days=90)
        
        # Phase 2: Analysis
        volatility_results = self.analyze_volatility()
        
        # Phase 3: Backtesting
        backtest_results = self.run_full_backtest()
        
        # Phase 4: Reporting
        self.generate_report(backtest_results)
        
        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE")
        print("=" * 80)
        print(f"\nResults available in: {self.research_dir}/")
        print("  - volatility_analysis.json")
        print("  - backtest_results.json")
        print("  - BACKTEST_REPORT.md")


if __name__ == '__main__':
    system = MemecoinStrategySystem()
    
    # Run full pipeline
    system.run_full_pipeline()
