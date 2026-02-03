"""Simplified backtesting engine - processes all signals without position management issues"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    max_leverage: float = 20.0
    fee_rate: float = 0.0001
    slippage_bps: float = 5.0
    max_position_size_pct: float = 0.25

class SimpleBacktestEngine:
    """Simplified vectorized backtesting"""
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
    
    def backtest_strategy(self, data: pd.DataFrame, signals: pd.DataFrame, symbol: str = '') -> Dict:
        """
        Run backtest on signals
        
        Args:
            data: OHLCV data with 'close' column
            signals: DataFrame with 'signal' (1/-1/0) and 'strength' columns
            symbol: Trading pair name
            
        Returns:
            Dict with performance metrics
        """
        
        # Calculate returns
        returns = data['close'].pct_change()
        
        # Position tracking
        positions = signals['signal'].copy()
        # positions already in {-1, 0, 1} from signal generation
        
        # Strategy returns (position * market returns - fees)
        fees = returns.abs() * self.config.fee_rate
        strategy_returns = positions.shift(1) * returns - fees
        
        # Cumulative returns
        cumulative_returns = (1 + strategy_returns).cumprod()
        total_return = (cumulative_returns.iloc[-1] - 1) * 100  # %
        
        # Calculate metrics
        equity = self.config.initial_capital * cumulative_returns
        
        # Sharpe ratio
        excess_returns = strategy_returns - 0.0001  # Risk-free rate
        sharpe = excess_returns.mean() / (excess_returns.std() + 1e-8) * np.sqrt(252)
        
        # Sortino ratio (downside deviation)
        downside = excess_returns[excess_returns < 0]
        sortino = excess_returns.mean() / (downside.std() + 1e-8) * np.sqrt(252) if len(downside) > 0 else 0
        
        # Max drawdown
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        max_drawdown = abs(drawdown.min()) * 100  # %
        
        # Win rate & trade analysis
        signal_changes = (signals['signal'] != signals['signal'].shift(1)).sum()  # Actual trades
        winning_trades = (strategy_returns > 0).sum()
        win_rate = winning_trades / max(signal_changes, 1)
        
        # Direction breakdown
        long_signals = (signals['signal'] == 1).sum()
        short_signals = (signals['signal'] == -1).sum()
        
        # Profit factor
        gross_profit = strategy_returns[strategy_returns > 0].sum()
        gross_loss = abs(strategy_returns[strategy_returns < 0].sum())
        profit_factor = gross_profit / max(gross_loss, 1e-8)
        
        return {
            'total_return': total_return,
            'sharpe_ratio': float(sharpe),
            'sortino_ratio': float(sortino),
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': float(profit_factor),
            'total_trades': int(signal_changes),
            'long_trades': int(long_signals),
            'short_trades': int(short_signals),
            'final_equity': float(equity.iloc[-1])
        }
