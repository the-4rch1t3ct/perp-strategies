"""
Lightweight numpy-based statistics to replace scipy dependency
Used for z-score, correlations, and other calculations
"""
import numpy as np
import pandas as pd
from typing import Tuple

def zscore(data: np.ndarray | pd.Series, ddof: int = 1) -> np.ndarray | pd.Series:
    """Calculate z-scores (standardized values)"""
    if isinstance(data, pd.Series):
        mean = data.mean()
        std = data.std(ddof=ddof)
        return (data - mean) / std
    else:
        mean = np.mean(data)
        std = np.std(data, ddof=ddof)
        return (data - mean) / std

def pearsonr(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculate Pearson correlation coefficient"""
    x = np.asarray(x).flatten()
    y = np.asarray(y).flatten()
    
    # Remove NaN values
    mask = ~(np.isnan(x) | np.isnan(y))
    x = x[mask]
    y = y[mask]
    
    if len(x) < 2:
        return np.nan, np.nan
    
    mean_x = np.mean(x)
    mean_y = np.mean(y)
    
    numerator = np.sum((x - mean_x) * (y - mean_y))
    denominator = np.sqrt(np.sum((x - mean_x)**2) * np.sum((y - mean_y)**2))
    
    if denominator == 0:
        return np.nan, np.nan
    
    r = numerator / denominator
    
    # Calculate p-value using t-distribution approximation
    n = len(x)
    t_stat = r * np.sqrt(n - 2) / np.sqrt(1 - r**2) if abs(r) < 1 else np.inf
    
    return r, np.nan  # p-value calculation omitted for simplicity

def spearmanr(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculate Spearman correlation coefficient"""
    x = np.asarray(x).flatten()
    y = np.asarray(y).flatten()
    
    # Handle NaN
    mask = ~(np.isnan(x) | np.isnan(y))
    x = x[mask]
    y = y[mask]
    
    # Rank values
    x_ranked = np.argsort(np.argsort(x))
    y_ranked = np.argsort(np.argsort(y))
    
    # Use Pearson on ranked data
    return pearsonr(x_ranked, y_ranked)

def norm_ppf(q: float) -> float:
    """Approximate inverse normal CDF (quantile function)"""
    # Polynomial approximation of inverse normal CDF
    a = [
        2.506628277459,
        3.224671290700,
        2.445134137142,
        0.254693230882,
    ]
    b = [
        1.423326310743,
        1.221482515665,
        3.020799498728e-1,
        2.908193052294e-4,
    ]
    
    if q < 0.5:
        t = np.sqrt(-2.0 * np.log(q))
    else:
        t = np.sqrt(-2.0 * np.log(1.0 - q))
    
    if q < 0.5:
        return -(((((a[3]*t + a[2])*t + a[1])*t + a[0]) /
                   (((b[3]*t + b[2])*t + b[1])*t + b[0])*t))
    else:
        return (((((a[3]*t + a[2])*t + a[1])*t + a[0]) /
                 (((b[3]*t + b[2])*t + b[1])*t + b[0])*t))

# Create mock scipy.stats module for import compatibility
class MockStats:
    @staticmethod
    def zscore(data, ddof=1):
        return zscore(data, ddof)
    
    @staticmethod
    def pearsonr(x, y):
        return pearsonr(x, y)
    
    @staticmethod
    def spearmanr(x, y):
        return spearmanr(x, y)
    
    @staticmethod
    def norm(loc=0, scale=1):
        class Norm:
            def ppf(self, q):
                return loc + scale * norm_ppf(q)
        return Norm()

# Make available as scipy.stats alternative
stats = MockStats()
