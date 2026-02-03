"""
High-Frequency Momentum Strategy
Optimized for 5m/15m timeframes with high trade volume
Focus: Increase win rate, reduce drawdowns, maximize returns
"""

import pandas as pd
import numpy as np
from typing import Dict
from .base_strategy import BaseStrategy

class HighFrequencyMomentumStrategy(BaseStrategy):
    """
    High-Frequency Momentum Strategy
    Optimized for lower timeframes (5m/15m) with:
    - Volume confirmation
    - Tighter stops (ATR-based)
    - Trailing stops
    - Multiple confirmation filters
    - Quick profit taking
    """
    
    def __init__(self, params: Dict = None, timeframe: str = '5m'):
        """
        Initialize strategy
        
        Args:
            params: Strategy parameters
            timeframe: '5m' or '15m' - adjusts periods accordingly
        """
        # Scale parameters based on timeframe
        if timeframe == '5m':
            # 5m: fast=12 periods (1h), slow=36 periods (3h)
            fast_period = 12
            slow_period = 36
            atr_period = 14
            rsi_period = 14
            min_hold_periods = 6  # 30 minutes
            max_hold_periods = 72  # 6 hours
        elif timeframe == '15m':
            # 15m: fast=8 periods (2h), slow=24 periods (6h)
            fast_period = 8
            slow_period = 24
            atr_period = 14
            rsi_period = 14
            min_hold_periods = 4  # 1 hour
            max_hold_periods = 48  # 12 hours
        else:  # Default to 1h equivalent
            fast_period = 6
            slow_period = 18
            atr_period = 14
            rsi_period = 14
            min_hold_periods = 2
            max_hold_periods = 24
        
        default_params = {
            'fast_period': fast_period,
            'slow_period': slow_period,
            'atr_period': atr_period,
            'rsi_period': rsi_period,
            'momentum_threshold': 0.005,  # 0.5% for lower timeframes
            'rsi_oversold': 35,  # Tighter range
            'rsi_overbought': 65,
            'rsi_neutral_low': 45,
            'rsi_neutral_high': 55,
            'min_hold_periods': min_hold_periods,
            'max_hold_periods': max_hold_periods,
            'volume_multiplier': 1.1,  # Volume must be 10% above average (lowered for more signals)
            'atr_stop_multiplier': 1.5,  # Stop loss at 1.5x ATR
            'atr_take_profit': 2.5,  # Take profit at 2.5x ATR (1.67:1 R:R)
            'trailing_stop_activation': 1.0,  # Activate trailing after 1x ATR profit
            'trailing_stop_distance': 0.8,  # Trail at 0.8x ATR
            'trend_strength_threshold': 0.001,  # Minimum trend strength (0.1% for lower timeframes)
            'min_volume_percentile': 20,  # Minimum volume percentile (lowered for more signals)
        }
        default_params.update(params or {})
        super().__init__('HighFrequencyMomentum', default_params)
        self.timeframe = timeframe
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate enhanced momentum indicators"""
        result = data.copy()
        
        # Moving averages
        result['ema_fast'] = data['close'].ewm(span=self.params['fast_period']).mean()
        result['ema_slow'] = data['close'].ewm(span=self.params['slow_period']).mean()
        
        # EMA trend strength (how far apart are the EMAs)
        ema_diff = (result['ema_fast'] - result['ema_slow']) / result['ema_slow']
        result['trend_strength'] = abs(ema_diff)
        
        # RSI with neutral zone
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.params['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params['rsi_period']).mean()
        rs = gain / loss
        result['rsi'] = 100 - (100 / (1 + rs))
        
        # Momentum (rate of change)
        result['momentum'] = data['close'].pct_change(periods=self.params['fast_period'])
        
        # ATR for dynamic stops
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        result['atr'] = tr.rolling(window=self.params['atr_period']).mean()
        result['atr_pct'] = result['atr'] / data['close'] * 100
        
        # Volume analysis
        result['volume_ma'] = data['volume'].rolling(window=self.params['slow_period']).mean()
        result['volume_ratio'] = data['volume'] / result['volume_ma']
        result['volume_percentile'] = data['volume'].rolling(window=100).rank(pct=True) * 100
        
        # MACD for additional confirmation
        ema12 = data['close'].ewm(span=12).mean()
        ema26 = data['close'].ewm(span=26).mean()
        result['macd'] = ema12 - ema26
        result['macd_signal'] = result['macd'].ewm(span=9).mean()
        result['macd_hist'] = result['macd'] - result['macd_signal']
        
        # Price position relative to recent range
        result['high_20'] = data['high'].rolling(window=20).max()
        result['low_20'] = data['low'].rolling(window=20).min()
        result['price_position'] = (data['close'] - result['low_20']) / (result['high_20'] - result['low_20'])
        
        return result
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate high-frequency momentum signals with enhanced filters"""
        indicators = self.calculate_indicators(data)
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals['strength'] = 0.0
        signals['stop_loss'] = np.nan
        signals['take_profit'] = np.nan
        
        # Enhanced entry conditions with multiple filters (relaxed for 5m timeframe)
        # Core requirements (must have)
        long_entry_core = (
            (indicators['ema_fast'] > indicators['ema_slow']) &
            (indicators['momentum'] > self.params['momentum_threshold']) &
            (indicators['rsi'] > self.params['rsi_neutral_low']) &
            (indicators['rsi'] < self.params['rsi_overbought'])
        )
        
        # Additional filters (at least 2 of 4 must pass)
        long_entry_filters = (
            (indicators['trend_strength'] > self.params['trend_strength_threshold']).astype(int) +
            (indicators['volume_ratio'] > self.params['volume_multiplier']).astype(int) +
            (indicators['macd_hist'] > 0).astype(int) +
            (indicators['price_position'] > 0.3).astype(int)
        ) >= 2
        
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
        ) >= 2
        
        short_entry_base = short_entry_core & short_entry_filters & (indicators['volume_percentile'] > self.params['min_volume_percentile'])
        
        # Position tracking
        position = 0  # 0=flat, 1=long, -1=short
        entry_time = None
        entry_price = None
        entry_atr = None
        highest_price = None
        lowest_price = None
        
        for i in range(len(signals)):
            current_price = data['close'].iloc[i]
            current_atr = indicators['atr'].iloc[i]
            current_atr_pct = indicators['atr_pct'].iloc[i]
            
            if position == 0:
                # Look for entry
                if long_entry_base.iloc[i]:
                    # Calculate signal strength (0-1)
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
                    
                    if signal_strength > 0.2:  # Minimum strength threshold (lowered for more signals)
                        signals.iloc[i, signals.columns.get_loc('signal')] = 1
                        signals.iloc[i, signals.columns.get_loc('strength')] = signal_strength
                        
                        # Set stop loss and take profit
                        stop_loss_price = current_price - (current_atr * self.params['atr_stop_multiplier'])
                        take_profit_price = current_price + (current_atr * self.params['atr_take_profit'])
                        
                        signals.iloc[i, signals.columns.get_loc('stop_loss')] = stop_loss_price
                        signals.iloc[i, signals.columns.get_loc('take_profit')] = take_profit_price
                        
                        position = 1
                        entry_time = signals.index[i]
                        entry_price = current_price
                        entry_atr = current_atr
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
                    
                    if signal_strength > 0.2:  # Minimum strength threshold (lowered for more signals)
                        signals.iloc[i, signals.columns.get_loc('signal')] = -1
                        signals.iloc[i, signals.columns.get_loc('strength')] = signal_strength
                        
                        stop_loss_price = current_price + (current_atr * self.params['atr_stop_multiplier'])
                        take_profit_price = current_price - (current_atr * self.params['atr_take_profit'])
                        
                        signals.iloc[i, signals.columns.get_loc('stop_loss')] = stop_loss_price
                        signals.iloc[i, signals.columns.get_loc('take_profit')] = take_profit_price
                        
                        position = -1
                        entry_time = signals.index[i]
                        entry_price = current_price
                        entry_atr = current_atr
                        lowest_price = current_price
            
            else:
                # Manage open position
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
                        highest_price = None
                elif position == -1:
                    if current_price >= entry_price + (entry_atr * self.params['atr_stop_multiplier']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        lowest_price = None
                
                # Check take profit
                elif position == 1:
                    if current_price >= entry_price + (entry_atr * self.params['atr_take_profit']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        highest_price = None
                
                elif position == -1:
                    if current_price <= entry_price - (entry_atr * self.params['atr_take_profit']):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        lowest_price = None
                
                # Trailing stop (after profit threshold)
                elif profit_atr >= self.params['trailing_stop_activation']:
                    if position == 1:
                        trailing_stop = highest_price - (entry_atr * self.params['trailing_stop_distance'])
                        if current_price <= trailing_stop:
                            signals.iloc[i, signals.columns.get_loc('signal')] = 0
                            position = 0
                            entry_time = None
                            entry_price = None
                            entry_atr = None
                            highest_price = None
                    elif position == -1:
                        trailing_stop = lowest_price + (entry_atr * self.params['trailing_stop_distance'])
                        if current_price >= trailing_stop:
                            signals.iloc[i, signals.columns.get_loc('signal')] = 0
                            position = 0
                            entry_time = None
                            entry_price = None
                            entry_atr = None
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
                        highest_price = None
                
                elif position == -1:
                    if (indicators['ema_fast'].iloc[i] > indicators['ema_slow'].iloc[i] or
                        indicators['macd_hist'].iloc[i] > 0):
                        signals.iloc[i, signals.columns.get_loc('signal')] = 0
                        position = 0
                        entry_time = None
                        entry_price = None
                        entry_atr = None
                        lowest_price = None
                
                # Force exit on max hold time
                elif periods_held >= self.params['max_hold_periods']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
                    entry_price = None
                    entry_atr = None
                    highest_price = None
                    lowest_price = None
        
        return signals
