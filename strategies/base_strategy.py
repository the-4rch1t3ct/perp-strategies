"""
Base Strategy Class for Memecoin Perpetual Futures
All strategies inherit from this base class
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Optional

class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, params: Dict = None):
        self.name = name
        self.params = params or {}
        self.signals = None
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals
        
        Returns:
            DataFrame with columns: 'signal' (1=long, -1=short, 0=flat), 
            'strength' (0-1), 'entry_time', 'exit_time'
        """
        pass
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators (override in subclasses)"""
        return data.copy()


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy
    Enters when price deviates significantly from mean, exits on reversion
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'lookback': 24,  # Hours
            'entry_threshold': 2.0,  # Standard deviations
            'exit_threshold': 0.5,  # Standard deviations
            'min_hold_hours': 4,
            'max_hold_hours': 48
        }
        default_params.update(params or {})
        super().__init__('MeanReversion', default_params)
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate mean reversion signals"""
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals['strength'] = 0.0
        
        # Calculate z-score
        returns = np.log(data['close'] / data['close'].shift(1))
        mean = returns.rolling(window=self.params['lookback']).mean()
        std = returns.rolling(window=self.params['lookback']).std()
        zscore = (returns - mean) / std
        
        # Entry signals
        long_entry = zscore < -self.params['entry_threshold']
        short_entry = zscore > self.params['entry_threshold']
        
        # Position tracking
        position = 0  # 0=flat, 1=long, -1=short
        entry_time = None
        
        for i in range(len(signals)):
            if position == 0:
                # Look for entry
                if long_entry.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 1
                    signals.iloc[i, signals.columns.get_loc('strength')] = min(
                        abs(zscore.iloc[i]) / self.params['entry_threshold'], 1.0
                    )
                    position = 1
                    entry_time = signals.index[i]
                
                elif short_entry.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc('signal')] = -1
                    signals.iloc[i, signals.columns.get_loc('strength')] = min(
                        abs(zscore.iloc[i]) / self.params['entry_threshold'], 1.0
                    )
                    position = -1
                    entry_time = signals.index[i]
            
            else:
                # Check exit conditions
                hours_held = (signals.index[i] - entry_time).total_seconds() / 3600
                
                # Exit on reversion
                if position == 1 and zscore.iloc[i] > -self.params['exit_threshold']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
                
                elif position == -1 and zscore.iloc[i] < self.params['exit_threshold']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
                
                # Force exit on max hold time
                elif hours_held >= self.params['max_hold_hours']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
        
        return signals


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy
    Enters on strong momentum, exits on momentum exhaustion
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'fast_period': 12,  # Hours
            'slow_period': 48,  # Hours
            'momentum_threshold': 0.02,  # 2% move
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'min_hold_hours': 2,
            'max_hold_hours': 72
        }
        default_params.update(params or {})
        super().__init__('Momentum', default_params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum indicators"""
        result = data.copy()
        
        # Moving averages
        result['ema_fast'] = data['close'].ewm(span=self.params['fast_period']).mean()
        result['ema_slow'] = data['close'].ewm(span=self.params['slow_period']).mean()
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.params['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params['rsi_period']).mean()
        rs = gain / loss
        result['rsi'] = 100 - (100 / (1 + rs))
        
        # Momentum (rate of change)
        result['momentum'] = data['close'].pct_change(periods=self.params['fast_period'])
        
        return result
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate momentum signals"""
        indicators = self.calculate_indicators(data)
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals['strength'] = 0.0
        
        # Entry conditions
        long_entry = (
            (indicators['ema_fast'] > indicators['ema_slow']) &
            (indicators['momentum'] > self.params['momentum_threshold']) &
            (indicators['rsi'] < self.params['rsi_overbought'])
        )
        
        short_entry = (
            (indicators['ema_fast'] < indicators['ema_slow']) &
            (indicators['momentum'] < -self.params['momentum_threshold']) &
            (indicators['rsi'] > self.params['rsi_oversold'])
        )
        
        # Exit conditions
        long_exit = (
            (indicators['ema_fast'] < indicators['ema_slow']) |
            (indicators['rsi'] > self.params['rsi_overbought'])
        )
        
        short_exit = (
            (indicators['ema_fast'] > indicators['ema_slow']) |
            (indicators['rsi'] < self.params['rsi_oversold'])
        )
        
        position = 0
        entry_time = None
        
        for i in range(len(signals)):
            if position == 0:
                if long_entry.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 1
                    signals.iloc[i, signals.columns.get_loc('strength')] = min(
                        abs(indicators['momentum'].iloc[i]) / (self.params['momentum_threshold'] * 2), 1.0
                    )
                    position = 1
                    entry_time = signals.index[i]
                
                elif short_entry.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc('signal')] = -1
                    signals.iloc[i, signals.columns.get_loc('strength')] = min(
                        abs(indicators['momentum'].iloc[i]) / (self.params['momentum_threshold'] * 2), 1.0
                    )
                    position = -1
                    entry_time = signals.index[i]
            
            else:
                hours_held = (signals.index[i] - entry_time).total_seconds() / 3600
                
                if position == 1 and (long_exit.iloc[i] or hours_held >= self.params['max_hold_hours']):
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
                
                elif position == -1 and (short_exit.iloc[i] or hours_held >= self.params['max_hold_hours']):
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
        
        return signals


class VolatilityArbitrageStrategy(BaseStrategy):
    """
    Volatility Arbitrage Strategy
    Enters when volatility is mispriced relative to historical norms
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'vol_lookback': 168,  # Hours (1 week)
            'vol_spike_threshold': 2.0,  # Standard deviations
            'vol_mean_reversion_threshold': 0.5,
            'min_hold_hours': 6,
            'max_hold_hours': 96
        }
        default_params.update(params or {})
        super().__init__('VolatilityArbitrage', default_params)
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate volatility arbitrage signals"""
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals['strength'] = 0.0
        
        # Calculate realized volatility
        returns = np.log(data['close'] / data['close'].shift(1))
        vol = returns.rolling(window=24).std() * np.sqrt(24) * 100
        
        # Volatility z-score
        vol_mean = vol.rolling(window=self.params['vol_lookback']).mean()
        vol_std = vol.rolling(window=self.params['vol_lookback']).std()
        vol_zscore = (vol - vol_mean) / vol_std
        
        # Entry: Short volatility when extremely high (expecting mean reversion)
        # Long volatility when extremely low (expecting spike)
        short_vol_entry = vol_zscore > self.params['vol_spike_threshold']
        long_vol_entry = vol_zscore < -self.params['vol_spike_threshold']
        
        # For simplicity, we'll trade the underlying based on vol regime
        # In practice, this would trade volatility derivatives
        
        position = 0
        entry_time = None
        
        for i in range(len(signals)):
            if position == 0:
                # When vol spikes, expect mean reversion (short)
                if short_vol_entry.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc('signal')] = -1
                    signals.iloc[i, signals.columns.get_loc('strength')] = min(
                        abs(vol_zscore.iloc[i]) / (self.params['vol_spike_threshold'] * 2), 1.0
                    )
                    position = -1
                    entry_time = signals.index[i]
                
                # When vol is extremely low, expect spike (long)
                elif long_vol_entry.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 1
                    signals.iloc[i, signals.columns.get_loc('strength')] = min(
                        abs(vol_zscore.iloc[i]) / (self.params['vol_spike_threshold'] * 2), 1.0
                    )
                    position = 1
                    entry_time = signals.index[i]
            
            else:
                hours_held = (signals.index[i] - entry_time).total_seconds() / 3600
                
                # Exit when vol returns to normal
                if abs(vol_zscore.iloc[i]) < self.params['vol_mean_reversion_threshold']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
                
                elif hours_held >= self.params['max_hold_hours']:
                    signals.iloc[i, signals.columns.get_loc('signal')] = 0
                    position = 0
                    entry_time = None
        
        return signals
