#!/usr/bin/env python3
"""Debug signal generation"""

import os
import glob
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from strategies.base_strategy import MeanReversionStrategy, MomentumStrategy, VolatilityArbitrageStrategy

# Load sample data
csv_files = glob.glob('data/*_1h.csv')
sample_file = csv_files[0]

df = pd.read_csv(sample_file, index_col=0, parse_dates=True)
symbol = os.path.basename(sample_file).replace('_1h.csv', '')

print(f"Testing {symbol}")
print(f"Data shape: {df.shape}")
print(f"Date range: {df.index[0]} to {df.index[-1]}")
print(f"Price range: {df['close'].min():.6f} - {df['close'].max():.6f}\n")

# Test Mean Reversion
print("=" * 60)
print("MEAN REVERSION STRATEGY")
print("=" * 60)

mr_strategy = MeanReversionStrategy(params={'lookback': 12})
mr_signals = mr_strategy.generate_signals(df)

print(f"Signals shape: {mr_signals.shape}")
print(f"Columns: {mr_signals.columns.tolist()}")
print(f"\nSignal value counts:")
if 'signal' in mr_signals.columns:
    print(mr_signals['signal'].value_counts())
    print(f"Total non-zero signals: {(mr_signals['signal'] != 0).sum()}")
    
print(f"\nFirst 10 signals:")
print(mr_signals[['signal', 'strength']].head(10) if 'strength' in mr_signals.columns else mr_signals[['signal']].head(10))

print(f"\nLast 10 signals:")
print(mr_signals[['signal', 'strength']].tail(10) if 'strength' in mr_signals.columns else mr_signals[['signal']].tail(10))

# Check returns and z-scores manually
print("\n" + "=" * 60)
print("MANUAL CALCULATION CHECK")
print("=" * 60)

returns = np.log(df['close'] / df['close'].shift(1))
mean = returns.rolling(window=12).mean()
std = returns.rolling(window=12).std()
zscore = (returns - mean) / std

print(f"Z-score stats: mean={zscore.mean():.4f}, std={zscore.std():.4f}")
print(f"Z-scores > 2.0: {(zscore > 2.0).sum()}")
print(f"Z-scores < -2.0: {(zscore < -2.0).sum()}")

print(f"\nZ-score distribution:")
print(f"  > 2.0: {(zscore > 2.0).sum()}")
print(f"  1.0-2.0: {((zscore > 1.0) & (zscore <= 2.0)).sum()}")
print(f"  0.5-1.0: {((zscore > 0.5) & (zscore <= 1.0)).sum()}")
print(f"  -0.5-0.5: {((zscore >= -0.5) & (zscore <= 0.5)).sum()}")
print(f"  -1.0--0.5: {((zscore < -0.5) & (zscore >= -1.0)).sum()}")
print(f"  -2.0--1.0: {((zscore < -1.0) & (zscore >= -2.0)).sum()}")
print(f"  < -2.0: {(zscore < -2.0).sum()}")

# Test Momentum
print("\n" + "=" * 60)
print("MOMENTUM STRATEGY")
print("=" * 60)

try:
    mom_strategy = MomentumStrategy(params={'fast_period': 6, 'slow_period': 24})
    mom_signals = mom_strategy.generate_signals(df)
    
    print(f"Signals shape: {mom_signals.shape}")
    if 'signal' in mom_signals.columns:
        print(f"Signal value counts:")
        print(mom_signals['signal'].value_counts())
        print(f"Total non-zero signals: {(mom_signals['signal'] != 0).sum()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test Volatility Arb
print("\n" + "=" * 60)
print("VOLATILITY ARBITRAGE STRATEGY")
print("=" * 60)

try:
    vol_strategy = VolatilityArbitrageStrategy(params={'vol_lookback': 48})
    vol_signals = vol_strategy.generate_signals(df)
    
    print(f"Signals shape: {vol_signals.shape}")
    if 'signal' in vol_signals.columns:
        print(f"Signal value counts:")
        print(vol_signals['signal'].value_counts())
        print(f"Total non-zero signals: {(vol_signals['signal'] != 0).sum()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
