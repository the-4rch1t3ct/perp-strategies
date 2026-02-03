"""
Vectorized Backtesting Engine for Memecoin Perpetual Futures
Includes realistic fees (0.0001%) and slippage modeling
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class PositionSide(Enum):
    LONG = 1
    SHORT = -1
    FLAT = 0

@dataclass
class Trade:
    """Represents a single trade"""
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    symbol: str
    side: PositionSide
    entry_price: float
    exit_price: float
    size: float
    leverage: float
    pnl: float
    fees: float
    slippage: float

@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    initial_capital: float = 10000.0
    max_leverage: float = 20.0
    fee_rate: float = 0.0001  # 0.0001% = 0.000001
    slippage_bps: float = 5.0  # 5 basis points slippage
    max_position_size_pct: float = 0.25  # Max 25% of capital per position
    stop_loss_pct: float = 0.05  # 5% stop loss
    take_profit_pct: Optional[float] = None
    max_drawdown_pct: float = 0.30  # 30% max drawdown
    commission_per_trade: float = 0.0

class BacktestEngine:
    """Vectorized backtesting engine"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.trades: List[Trade] = []
        self.equity_curve: pd.Series = None
        self.positions: Dict[str, Dict] = {}
        
    def calculate_slippage(self, price: float, side: PositionSide) -> float:
        """Calculate slippage cost"""
        slippage_pct = self.config.slippage_bps / 10000.0
        if side == PositionSide.LONG:
            return price * (1 + slippage_pct)  # Pay more to buy
        else:
            return price * (1 - slippage_pct)  # Get less to sell
    
    def calculate_fees(self, notional: float) -> float:
        """Calculate trading fees"""
        return notional * self.config.fee_rate
    
    def calculate_position_size(self, price: float, signal_strength: float = 1.0) -> float:
        """
        Calculate position size based on risk management
        
        Args:
            price: Entry price
            signal_strength: 0-1, adjusts position size
            
        Returns:
            Position size in base currency
        """
        # Base position size as % of capital
        base_size_pct = self.config.max_position_size_pct * signal_strength
        
        # Account for leverage
        notional = self.config.initial_capital * base_size_pct * self.config.max_leverage
        position_size = notional / price
        
        return position_size
    
    def check_stop_loss(self, entry_price: float, current_price: float, 
                       side: PositionSide) -> bool:
        """Check if stop loss is triggered"""
        if side == PositionSide.LONG:
            return current_price <= entry_price * (1 - self.config.stop_loss_pct)
        else:
            return current_price >= entry_price * (1 + self.config.stop_loss_pct)
    
    def check_take_profit(self, entry_price: float, current_price: float,
                         side: PositionSide) -> bool:
        """Check if take profit is triggered"""
        if self.config.take_profit_pct is None:
            return False
        
        if side == PositionSide.LONG:
            return current_price >= entry_price * (1 + self.config.take_profit_pct)
        else:
            return current_price <= entry_price * (1 - self.config.take_profit_pct)
    
    def backtest_strategy(self, 
                         data: pd.DataFrame,
                         signals: pd.DataFrame,
                         symbol: str = 'UNKNOWN') -> Dict:
        """
        Backtest a strategy on historical data
        
        Args:
            data: OHLCV DataFrame with index as timestamp
            signals: DataFrame with columns: 'signal' (1=long, -1=short, 0=flat), 
                    'strength' (0-1), 'entry_time', 'exit_time'
        
        Returns:
            Dictionary with backtest results
        """
        capital = self.config.initial_capital
        equity_curve = [capital]
        current_position = None
        last_exit_time = None  # Track last exit for cooldown
        
        for i in range(len(data)):
            timestamp = data.index[i]
            price = data['close'].iloc[i]
            
            # Check for exit signals
            if current_position is not None:
                # Check stop loss
                if self.check_stop_loss(current_position['entry_price'], price, 
                                       current_position['side']):
                    # Exit position
                    exit_price = self.calculate_slippage(price, current_position['side'])
                    pnl = self._calculate_pnl(
                        current_position['entry_price'],
                        exit_price,
                        current_position['size'],
                        current_position['side'],
                        current_position['leverage']
                    )
                    
                    fees = self.calculate_fees(current_position['size'] * price) * 2
                    capital += pnl - fees
                    
                    trade = Trade(
                        entry_time=current_position['entry_time'],
                        exit_time=timestamp,
                        symbol=symbol,
                        side=current_position['side'],
                        entry_price=current_position['entry_price'],
                        exit_price=exit_price,
                        size=current_position['size'],
                        leverage=current_position['leverage'],
                        pnl=pnl,
                        fees=fees,
                        slippage=abs(exit_price - price) * current_position['size']
                    )
                    self.trades.append(trade)
                    current_position = None
                
                # Check take profit
                elif self.check_take_profit(current_position['entry_price'], price,
                                          current_position['side']):
                    exit_price = self.calculate_slippage(price, current_position['side'])
                    pnl = self._calculate_pnl(
                        current_position['entry_price'],
                        exit_price,
                        current_position['size'],
                        current_position['side'],
                        current_position['leverage']
                    )
                    
                    fees = self.calculate_fees(current_position['size'] * price) * 2
                    capital += pnl - fees
                    
                    trade = Trade(
                        entry_time=current_position['entry_time'],
                        exit_time=timestamp,
                        symbol=symbol,
                        side=current_position['side'],
                        entry_price=current_position['entry_price'],
                        exit_price=exit_price,
                        size=current_position['size'],
                        leverage=current_position['leverage'],
                        pnl=pnl,
                        fees=fees,
                        slippage=abs(exit_price - price) * current_position['size']
                    )
                    self.trades.append(trade)
                    current_position = None
                    last_exit_time = timestamp  # Record exit time for faster re-entry
            
            # Check for entry signals - allow immediate re-entry (no cooldown)
            if current_position is None and i < len(signals):
                signal_row = signals.iloc[i]
                signal = signal_row.get('signal', 0)
                strength = signal_row.get('strength', 1.0)
                signal_leverage = signal_row.get('leverage', self.config.max_leverage)  # Use dynamic leverage if available
                
                if signal != 0:
                    side = PositionSide.LONG if signal > 0 else PositionSide.SHORT
                    entry_price = self.calculate_slippage(price, side)
                    position_size = self.calculate_position_size(entry_price, strength)
                    
                    # Use signal leverage if provided, otherwise use max_leverage
                    leverage = min(signal_leverage, self.config.max_leverage)  # Cap at max_leverage
                    
                    # Check if we have enough capital
                    notional = position_size * entry_price
                    required_margin = notional / leverage
                    
                    if required_margin <= capital:
                        fees = self.calculate_fees(notional)
                        capital -= fees
                        
                        current_position = {
                            'entry_time': timestamp,
                            'entry_price': entry_price,
                            'size': position_size,
                            'side': side,
                            'leverage': leverage
                        }
            
            # Check max drawdown
            if len(equity_curve) > 0:
                peak = max(equity_curve)
                drawdown = (peak - capital) / peak
                if drawdown > self.config.max_drawdown_pct:
                    # Force close all positions and stop trading
                    if current_position:
                        exit_price = self.calculate_slippage(price, current_position['side'])
                        pnl = self._calculate_pnl(
                            current_position['entry_price'],
                            exit_price,
                            current_position['size'],
                            current_position['side'],
                            current_position['leverage']
                        )
                        fees = self.calculate_fees(current_position['size'] * price)
                        capital += pnl - fees
                        current_position = None
                    break
            
            equity_curve.append(capital)
        
        # Close any remaining position at end
        if current_position:
            final_price = data['close'].iloc[-1]
            exit_price = self.calculate_slippage(final_price, current_position['side'])
            pnl = self._calculate_pnl(
                current_position['entry_price'],
                exit_price,
                current_position['size'],
                current_position['side'],
                current_position['leverage']
            )
            fees = self.calculate_fees(current_position['size'] * final_price)
            capital += pnl - fees
            
            trade = Trade(
                entry_time=current_position['entry_time'],
                exit_time=data.index[-1],
                symbol=symbol,
                side=current_position['side'],
                entry_price=current_position['entry_price'],
                exit_price=exit_price,
                size=current_position['size'],
                leverage=current_position['leverage'],
                pnl=pnl,
                fees=fees,
                slippage=abs(exit_price - final_price) * current_position['size']
            )
            self.trades.append(trade)
            equity_curve[-1] = capital
        
        # Align equity curve with data index (equity_curve has one extra element for initial capital)
        if len(equity_curve) == len(data.index) + 1:
            # Use data index, drop first element (initial capital)
            self.equity_curve = pd.Series(equity_curve[1:], index=data.index)
        elif len(equity_curve) == len(data.index):
            # Already aligned
            self.equity_curve = pd.Series(equity_curve, index=data.index)
        else:
            # Truncate or pad to match
            min_len = min(len(equity_curve), len(data.index))
            self.equity_curve = pd.Series(equity_curve[-min_len:], index=data.index[-min_len:])
        
        return self._calculate_metrics()
    
    def _calculate_pnl(self, entry_price: float, exit_price: float,
                      size: float, side: PositionSide, leverage: float) -> float:
        """Calculate P&L for a trade"""
        if side == PositionSide.LONG:
            price_change = (exit_price - entry_price) / entry_price
        else:
            price_change = (entry_price - exit_price) / entry_price
        
        notional = size * entry_price
        pnl = notional * price_change * leverage
        
        return pnl
    
    def _calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_trades': 0
            }
        
        # Equity curve metrics
        returns = self.equity_curve.pct_change().dropna()
        total_return = (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1) * 100
        
        # Sharpe ratio (assuming 1h returns, annualize)
        if returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(24 * 365)
        else:
            sharpe = 0.0
        
        # Sortino ratio (downside deviation only)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino = (returns.mean() / downside_returns.std()) * np.sqrt(24 * 365)
        else:
            sortino = 0.0
        
        # Max drawdown
        peak = self.equity_curve.expanding().max()
        drawdown = (self.equity_curve - peak) / peak
        max_drawdown = abs(drawdown.min()) * 100
        
        # Trade statistics
        trade_pnls = [t.pnl for t in self.trades]
        winning_trades = [pnl for pnl in trade_pnls if pnl > 0]
        losing_trades = [pnl for pnl in trade_pnls if pnl < 0]
        
        win_rate = len(winning_trades) / len(trade_pnls) if trade_pnls else 0.0
        
        gross_profit = sum(winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(self.trades),
            'avg_win': np.mean(winning_trades) if winning_trades else 0.0,
            'avg_loss': np.mean(losing_trades) if losing_trades else 0.0,
            'total_pnl': sum(trade_pnls),
            'total_fees': sum(t.fees for t in self.trades),
            'equity_curve': self.equity_curve,
            'trades': self.trades
        }
