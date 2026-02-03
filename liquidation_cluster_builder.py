#!/usr/bin/env python3
"""
Liquidation Cluster Builder
Builds liquidation clusters from history data (available in lower Coinglass tiers)
Much cheaper than Professional tier heatmap models!
"""

import pandas as pd
import numpy as np
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist
from liquidation_data_sources import LiquidationDataPoint

class LiquidationClusterBuilder:
    """
    Builds liquidation clusters from historical liquidation data
    Works with Coinglass liquidation history (available in $29-$299 tiers)
    or free exchange APIs
    """
    
    def __init__(self, cluster_window_pct: float = 0.02, 
                 min_cluster_size: int = 5,
                 time_decay_hours: int = 24):
        """
        Initialize cluster builder
        
        Args:
            cluster_window_pct: Price window for clustering (%)
            min_cluster_size: Minimum liquidations per cluster
            time_decay_hours: Hours for time decay weighting
        """
        self.cluster_window_pct = cluster_window_pct
        self.min_cluster_size = min_cluster_size
        self.time_decay_hours = time_decay_hours
    
    def build_clusters_from_history(self, 
                                   liquidations: List[LiquidationDataPoint],
                                   current_price: float,
                                   lookback_hours: int = 24) -> List[Dict]:
        """
        Build clusters from liquidation history data
        
        Args:
            liquidations: List of LiquidationDataPoint objects
            current_price: Current market price
            lookback_hours: Hours of history to use
            
        Returns:
            List of cluster dicts with price, side, strength, etc.
        """
        if not liquidations:
            return []
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'price': liq.price,
            'side': liq.side,
            'size': liq.size,
            'notional': liq.notional,
            'timestamp': liq.timestamp
        } for liq in liquidations])
        
        # Filter by time (recent liquidations weighted more)
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        df = df[df['timestamp'] >= cutoff_time].copy()
        
        if len(df) == 0:
            return []
        
        # Calculate time decay weights (recent = higher weight)
        now = datetime.now()
        df['age_hours'] = (now - df['timestamp']).dt.total_seconds() / 3600
        df['time_weight'] = np.exp(-df['age_hours'] / self.time_decay_hours)
        
        # Filter by distance from current price
        df['distance_pct'] = abs((df['price'] - current_price) / current_price) * 100
        max_distance = 10.0  # 10% max distance
        df = df[df['distance_pct'] <= max_distance].copy()
        
        if len(df) == 0:
            return []
        
        # Separate by side
        long_liq = df[df['side'] == 'long'].copy()
        short_liq = df[df['side'] == 'short'].copy()
        
        clusters = []
        
        # Build clusters for long liquidations
        if len(long_liq) > 0:
            long_clusters = self._cluster_by_price(
                long_liq, current_price, 'long'
            )
            clusters.extend(long_clusters)
        
        # Build clusters for short liquidations
        if len(short_liq) > 0:
            short_clusters = self._cluster_by_price(
                short_liq, current_price, 'short'
            )
            clusters.extend(short_clusters)
        
        # Sort by strength
        clusters.sort(key=lambda x: x['strength'], reverse=True)
        
        return clusters
    
    def _cluster_by_price(self, df: pd.DataFrame, current_price: float,
                         side: str) -> List[Dict]:
        """
        Cluster liquidations by price level
        
        Args:
            df: DataFrame with liquidation data
            current_price: Current market price
            side: 'long' or 'short'
            
        Returns:
            List of cluster dicts
        """
        if len(df) < self.min_cluster_size:
            return []
        
        # Use price percentage for clustering (normalized)
        prices = df['price'].values
        price_pcts = ((prices - current_price) / current_price) * 100
        
        # Cluster using hierarchical clustering
        distance_threshold = self.cluster_window_pct * 100  # Convert to percentage
        
        if len(prices) > 1:
            try:
                price_data = price_pcts.reshape(-1, 1)
                linkage_matrix = linkage(price_data, method='ward')
                cluster_labels = fcluster(linkage_matrix, distance_threshold, 
                                         criterion='distance')
            except:
                # Fallback: simple binning
                bins = np.arange(price_pcts.min(), 
                               price_pcts.max() + distance_threshold, 
                               distance_threshold)
                cluster_labels = np.digitize(price_pcts, bins)
        else:
            cluster_labels = [1]
        
        # Aggregate clusters
        cluster_dict = defaultdict(lambda: {
            'prices': [],
            'sizes': [],
            'notionals': [],
            'time_weights': []
        })
        
        for i, label in enumerate(cluster_labels):
            cluster_dict[label]['prices'].append(prices[i])
            cluster_dict[label]['sizes'].append(df.iloc[i]['size'])
            cluster_dict[label]['notionals'].append(df.iloc[i]['notional'])
            cluster_dict[label]['time_weights'].append(df.iloc[i]['time_weight'])
        
        clusters = []
        
        # Calculate cluster metrics
        all_counts = [len(c['prices']) for c in cluster_dict.values()]
        all_notionals = [sum(c['notionals']) for c in cluster_dict.values()]
        max_count = max(all_counts) if all_counts else 1
        max_notional = max(all_notionals) if all_notionals else 1
        
        for cluster_id, data in cluster_dict.items():
            if len(data['prices']) < self.min_cluster_size:
                continue
            
            prices_in_cluster = np.array(data['prices'])
            sizes_in_cluster = np.array(data['sizes'])
            notionals_in_cluster = np.array(data['notionals'])
            time_weights = np.array(data['time_weights'])
            
            # Weighted average price (by notional and time)
            weights = notionals_in_cluster * time_weights
            if weights.sum() > 0:
                weighted_price = np.average(prices_in_cluster, weights=weights)
            else:
                weighted_price = np.mean(prices_in_cluster)
            
            # Total notional (time-weighted)
            total_notional = (notionals_in_cluster * time_weights).sum()
            
            # Cluster strength (0-1)
            count_strength = len(prices_in_cluster) / max_count if max_count > 0 else 0
            notional_strength = total_notional / max_notional if max_notional > 0 else 0
            strength = (count_strength * 0.4 + notional_strength * 0.6)  # Weight notional more
            
            # Distance from current price
            distance_pct = abs((weighted_price - current_price) / current_price) * 100
            
            cluster = {
                'price_level': weighted_price,
                'liquidation_count': len(prices_in_cluster),
                'total_notional': total_notional,
                'side': side,
                'strength': strength,
                'distance_from_price': distance_pct,
                'cluster_id': cluster_id,
                'avg_size': np.mean(sizes_in_cluster),
                'max_size': np.max(sizes_in_cluster)
            }
            
            clusters.append(cluster)
        
        return clusters


class AffordableCoinglassFetcher:
    """
    Fetches liquidation history from Coinglass (available in lower tiers)
    Then builds clusters from the history data
    """
    
    BASE_URL = "https://open-api.coinglass.com"
    
    def __init__(self, api_key: str):
        """
        Initialize affordable Coinglass fetcher
        
        Args:
            api_key: Coinglass API key (Hobbyist $29/mo or Startup $79/mo)
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'coinglassSecret': api_key,
            'Content-Type': 'application/json'
        })
        self.cluster_builder = LiquidationClusterBuilder()
    
    def fetch_liquidation_history(self, symbol: str, exchange: str = 'binance',
                                 hours: int = 24) -> List[LiquidationDataPoint]:
        """
        Fetch liquidation history (available in lower tiers)
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            exchange: Exchange name
            hours: Hours of history
            
        Returns:
            List of LiquidationDataPoint objects
        """
        import requests
        
        try:
            url = f"{self.BASE_URL}/api/futures/liquidation/history"
            
            params = {
                'symbol': symbol,
                'exchange': exchange,
                'timeType': '1',  # 1h intervals
                'limit': min(hours, 168)  # Max 7 days
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            liquidations = []
            
            if 'data' in data and isinstance(data['data'], list):
                for item in data['data']:
                    price = item.get('price', 0)
                    side_str = item.get('side', '').lower()
                    
                    # Determine side
                    if 'buy' in side_str or 'long' in side_str:
                        side = 'long'
                    else:
                        side = 'short'
                    
                    size = item.get('size', 0) or item.get('qty', 0) or item.get('amount', 0)
                    timestamp_ms = item.get('time', 0) or item.get('timestamp', 0)
                    
                    if price > 0 and size > 0:
                        timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                        
                        liquidations.append(LiquidationDataPoint(
                            price=price,
                            side=side,
                            size=size,
                            notional=size * price,
                            timestamp=timestamp,
                            exchange=exchange
                        ))
            
            return liquidations
            
        except Exception as e:
            print(f"Error fetching Coinglass history: {e}")
            return []
    
    def get_clusters(self, symbol: str, current_price: float,
                    exchange: str = 'binance', hours: int = 24) -> List[Dict]:
        """
        Get liquidation clusters built from history data
        
        Args:
            symbol: Trading pair
            current_price: Current market price
            exchange: Exchange name
            hours: Hours of history to analyze
            
        Returns:
            List of cluster dicts (same format as heatmap models)
        """
        # Fetch history (available in lower tiers)
        liquidations = self.fetch_liquidation_history(symbol, exchange, hours)
        
        if not liquidations:
            return []
        
        # Build clusters from history
        clusters = self.cluster_builder.build_clusters_from_history(
            liquidations, current_price, hours
        )
        
        return clusters


# Example usage
if __name__ == '__main__':
    print("=" * 70)
    print("AFFORDABLE LIQUIDATION CLUSTER SOLUTION")
    print("=" * 70)
    print("\nInstead of Professional tier ($879/mo) heatmap models,")
    print("we can use lower tier liquidation history + build clusters!")
    print("\nAvailable Plans:")
    print("  • Hobbyist: $29/mo - Liquidation History ✅")
    print("  • Startup: $79/mo - Liquidation History ✅")
    print("  • Standard: $299/mo - Liquidation History ✅")
    print("  • Professional: $879/mo - Heatmap Models (not needed!)")
    print("\n" + "=" * 70)
