"""
Final Optimized High-Frequency Momentum Strategy
- Improved win rate (tighter filters)
- Optimized leverage distribution
- Better entry criteria
"""

import pandas as pd
import numpy as np
from typing import Dict
from .high_frequency_momentum import HighFrequencyMomentumStrategy

class FinalOptimizedMomentumStrategy(HighFrequencyMomentumStrategy):
    """
    Final optimized version with:
    - Tighter filters for better win rate (target 50%+)
    - Optimized leverage distribution (50% 10x, 35% 15x, 15% 20x)
    - Better entry criteria
    - Improved signal strength calculation
    """
    
    def __init__(self, params: Dict = None, timeframe: str = '5m'):
        # Start with parent defaults
        super().__init__(params, timeframe)
        
        # Optimized parameters for better win rate
        self.params.update({
            'momentum_threshold': 0.004,  # Slightly higher (0.4% vs 0.3%)
            'volume_multiplier': 1.08,  # Slightly higher (8% vs 5%)
            'min_volume_percentile': 25,  # Higher (25% vs 15%)
            'trend_strength_threshold': 0.0008,  # Higher (0.08% vs 0.05%)
            'signal_strength_min': 0.25,  # Higher (0.25 vs 0.15) - KEY CHANGE
            'dynamic_leverage': True,
            # Optimized leverage thresholds for target distribution
            'leverage_strong': 20.0,  # Signal strength > 0.65 (target 15%)
            'leverage_medium': 15.0,  # Signal strength 0.35-0.65 (target 35%)
            'leverage_weak': 10.0,  # Signal strength 0.25-0.35 (target 50%)
            'filter_requirement': 2,  # Require 2 of 4 filters (vs 1) - KEY CHANGE
            # Additional filters
            'rsi_trend_confirmation': True,  # RSI must align with trend
            'min_price_move': 0.002,  # Minimum 0.2% price move for entry
        })
    
    def calculate_leverage(self, signal_strength: float) -> float:
        """Calculate dynamic leverage with optimized thresholds"""
        if not self.params.get('dynamic_leverage', False):
            return self.params.get('max_leverage', 20.0)
        
        # Optimized thresholds for target distribution (50% 10x, 35% 15x, 15% 20x)
        if signal_strength >= 0.65:  # Top 15% of signals
            return self.params['leverage_strong']
        elif signal_strength >= 0.35:  # Next 35% of signals
            return self.params['leverage_medium']
        else:  # Bottom 50% of signals
            return self.params['leverage_weak']
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals with improved filters"""
        indicators = self.calculate_indicators(data)
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals['strength'] = 0.0
        signals['leverage'] = 1.0
        signals['stop_loss'] = np.nan
        signals['take_profit'] = np.nan
        
        # Core requirements (must have) - stricter
        long_entry_core = (
            (indicators['ema_fast'] > indicators['ema_slow']) &
            (indicators['momentum'] > self.params['momentum_threshold']) &
            (indicators['rsi'] > self.params['rsi_neutral_low']) &
            (indicators['rsi'] < self.params['rsi_overbought']) &
            (indicators['rsi'] > 50)  # RSI trend confirmation - must be above neutral
        )
        
        short_entry_core = (
            (indicators['ema_fast'] < indicators['ema_slow']) &
            (indicators['momentum'] < -self.params['momentum_threshold']) &
            (indicators['rsi'] < self.params['rsi_neutral_high']) &
            (indicators['rsi'] > self.params['rsi_oversold']) &
            (indicators['rsi'] < 50)  # RSI trend confirmation - must be below neutral
        )
        
        # Additional filters (require 2 of 4)
        filter_requirement = self.params.get('filter_requirement', 2)
        
        long_entry_filters = (
            (indicators['trend_strength'] > self.params['trend_strength_threshold']).astype(int) +
            (indicators['volume_ratio'] > self.params['volume_multiplier']).astype(int) +
            (indicators['macd_hist'] > 0).astype(int) +
            (indicators['price_position'] > 0.3).astype(int)
        ) >= filter_requirement
        
        short_entry_filters = (
            (indicators['trend_strength'] > self.params['trend_strength_threshold']).astype(int) +
            (indicators['volume_ratio'] > self.params['volume_multiplier']).astype(int) +
            (indicators['macd_hist'] < 0).astype(int) +
            (indicators['price_position'] < 0.7).astype(int)
        ) >= filter_requirement
        
        # Price move filter (avoid choppy markets)
        price_move = abs(indicators['momentum'])
        min_price_move_filter = price_move > self.params['min_price_move']
        
        long_entry_base = (
            long_entry_core & 
            long_entry_filters & 
            (indicators['volume_percentile'] > self.params['min_volume_percentile']) &
            min_price_move_filter
        )
        
        short_entry_base = (
            short_entry_core & 
            short_entry_filters & 
            (indicators['volume_percentile'] > self.params['min_volume_percentile']) &
            min_price_move_filter
        )
        
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
                    # Enhanced signal strength calculation
                    momentum_strength = min(
                        indicators['momentum'].iloc[i] / (self.params['momentum_threshold'] * 2.5), 1.0
                    )
                    volume_strength = min(
                        (indicators['volume_ratio'].iloc[i] - 1.0) / 1.5, 1.0
                    )
                    trend_strength = min(
                        indicators['trend_strength'].iloc[i] / 0.3, 1.0
                    )
                    rsi_strength = (indicators['rsi'].iloc[i] - 50) / 15  # Normalize RSI
                    rsi_strength = min(max(rsi_strength, 0), 1.0)
                    
                    # Weighted combination (momentum and trend more important)
                    signal_strength = (
                        momentum_strength * 0.35 +
                        volume_strength * 0.25 +
                        trend_strength * 0.25 +
                        rsi_strength * 0.15
                    )
                    
                    if signal_strength > self.params['signal_strength_min']:
                        leverage = self.calculate_leverage(signal_strength)
                        
                        signals.iloc[i, signals.columns.get_loc('signal')] = 1
                        signals.iloc[i, signals.columns.get_loc('strength')] = signal_strength
                        signals.iloc[i, signals.columns.get_loc('leverage')] = leverage
                        
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
                        abs(indicators['momentum'].iloc[i]) / (self.params['momentum_threshold'] * 2.5), 1.0
                    )
                    volume_strength = min(
                        (indicators['volume_ratio'].iloc[i] - 1.0) / 1.5, 1.0
                    )
                    trend_strength = min(
                        indicators['trend_strength'].iloc[i] / 0.3, 1.0
                    )
                    rsi_strength = (50 - indicators['rsi'].iloc[i]) / 15  # Normalize RSI for shorts
                    rsi_strength = min(max(rsi_strength, 0), 1.0)
                    
                    signal_strength = (
                        momentum_strength * 0.35 +
                        volume_strength * 0.25 +
                        trend_strength * 0.25 +
                        rsi_strength * 0.15
                    )
                    
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
                # Manage open position (same as parent)
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
                
                # Check stop loss
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
