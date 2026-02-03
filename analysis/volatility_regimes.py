"""
Volatility Regime Analysis for Memecoins
Identifies characteristic spikes, squeezes, and decay patterns
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

class VolatilityRegimeAnalyzer:
    """Analyzes volatility regimes in memecoin price action"""
    
    def __init__(self):
        self.regimes = {}
    
    def calculate_returns(self, df: pd.DataFrame) -> pd.Series:
        """Calculate log returns"""
        return np.log(df['close'] / df['close'].shift(1))
    
    def calculate_realized_volatility(self, df: pd.DataFrame, window: int = 24) -> pd.Series:
        """Calculate realized volatility (rolling std of returns)"""
        returns = self.calculate_returns(df)
        return returns.rolling(window=window).std() * np.sqrt(window) * 100  # Annualized %
    
    def identify_volatility_regimes(self, df: pd.DataFrame, 
                                   lookback: int = 168) -> pd.DataFrame:
        """
        Identify volatility regimes: low, normal, high, extreme
        
        Returns DataFrame with regime labels
        """
        returns = self.calculate_returns(df)
        vol = returns.rolling(window=24).std() * np.sqrt(24) * 100
        
        # Calculate percentiles over lookback period
        vol_p25 = vol.rolling(lookback).quantile(0.25)
        vol_p50 = vol.rolling(lookback).quantile(0.50)
        vol_p75 = vol.rolling(lookback).quantile(0.75)
        vol_p95 = vol.rolling(lookback).quantile(0.95)
        
        # Classify regimes
        regime = pd.Series(index=df.index, dtype=str)
        regime[vol < vol_p25] = 'low'
        regime[(vol >= vol_p25) & (vol < vol_p50)] = 'normal_low'
        regime[(vol >= vol_p50) & (vol < vol_p75)] = 'normal_high'
        regime[(vol >= vol_p75) & (vol < vol_p95)] = 'high'
        regime[vol >= vol_p95] = 'extreme'
        
        result = df.copy()
        result['volatility'] = vol
        result['regime'] = regime
        result['returns'] = returns
        
        return result
    
    def detect_volatility_spikes(self, df: pd.DataFrame, 
                                threshold_multiplier: float = 2.0) -> pd.DataFrame:
        """
        Detect sudden volatility spikes (potential squeeze setups)
        
        Returns DataFrame with spike flags
        """
        vol = self.calculate_realized_volatility(df, window=24)
        vol_ma = vol.rolling(window=168).mean()
        vol_std = vol.rolling(window=168).std()
        
        spike_threshold = vol_ma + (threshold_multiplier * vol_std)
        spikes = vol > spike_threshold
        
        result = df.copy()
        result['vol_spike'] = spikes
        result['vol_ratio'] = vol / vol_ma  # How many std above mean
        
        return result
    
    def analyze_decay_patterns(self, df: pd.DataFrame) -> Dict:
        """
        Analyze post-spike decay patterns
        Returns statistics on how volatility decays after spikes
        """
        result = self.detect_volatility_spikes(df)
        spikes = result[result['vol_spike']].index
        
        decay_stats = []
        
        for spike_time in spikes:
            # Look at next 24-72 hours
            post_spike = result.loc[spike_time:spike_time + pd.Timedelta(hours=72)]
            if len(post_spike) > 24:
                initial_vol = post_spike['volatility'].iloc[0]
                final_vol = post_spike['volatility'].iloc[-1]
                decay_rate = (initial_vol - final_vol) / initial_vol
                
                decay_stats.append({
                    'spike_time': spike_time,
                    'initial_vol': initial_vol,
                    'final_vol': final_vol,
                    'decay_rate': decay_rate,
                    'decay_hours': len(post_spike)
                })
        
        return pd.DataFrame(decay_stats) if decay_stats else pd.DataFrame()
    
    def calculate_correlations(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Calculate correlation matrix between memecoins"""
        returns_dict = {}
        
        for symbol, df in data_dict.items():
            returns = self.calculate_returns(df)
            returns_dict[symbol] = returns
        
        returns_df = pd.DataFrame(returns_dict)
        correlation_matrix = returns_df.corr()
        
        return correlation_matrix
    
    def analyze_liquidation_cascades(self, df: pd.DataFrame, 
                                    leverage: float = 20.0) -> pd.DataFrame:
        """
        Estimate liquidation pressure based on price moves
        
        Assumes average leverage of 20x, calculates potential liquidations
        """
        returns = self.calculate_returns(df)
        
        # Rough liquidation estimate: -5% move = 100% loss at 20x
        liquidation_threshold = -0.05 / leverage  # ~-0.25% for 20x
        
        # Identify sharp down moves
        sharp_downs = returns < liquidation_threshold
        
        result = df.copy()
        result['liquidation_risk'] = sharp_downs
        result['liquidation_pressure'] = np.where(
            returns < 0,
            abs(returns) * leverage * 100,  # Estimated liquidation %
            0
        )
        
        return result


def analyze_all_memecoins(data_dir: str = 'data') -> Dict:
    """Run volatility analysis on all memecoin data"""
    import os
    import glob
    
    analyzer = VolatilityRegimeAnalyzer()
    results = {}
    
    # Load all CSV files
    csv_files = glob.glob(os.path.join(data_dir, '*_1h.csv'))
    
    for filepath in csv_files:
        symbol = os.path.basename(filepath).replace('_1h.csv', '').replace('_', '/')
        print(f"Analyzing {symbol}...")
        
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            
            # Run analyses
            regime_df = analyzer.identify_volatility_regimes(df)
            spike_df = analyzer.detect_volatility_spikes(df)
            decay_df = analyzer.analyze_decay_patterns(df)
            liq_df = analyzer.analyze_liquidation_cascades(df)
            
            results[symbol] = {
                'regimes': regime_df,
                'spikes': spike_df,
                'decay': decay_df,
                'liquidation': liq_df,
                'stats': {
                    'mean_vol': analyzer.calculate_realized_volatility(df).mean(),
                    'max_vol': analyzer.calculate_realized_volatility(df).max(),
                    'spike_count': spike_df['vol_spike'].sum(),
                }
            }
            
        except Exception as e:
            print(f"  Error: {e}")
    
    return results


if __name__ == '__main__':
    print("Analyzing volatility regimes...")
    results = analyze_all_memecoins()
    
    print("\nVolatility Statistics:")
    print("=" * 60)
    for symbol, data in results.items():
        stats = data['stats']
        print(f"{symbol}:")
        print(f"  Mean Vol: {stats['mean_vol']:.2f}%")
        print(f"  Max Vol: {stats['max_vol']:.2f}%")
        print(f"  Spike Count: {stats['spike_count']}")
