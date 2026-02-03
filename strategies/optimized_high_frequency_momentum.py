"""
Optimized High-Frequency Momentum Strategy
- Dynamic leverage based on signal strength
- Relaxed filters for more volume
- Better risk management
"""

import pandas as pd
import numpy as np
from typing import Dict
from .high_frequency_momentum import HighFrequencyMomentumStrategy

class OptimizedHighFrequencyMomentumStrategy(HighFrequencyMomentumStrategy):
    """
    Optimized version with:
    - Dynamic leverage (10x-20x based on signal strength)
    - More relaxed filters for higher volume
    - Better trade frequency
    """
    
    def __init__(self, params: Dict = None, timeframe: str = '5m'):
        # Start with parent defaults
        super().__init__(params, timeframe)
        
        # Override with more relaxed parameters
        self.params.update({
            'momentum_threshold': 0.003,  # Lowered from 0.005 (0.3% vs 0.5%)
            'volume_multiplier': 1.05,  # Lowered from 1.1 (5% vs 10%)
            'min_volume_percentile': 15,  # Lowered from 20
            'trend_strength_threshold': 0.0005,  # Lowered from 0.001
            'signal_strength_min': 0.15,  # Lowered from 0.2
            'dynamic_leverage': True,  # Enable dynamic leverage
            'leverage_strong': 20.0,  # Strong signals (>0.7)
            'leverage_medium': 15.0,  # Medium signals (0.4-0.7)
            'leverage_weak': 10.0,  # Weak signals (0.15-0.4)
            'filter_requirement': 1,  # Require only 1 of 4 optional filters (vs 2)
        })
    
    def calculate_leverage(self, signal_strength: float) -> float:
        """Calculate dynamic leverage based on signal strength"""
        if not self.params.get('dynamic_leverage', False):
            return self.params.get('max_leverage', 20.0)
        
        if signal_strength >= 0.7:
            return self.params['leverage_strong']
        elif signal_strength >= 0.4:
            return self.params['leverage_medium']
        else:
            return self.params['leverage_weak']
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals with optimized filters"""
        indicators = self.calculate_indicators(data)
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals['strength'] = 0.0
        signals['leverage'] = 1.0  # Store leverage for each signal
        signals['stop_loss'] = np.nan
        signals['take_profit'] = np.nan
        
        # Core requirements (must have) - more relaxed
        long_entry_core = (
            (indicators['ema_fast'] > indicators['ema_slow']) &
            (indicators['momentum'] > self.params['momentum_threshold']) &
            (indicators['rsi'] > self.params['rsi_neutral_low']) &
            (indicators['rsi'] < self.params['rsi_overbought'])
        )
        
        # Additional filters (only need 1 of 4 now)
        filter_requirement = self.params.get('filter_requirement', 1)
        long_entry_filters = (
            (indicators['trend_strength'] > self.params['trend_strength_threshold']).astype(int) +
            (indicators['volume_ratio'] > self.params['volume_multiplier']).astype(int) +
            (indicators['macd_hist'] > 0).astype(int) +
            (indicators['price_position'] > 0.3).astype(int)
        ) >= filter_requirement
        
        long_entry_base = long_entry_core & long_entry_filters & (indicators['volume_percentile'] > self.params['min_volume_percentile'])
        
        short_entry_core = (
            (indicators['ema_fast'] < indicators['ema_slow']) &
            (indicators['momentum'] < -self.params['momentum_threshold']) &
            (indicators['rsi'] < self.params['rsi_neutral_high']) &
            (indicators['rsi'] > self.params['rsi_oversold'])
        )
        
        short_entry_filters = (
            (indicators['trend_strength'] > self.params['trend_strength_threshold']).astype(int) +
            (indicators['volume_ratio'] > self.params['volume_multiplier']).astype(int) +
            (indicators['macd_hist'] < 0).astype(int) +
            (indicators['price_position'] < 0.7).astype(int)
        ) >= filter_requirement
        
        short_entry_base = short_entry_core & short_entry_filters & (indicators['volume_percentile'] > self.params['min_volume_percentile'])
        
        # Position tracking
        position = 0
        entry_time = None
        entry_price = None
        entry_atr = None
        entry_leverage = None
        highest_price = None
        lowest_price = None
        
        for i in range(len(signals)):
            current_price = data['close'].iloc[i]
            current_atr = indicators['atr'].iloc[i]
            
            if position == 0:
                # Look for entry
                if long_entry_base.iloc[i]:
                    # Calculate signal strength
                    momentum_strength = min(
                        indicators['momentum'].iloc[i] / (self.params['momentum_threshold'] * 3), 1.0
                    )
                    volume_strength = min(
                        (indicators['volume_ratio'].iloc[i] - 1.0) / 2.0, 1.0
                    )
                    trend_strength = min(
                        indicators['trend_strength'].iloc[i] / 0.5, 1.0
                    )
                    signal_strength = (momentum_strength * 0.4 + volume_strength * 0.3 + trend_strength * 0.3)
                    
                    if signal_strength > self.params['signal_strength_min']:
                        # Calculate dynamic leverage
                        leverage = self.calculate_leverage(signal_strength)
                        
                        signals.iloc[i, signals.columns.get_loc('signal')] = 1
                        signals.iloc[i, signals.columns.get_loc('strength')] = signal_strength
                        signals.iloc[i, signals.columns.get_loc('leverage')] = leverage
                        
                        # Set stop loss and take profit (ATR-based)
                        stop_loss_price = current_price - (current_atr * self.params['atr_stop_multiplier'])
                        take_profit_price = current_price + (current_atr * self.params['atr_take_profit'])
                        
                        signals.iloc[i, signals.columns.get_loc('stop_loss')] = stop_loss_price
                        signals.iloc[i, signals.columns.get_loc('take_profit')] = take_profit_price
                        
                        position = 1
                        entry_time = signals.index[i]
                        entry_price = current_price
                        entry_atr = current_atr
                        entry_leverage = leverage
                        highest_price = current_price
                
                elif short_entry_base.iloc[i]:
                    momentum_strength = min(
                        abs(indicators['momentum'].iloc[i]) / (self.params['momentum_threshold'] * 3), 1.0
                    )
                    volume_strength = min(
                        (indicators['volume_ratio'].iloc[i] - 1.0) / 2.0, 1.0
                    )
                    trend_strength = min(
                        indicators['trend_strength'].iloc[i] / 0.5, 1.0
                    )
                    signal_strength = (momentum_strength * 0.4 + volume_strength * 0.3 + trend_strength * 0.3)
                    
                    if signal_strength > self.params['signal_strength_min']:
                        leverage = self.calculate_leverage(signal_strength)
                        
                        signals.iloc[i, signals.columns.get_loc('signal')] = -1
                        signals.iloc[i, signals.columns.get_loc('strength')] = signal_strength
                        signals.iloc[i, signals.columns.get_loc('leverage')] = leverage
                        
                        stop_loss_price = current_price + (current_atr * self.params['atr_stop_multiplier'])
                        take_profit_price = current_price - (current_atr * self.params['atr_take_profit'])
                        
                        signals.iloc[i, signals.columns.get_loc('stop_loss')] = stop_loss_price
                        signals.iloc[i, signals.columns.get_loc('take_profit')] = take_profit_price
                        
                        position = -1
                        entry_time = signals.index[i]
                        entry_price = current_price
                        entry_atr = current_atr
                        entry_leverage = leverage
                        lowest_price = current_price
            
            else:
                # Manage open position (same as parent class)
                try:
                    entry_idx = signals.index.get_loc(entry_time)
                    periods_held = i - entry_idx
                except:
                    periods_held = 0
                
                # Update highest/lowest for trailing stop
                if position == 1:
                    highest_price = max(highest_price, current_price)
                    profit_atr = (highest_price - entry_price) / entry_atr if entry_atr and entry_atr > 0 else 0
                else:
                    lowest_price = min(lowest_price, current_price)
                    profit_atr = (entry_price - lowest_price) / entry_atr if entry_atr and entry_atr > 0 else 0
                
                # Check stop loss (using entry_atr and entry_leverage)
                if position == 1:
                    if current_price <= entry_price - (entry_atr * self.params['atr_stop_multiplier']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        entry_leverage = None
                        highest_price = None
                elif position == -1:
                    if current_price >= entry_price + (entry_atr * self.params['atr_stop_multiplier']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        entry_leverage = None
                        lowest_price = None
                
                # Check take profit
                elif position == 1:
                    if current_price >= entry_price + (entry_atr * self.params['atr_take_profit']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        entry_leverage = None
                        highest_price = None
                elif position == -1:
                    if current_price <= entry_price - (entry_atr * self.params['atr_take_profit']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        entry_leverage = None
                        lowest_price = None
                
                # Trailing stop
                elif profit_atr >= self.params['trailing_stop_activation']:
                    if position == 1:
                        trailing_stop = highest_price - (entry_atr * self.params['trailing_stop_distance'])
                        if current_price <= trailing_stop:
                            signals.iloc[i, signals.columns.get_loc('signal')] = 0
                            position = 0
                            entry_time = None
                            entry_price = None
                            entry_atr = None
                            entry_leverage = None
                            highest_price = None
                    elif position == -1:
                        trailing_stop = lowest_price + (entry_atr * self.params['trailing_stop_distance'])
                        if current_price >= trailing_stop:
                            signals.iloc[i, signals.columns.get_loc('signal')] = 0
                            position = 0
                            entry_time = None
                            entry_price = None
                            entry_atr = None
                            entry_leverage = None
                            lowest_price = None
                
                # Exit on trend reversal
                elif position == 1:
                    if (indicators['ema_fast'].iloc[i] < indicators['ema_slow'].iloc[i] or
                        indicators['macd_hist'].iloc[i] < 0):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        entry_leverage = None
                        highest_price = None
                elif position == -1:
                    if (indicators['ema_fast'].iloc[i] > indicators['ema_slow'].iloc[i] or
                        indicators['macd_hist'].iloc[i] > 0):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        entry_leverage = None
                        lowest_price = None
                
                # Force exit on max hold time
                elif periods_held >= self.params['max_hold_periods']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
                    entry_price = None
                    entry_atr = None
                    entry_leverage = None
                    highest_price = None
                    lowest_price = None
        
        return signals
