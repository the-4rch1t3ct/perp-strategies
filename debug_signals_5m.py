#!/usr/bin/env python3
"""Debug signal generation to see why no signals are being created"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from data.fetch_data import MemecoinDataFetcher
from strategies.high_frequency_momentum import HighFrequencyMomentumStrategy

fetcher = MemecoinDataFetcher()
df = fetcher.load_data('DOGE/USDT:USDT', timeframe='5m')

if df.empty:
    print("No data!")
    exit(1)

print(f"Data: {len(df)} candles")
print(f"Date range: {df.index[0]} to {df.index[-1]}")

strategy = HighFrequencyMomentumStrategy(timeframe='5m')
indicators = strategy.calculate_indicators(df)

# Check each filter condition
print("\nChecking filter conditions...")

# Long entry conditions
long_entry_base = (
    (indicators['ema_fast'] > indicators['ema_slow']) &
    (indicators['momentum'] > strategy.params['momentum_threshold']) &
    (indicators['trend_strength'] > strategy.params['trend_strength_threshold']) &
    (indicators['volume_ratio'] > strategy.params['volume_multiplier']) &
    (indicators['volume_percentile'] > strategy.params['min_volume_percentile']) &
    (indicators['rsi'] > strategy.params['rsi_neutral_low']) &
    (indicators['rsi'] < strategy.params['rsi_overbought']) &
    (indicators['macd_hist'] > 0) &
    (indicators['price_position'] > 0.3)
)

print(f"\nLong entry conditions:")
print(f"  EMA fast > slow: {(indicators['ema_fast'] > indicators['ema_slow']).sum()}")
print(f"  Momentum > threshold: {(indicators['momentum'] > strategy.params['momentum_threshold']).sum()}")
print(f"  Trend strength > threshold: {(indicators['trend_strength'] > strategy.params['trend_strength_threshold']).sum()}")
print(f"  Volume ratio > multiplier: {(indicators['volume_ratio'] > strategy.params['volume_multiplier']).sum()}")
print(f"  Volume percentile > min: {(indicators['volume_percentile'] > strategy.params['min_volume_percentile']).sum()}")
print(f"  RSI in range: {((indicators['rsi'] > strategy.params['rsi_neutral_low']) & (indicators['rsi'] < strategy.params['rsi_overbought'])).sum()}")
print(f"  MACD hist > 0: {(indicators['macd_hist'] > 0).sum()}")
print(f"  Price position > 0.3: {(indicators['price_position'] > 0.3).sum()}")
print(f"  ALL CONDITIONS: {long_entry_base.sum()}")

# Check individual filter stats
print(f"\nFilter statistics:")
print(f"  Trend strength - min: {indicators['trend_strength'].min():.4f}, max: {indicators['trend_strength'].max():.4f}, mean: {indicators['trend_strength'].mean():.4f}")
print(f"  Volume ratio - min: {indicators['volume_ratio'].min():.2f}, max: {indicators['volume_ratio'].max():.2f}, mean: {indicators['volume_ratio'].mean():.2f}")
print(f"  Momentum - min: {indicators['momentum'].min():.4f}, max: {indicators['momentum'].max():.4f}, mean: {indicators['momentum'].mean():.4f}")

# Check if any single condition is too restrictive
print(f"\nChecking which filters are most restrictive:")
conditions = {
    'EMA crossover': (indicators['ema_fast'] > indicators['ema_slow']).sum(),
    'Momentum': (indicators['momentum'] > strategy.params['momentum_threshold']).sum(),
    'Trend strength': (indicators['trend_strength'] > strategy.params['trend_strength_threshold']).sum(),
    'Volume ratio': (indicators['volume_ratio'] > strategy.params['volume_multiplier']).sum(),
    'Volume percentile': (indicators['volume_percentile'] > strategy.params['min_volume_percentile']).sum(),
    'RSI range': ((indicators['rsi'] > strategy.params['rsi_neutral_low']) & (indicators['rsi'] < strategy.params['rsi_overbought'])).sum(),
    'MACD': (indicators['macd_hist'] > 0).sum(),
    'Price position': (indicators['price_position'] > 0.3).sum(),
}

for name, count in sorted(conditions.items(), key=lambda x: x[1]):
    print(f"  {name}: {count} ({count/len(df)*100:.1f}%)")
