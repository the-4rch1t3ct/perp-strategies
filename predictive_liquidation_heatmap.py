#!/usr/bin/env python3
"""
Predictive Liquidation Heatmap
Calculates potential liquidation levels based on Open Interest and leverage tiers
Shows risk zones BEFORE liquidations occur (like Coinglass)
"""

import json
import math
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import httpx
import numpy as np
from dataclasses import dataclass, asdict
from scipy.cluster.hierarchy import linkage, fcluster

try:
    import websocket
except ImportError:
    websocket = None

# Strength (confidence): sqrt scale so values spread. Factor 3: 33% OI -> 1.0, 20% -> 0.77, 12% -> 0.6.
# Dominant tier often ~15-45%, so we get conf in 0.6-1.0 range and differentiate symbols.
def _strength_from_oi_fraction(oi_per_tier: float, total_oi: float) -> float:
    if not total_oi or total_oi <= 0:
        return 0.0
    frac = oi_per_tier / total_oi
    return min(1.0, math.sqrt(frac * 3.0))

@dataclass
class LiquidationLevel:
    """Predicted liquidation level"""
    price_level: float
    side: str  # 'long' or 'short'
    leverage_tier: float  # e.g., 100, 50, 25
    open_interest: float  # USD value of OI at this level
    liquidation_count: int  # Estimated number of positions
    strength: float  # 0-1, normalized intensity
    distance_from_price: float  # % from current price
    cluster_id: int
    last_updated: datetime

@dataclass
class PositionData:
    """Position data from exchange"""
    symbol: str
    price: float
    side: str  # 'long' or 'short'
    leverage: float
    notional: float  # USD value
    liquidation_price: float

class PredictiveLiquidationHeatmap:
    """
    Predictive liquidation heatmap based on Open Interest and leverage calculations
    """
    
    def __init__(self,
                 leverage_tiers: List[float] = None,
                 price_bucket_pct: float = 0.005,  # 0.5% buckets (increased to reduce noise)
                 min_oi_threshold: float = 25000,  # Absolute OI floor (USD) to show
                 min_oi_threshold_pct: float = 0.02,  # Relative OI floor (% of total OI)
                 min_cluster_distance_pct: float = 0.3,  # Minimum distance between clusters (%)
                 update_interval: float = 5.0):
        """
        Initialize predictive heatmap
        
        Args:
            leverage_tiers: List of leverage levels to calculate (e.g., [100, 50, 25, 10])
            price_bucket_pct: Price bucket size for clustering (%)
            min_oi_threshold: Minimum Open Interest to display (USD)
            min_oi_threshold_pct: Minimum OI per tier as % of total OI
            update_interval: Seconds between updates
        """
        self.leverage_tiers = leverage_tiers or [100, 50, 25, 10, 5]
        self.price_bucket_pct = price_bucket_pct
        self.min_oi_threshold = min_oi_threshold
        self.min_oi_threshold_pct = min_oi_threshold_pct
        self.min_cluster_distance_pct = min_cluster_distance_pct
        self.update_interval = update_interval
        
        # Data storage
        self.current_prices: Dict[str, float] = {}
        self.open_interest_data: Dict[str, Dict] = {}  # symbol -> {long_oi, short_oi, long_short_ratio}
        self.liquidation_levels: Dict[str, List[LiquidationLevel]] = {}
        self.last_update: Dict[str, datetime] = {}
        
        # WebSocket for price updates
        self.price_ws = None
        self.running = False
        
    def start(self, symbols: List[str] = None):
        """Start real-time price updates"""
        if symbols is None:
            symbols = []
        
        self.symbols = symbols
        self.running = True
        
        # Start background tasks
        threading.Thread(target=self._update_prices_loop, daemon=True).start()
        threading.Thread(target=self._update_oi_loop, daemon=True).start()
        threading.Thread(target=self._calculate_levels_loop, daemon=True).start()
        
        print(f"✅ Predictive heatmap started for {len(symbols)} symbols")
    
    def stop(self):
        """Stop the heatmap"""
        self.running = False
        if self.price_ws:
            self.price_ws.close()
    
    def _update_prices_loop(self):
        """Background loop to update current prices. Binance: 1 req (all symbols)."""
        while self.running:
            try:
                self._fetch_current_prices()
                time.sleep(5)  # 5s: ~12 req/min, well under Binance 1200/min
            except Exception as e:
                print(f"Error updating prices: {e}")
                time.sleep(30)
    
    def _update_oi_loop(self):
        """Background loop: OI + depth per symbol. Binance: 2 req/symbol, 10 symbols = 20 req/cycle."""
        while self.running:
            try:
                for symbol in self.symbols:
                    self._fetch_open_interest(symbol)
                    time.sleep(0.25)  # 0.25s between symbols to avoid burst (20 req in ~5s)
                time.sleep(15)  # 15s cycle: ~80 req/min, under 1200/min
            except Exception as e:
                print(f"Error updating OI: {e}")
                time.sleep(60)
    
    def _calculate_levels_loop(self):
        """Background loop to calculate liquidation levels (uses cached prices/OI, no API calls)."""
        while self.running:
            try:
                for symbol in self.symbols:
                    if symbol in self.current_prices and symbol in self.open_interest_data:
                        self._calculate_liquidation_levels(symbol)
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error calculating levels: {e}")
                time.sleep(10)
    
    def refresh_prices(self) -> None:
        """Fetch latest prices from Binance now (1 req for all symbols). Call before reading to get freshest price."""
        self._fetch_current_prices()

    def _fetch_current_prices(self):
        """Fetch current prices from Binance"""
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    'https://fapi.binance.com/fapi/v1/ticker/price',
                    timeout=10
                )
                prices = response.json()
                
                for ticker in prices:
                    symbol = ticker['symbol']
                    if symbol in self.symbols:
                        self.current_prices[symbol] = float(ticker['price'])
        except Exception as e:
            print(f"Error fetching prices: {e}")
    
    def _fetch_open_interest(self, symbol: str):
        """
        Fetch Open Interest data from Binance and estimate distribution
        
        Uses order book depth to estimate position concentration at price levels
        """
        try:
            with httpx.Client(timeout=10) as client:
                # Fetch aggregate OI
                oi_response = client.get(
                    f'https://fapi.binance.com/fapi/v1/openInterest',
                    params={'symbol': symbol},
                    timeout=10
                )
                oi_data = oi_response.json()
                
                # Fetch order book depth to estimate position distribution
                depth_response = client.get(
                    f'https://fapi.binance.com/fapi/v1/depth',
                    params={'symbol': symbol, 'limit': 100},  # Top 100 levels
                    timeout=10
                )
                depth_data = depth_response.json()
                
                total_oi = float(oi_data.get('openInterest', 0))
                current_price = self.current_prices.get(symbol, 0)
                total_oi_usd = total_oi * current_price
                
                # Estimate long/short distribution from order book
                # Bids (buyers) = potential long positions
                # Asks (sellers) = potential short positions
                bids = depth_data.get('bids', [])
                asks = depth_data.get('asks', [])
                
                # Calculate weighted distribution
                bid_volume = sum(float(qty) * float(price) for price, qty in bids)
                ask_volume = sum(float(qty) * float(price) for price, qty in asks)
                total_depth_volume = bid_volume + ask_volume
                
                if total_depth_volume > 0:
                    long_ratio = bid_volume / total_depth_volume
                    short_ratio = ask_volume / total_depth_volume
                else:
                    long_ratio = 0.5
                    short_ratio = 0.5
                
                long_oi_usd = total_oi_usd * long_ratio
                short_oi_usd = total_oi_usd * short_ratio
                
                # Store order book data for position distribution estimation
                self.open_interest_data[symbol] = {
                    'total_oi': total_oi,
                    'total_oi_usd': total_oi_usd,
                    'long_oi_usd': long_oi_usd,
                    'short_oi_usd': short_oi_usd,
                    'long_short_ratio': long_ratio / short_ratio if short_ratio > 0 else 1.0,
                    'order_book_bids': bids[:50],  # Store top 50 for distribution
                    'order_book_asks': asks[:50],
                    'last_update': datetime.now()
                }
                
        except Exception as e:
            print(f"Error fetching OI for {symbol}: {e}")
            # Fallback to simple 50/50 split
            if symbol in self.current_prices:
                current_price = self.current_prices[symbol]
                # Try to get OI from simpler endpoint
                try:
                    with httpx.Client(timeout=10) as client:
                        oi_response = client.get(
                            f'https://fapi.binance.com/fapi/v1/openInterest',
                            params={'symbol': symbol},
                            timeout=10
                        )
                        oi_data = oi_response.json()
                        total_oi = float(oi_data.get('openInterest', 0))
                        total_oi_usd = total_oi * current_price
                        
                        self.open_interest_data[symbol] = {
                            'total_oi': total_oi,
                            'total_oi_usd': total_oi_usd,
                            'long_oi_usd': total_oi_usd * 0.5,
                            'short_oi_usd': total_oi_usd * 0.5,
                            'long_short_ratio': 1.0,
                            'order_book_bids': [],
                            'order_book_asks': [],
                            'last_update': datetime.now()
                        }
                except:
                    pass
    
    def _calculate_liquidation_levels(self, symbol: str):
        """
        Calculate liquidation levels for a symbol based on current price and OI
        
        Formula:
        - Long liquidation: L = P × (1 - 1/Leverage)
        - Short liquidation: L = P × (1 + 1/Leverage)
        """
        if symbol not in self.current_prices or symbol not in self.open_interest_data:
            return
        
        current_price = self.current_prices[symbol]
        oi_data = self.open_interest_data[symbol]
        
        levels = []
        cluster_id = 0
        
        # Estimate OI distribution across leverage tiers
        # Higher leverage = more risk = assume more OI at higher leverage
        # Use exponential distribution: more OI at lower leverage (safer), less at higher (riskier)
        leverage_weights = {}
        total_weight = 0
        for lev in self.leverage_tiers:
            # Inverse relationship: lower leverage gets more weight (more positions)
            weight = 1.0 / (lev ** 0.5)  # Square root decay
            leverage_weights[lev] = weight
            total_weight += weight
        
        # Normalize weights
        for lev in leverage_weights:
            leverage_weights[lev] /= total_weight
        
        # Dynamic OI floor: absolute minimum + % of total OI
        total_oi_usd = oi_data.get('total_oi_usd', 0.0) or 0.0
        dynamic_min_oi = max(self.min_oi_threshold, total_oi_usd * self.min_oi_threshold_pct)
        
        # Calculate levels for each leverage tier
        for leverage in self.leverage_tiers:
            weight = leverage_weights[leverage]
            
            # Long liquidation levels (below current price)
            # Formula: L = P × (1 - 1/Leverage)
            long_liq_price = current_price * (1 - 1/leverage)
            distance_pct = abs((long_liq_price - current_price) / current_price) * 100
            
            # Distribute OI based on weight
            oi_per_tier = oi_data['long_oi_usd'] * weight
            
            if oi_per_tier >= dynamic_min_oi:
                max_oi = oi_data['total_oi_usd']
                strength = _strength_from_oi_fraction(oi_per_tier, max_oi)
                
                # Estimate position count (assume average position size)
                avg_position_size = current_price * 0.01  # Rough estimate
                liquidation_count = int(oi_per_tier / avg_position_size) if avg_position_size > 0 else 0
                
                level = LiquidationLevel(
                    price_level=long_liq_price,
                    side='long',
                    leverage_tier=leverage,
                    open_interest=oi_per_tier,
                    liquidation_count=liquidation_count,
                    strength=strength,
                    distance_from_price=distance_pct,
                    cluster_id=cluster_id,
                    last_updated=datetime.now()
                )
                levels.append(level)
                cluster_id += 1
            
            # Short liquidation levels (above current price)
            # Formula: L = P × (1 + 1/Leverage)
            short_liq_price = current_price * (1 + 1/leverage)
            distance_pct = abs((short_liq_price - current_price) / current_price) * 100
            
            oi_per_tier = oi_data['short_oi_usd'] * weight
            
            if oi_per_tier >= dynamic_min_oi:
                max_oi = oi_data['total_oi_usd']
                strength = _strength_from_oi_fraction(oi_per_tier, max_oi)
                
                avg_position_size = current_price * 0.01
                liquidation_count = int(oi_per_tier / avg_position_size) if avg_position_size > 0 else 0
                
                level = LiquidationLevel(
                    price_level=short_liq_price,
                    side='short',
                    leverage_tier=leverage,
                    open_interest=oi_per_tier,
                    liquidation_count=liquidation_count,
                    strength=strength,
                    distance_from_price=distance_pct,
                    cluster_id=cluster_id,
                    last_updated=datetime.now()
                )
                levels.append(level)
                cluster_id += 1
        
        # Cluster nearby levels into buckets
        clustered_levels = self._cluster_levels(levels, current_price)
        
        # Apply noise reduction: filter and deduplicate
        filtered_levels = self._reduce_noise(clustered_levels, current_price)
        
        self.liquidation_levels[symbol] = filtered_levels
        self.last_update[symbol] = datetime.now()
    
    def _cluster_levels(self, levels: List[LiquidationLevel], current_price: float) -> List[LiquidationLevel]:
        """
        Cluster liquidation levels into price buckets
        
        Groups levels within price_bucket_pct of each other
        """
        if not levels:
            return []
        
        # Sort by price
        sorted_levels = sorted(levels, key=lambda x: x.price_level)
        
        # Group into buckets
        buckets = defaultdict(list)
        for level in sorted_levels:
            # Calculate bucket index
            price_delta = abs(level.price_level - current_price) / current_price
            bucket_idx = int(price_delta / self.price_bucket_pct)
            buckets[bucket_idx].append(level)
        
        # Aggregate buckets
        clustered = []
        cluster_id = 0
        for bucket_idx in sorted(buckets.keys()):
            bucket_levels = buckets[bucket_idx]
            
            # Aggregate OI and calculate weighted average price
            total_oi = sum(level.open_interest for level in bucket_levels)
            total_count = sum(level.liquidation_count for level in bucket_levels)
            weighted_price = sum(level.price_level * level.open_interest for level in bucket_levels) / total_oi if total_oi > 0 else bucket_levels[0].price_level
            
            # Determine dominant side
            long_oi = sum(level.open_interest for level in bucket_levels if level.side == 'long')
            short_oi = sum(level.open_interest for level in bucket_levels if level.side == 'short')
            dominant_side = 'long' if long_oi > short_oi else 'short'
            
            # Calculate average leverage
            avg_leverage = np.mean([level.leverage_tier for level in bucket_levels])
            
            # Calculate strength (normalized)
            max_strength = max(level.strength for level in bucket_levels)
            
            distance_pct = abs((weighted_price - current_price) / current_price) * 100
            
            clustered_level = LiquidationLevel(
                price_level=weighted_price,
                side=dominant_side,
                leverage_tier=avg_leverage,
                open_interest=total_oi,
                liquidation_count=total_count,
                strength=max_strength,
                distance_from_price=distance_pct,
                cluster_id=cluster_id,
                last_updated=datetime.now()
            )
            clustered.append(clustered_level)
            cluster_id += 1
        
        return clustered
    
    def _reduce_noise(self, levels: List[LiquidationLevel], current_price: float) -> List[LiquidationLevel]:
        """
        Reduce noise by:
        1. Filtering out weak clusters
        2. Merging clusters that are too close together
        3. Prioritizing stronger signals
        """
        if not levels:
            return []
        
        # Sort by strength (descending) and distance (ascending)
        sorted_levels = sorted(levels, key=lambda x: (-x.strength, x.distance_from_price))
        
        filtered = []
        used_prices = set()
        
        for level in sorted_levels:
            # Skip if too close to an already selected cluster
            too_close = False
            for used_price in used_prices:
                price_diff_pct = abs(level.price_level - used_price) / current_price * 100
                if price_diff_pct < self.min_cluster_distance_pct:
                    too_close = True
                    break
            
            if not too_close:
                # Calculate signal quality score (combines strength, OI, and distance)
                # Higher score = better signal
                quality_score = (
                    level.strength * 0.5 +  # Strength weight
                    min(level.open_interest / 10000000, 1.0) * 0.3 +  # OI weight (normalized)
                    (1.0 / (1.0 + level.distance_from_price / 10)) * 0.2  # Distance weight (closer = better)
                )
                
                # Only include high-quality signals
                if quality_score >= 0.15:  # Minimum quality threshold
                    filtered.append(level)
                    used_prices.add(level.price_level)
        
        # Sort by price for display
        return sorted(filtered, key=lambda x: x.price_level)
    
    def get_levels(self, symbol: str, min_strength: float = 0.0, max_distance: float = 50.0) -> List[LiquidationLevel]:
        """
        Get liquidation levels for a symbol
        
        Args:
            symbol: Trading symbol
            min_strength: Minimum cluster strength (0-1)
            max_distance: Maximum distance from price (%)
        """
        if symbol not in self.liquidation_levels:
            return []
        
        levels = self.liquidation_levels[symbol]
        
        # Filter
        filtered = [
            level for level in levels
            if level.strength >= min_strength and level.distance_from_price <= max_distance
        ]
        
        return filtered
    
    def update_price(self, symbol: str, price: float):
        """Update current price for a symbol (triggers recalculation)"""
        self.current_prices[symbol] = price
