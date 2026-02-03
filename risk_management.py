"""
Risk Management Module
Position sizing, stop-loss, drawdown limits, risk-of-ruin calculations
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from scipy import stats

class RiskManager:
    """Manages risk across the portfolio"""
    
    def __init__(self, 
                 initial_capital: float = 10000.0,
                 max_leverage: float = 20.0,
                 max_position_size_pct: float = 0.25,
                 max_portfolio_risk_pct: float = 0.02,  # 2% risk per trade
                 max_drawdown_pct: float = 0.30,
                 risk_free_rate: float = 0.05):  # 5% annual
        self.initial_capital = initial_capital
        self.max_leverage = max_leverage
        self.max_position_size_pct = max_position_size_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.risk_free_rate = risk_free_rate
    
    def calculate_kelly_criterion(self, win_rate: float, avg_win: float, 
                                  avg_loss: float) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing
        
        Returns:
            Kelly percentage (0-1)
        """
        if avg_loss == 0:
            return 0.0
        
        win_loss_ratio = avg_win / abs(avg_loss)
        kelly = (win_rate * (win_loss_ratio + 1) - 1) / win_loss_ratio
        
        # Fractional Kelly (use 25% for safety)
        return max(0.0, min(0.25, kelly * 0.25))
    
    def calculate_position_size(self, 
                                current_capital: float,
                                entry_price: float,
                                stop_loss_price: float,
                                signal_strength: float = 1.0,
                                volatility: float = None) -> Tuple[float, float]:
        """
        Calculate optimal position size based on risk
        
        Args:
            current_capital: Current account equity
            entry_price: Entry price
            stop_loss_price: Stop loss price
            signal_strength: 0-1, adjusts position size
            volatility: Optional volatility for volatility-adjusted sizing
        
        Returns:
            Tuple of (position_size, notional_value)
        """
        # Risk per trade
        risk_amount = current_capital * self.max_portfolio_risk_pct * signal_strength
        
        # Price risk
        price_risk_pct = abs(entry_price - stop_loss_price) / entry_price
        
        if price_risk_pct == 0:
            return 0.0, 0.0
        
        # Base position size
        notional = risk_amount / price_risk_pct
        
        # Apply leverage
        notional *= self.max_leverage
        
        # Cap at max position size
        max_notional = current_capital * self.max_position_size_pct * self.max_leverage
        notional = min(notional, max_notional)
        
        # Volatility adjustment (reduce size in high vol)
        if volatility is not None:
            # Normalize volatility (assume 50% annual vol as baseline)
            vol_adjustment = min(1.0, 0.50 / max(volatility, 0.10))
            notional *= vol_adjustment
        
        position_size = notional / entry_price
        
        return position_size, notional
    
    def calculate_stop_loss(self, 
                           entry_price: float,
                           side: str,  # 'long' or 'short'
                           atr: float = None,
                           volatility: float = None) -> float:
        """
        Calculate stop loss price
        
        Args:
            entry_price: Entry price
            side: 'long' or 'short'
            atr: Average True Range (optional)
            volatility: Volatility percentage (optional)
        
        Returns:
            Stop loss price
        """
        # Default stop loss: 5% for longs, 5% above for shorts
        default_stop_pct = 0.05
        
        if atr is not None:
            # Use 2x ATR
            stop_pct = (2 * atr) / entry_price
            stop_pct = min(stop_pct, 0.10)  # Cap at 10%
        elif volatility is not None:
            # Use 1.5x volatility
            stop_pct = min(volatility * 1.5, 0.10)
        else:
            stop_pct = default_stop_pct
        
        if side == 'long':
            return entry_price * (1 - stop_pct)
        else:
            return entry_price * (1 + stop_pct)
    
    def calculate_take_profit(self,
                             entry_price: float,
                             side: str,
                             risk_reward_ratio: float = 2.0,
                             stop_loss_price: float = None) -> float:
        """
        Calculate take profit price based on risk-reward ratio
        
        Args:
            entry_price: Entry price
            side: 'long' or 'short'
            risk_reward_ratio: Desired risk-reward (e.g., 2.0 = 2:1)
            stop_loss_price: Stop loss price (if None, uses default)
        
        Returns:
            Take profit price
        """
        if stop_loss_price is None:
            stop_loss_price = self.calculate_stop_loss(entry_price, side)
        
        risk = abs(entry_price - stop_loss_price)
        reward = risk * risk_reward_ratio
        
        if side == 'long':
            return entry_price + reward
        else:
            return entry_price - reward
    
    def calculate_risk_of_ruin(self,
                              win_rate: float,
                              avg_win: float,
                              avg_loss: float,
                              num_trades: int,
                              initial_capital: float) -> float:
        """
        Calculate probability of ruin
        
        Returns:
            Probability of losing entire capital (0-1)
        """
        if avg_loss == 0 or win_rate <= 0:
            return 1.0
        
        # Risk per trade as % of capital
        risk_per_trade = abs(avg_loss) / initial_capital
        
        if risk_per_trade >= 1.0:
            return 1.0
        
        # Expected value per trade
        expected_value = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        
        if expected_value <= 0:
            return 1.0
        
        # Simplified ruin probability
        # Using formula: P(ruin) ≈ exp(-2 * EV * capital / variance)
        variance = (win_rate * (avg_win - expected_value)**2 + 
                   (1 - win_rate) * (avg_loss - expected_value)**2)
        
        if variance == 0:
            return 0.0
        
        ruin_prob = np.exp(-2 * expected_value * initial_capital / variance)
        
        return min(1.0, max(0.0, ruin_prob))
    
    def calculate_max_drawdown(self, equity_curve: pd.Series) -> Dict:
        """
        Calculate maximum drawdown statistics
        
        Returns:
            Dictionary with max_drawdown, duration, recovery info
        """
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak
        
        max_dd = abs(drawdown.min())
        max_dd_idx = drawdown.idxmin()
        
        # Find peak before drawdown
        peak_before = equity_curve.loc[:max_dd_idx].max()
        peak_before_idx = equity_curve.loc[:max_dd_idx].idxmax()
        
        # Find recovery point (if any)
        recovery_idx = None
        if max_dd_idx < len(equity_curve) - 1:
            post_dd = equity_curve.loc[max_dd_idx:]
            recovery = post_dd[post_dd >= peak_before]
            if len(recovery) > 0:
                recovery_idx = recovery.index[0]
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd * 100,
            'peak_before': peak_before,
            'peak_before_time': peak_before_idx,
            'drawdown_time': max_dd_idx,
            'recovery_time': recovery_idx,
            'drawdown_duration': (max_dd_idx - peak_before_idx).total_seconds() / 3600 if recovery_idx is None else None,
            'recovery_duration': (recovery_idx - max_dd_idx).total_seconds() / 3600 if recovery_idx else None
        }
    
    def calculate_sharpe_ratio(self, returns: pd.Series, periods_per_year: int = 8760) -> float:
        """Calculate Sharpe ratio (annualized)"""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (self.risk_free_rate / periods_per_year)
        sharpe = (excess_returns.mean() / returns.std()) * np.sqrt(periods_per_year)
        
        return sharpe
    
    def calculate_sortino_ratio(self, returns: pd.Series, periods_per_year: int = 8760) -> float:
        """Calculate Sortino ratio (downside deviation only)"""
        if len(returns) == 0:
            return 0.0
        
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (self.risk_free_rate / periods_per_year)
        sortino = (excess_returns.mean() / downside_returns.std()) * np.sqrt(periods_per_year)
        
        return sortino
    
    def check_portfolio_limits(self,
                              current_capital: float,
                              open_positions: Dict,
                              new_position_size: float,
                              new_position_notional: float) -> Tuple[bool, str]:
        """
        Check if new position violates portfolio limits
        
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check max drawdown
        drawdown = (self.initial_capital - current_capital) / self.initial_capital
        if drawdown > self.max_drawdown_pct:
            return False, f"Max drawdown exceeded: {drawdown*100:.2f}%"
        
        # Check total exposure
        total_notional = sum(pos.get('notional', 0) for pos in open_positions.values())
        total_notional += new_position_notional
        
        max_notional = current_capital * self.max_leverage
        if total_notional > max_notional:
            return False, f"Total exposure exceeds limit: {total_notional/max_notional*100:.2f}%"
        
        # Check individual position size
        if new_position_notional > current_capital * self.max_position_size_pct * self.max_leverage:
            return False, f"Position size exceeds limit"
        
        return True, "OK"
