#!/usr/bin/env python3
"""
Liquidation Hunter Trading Agent for PriveX
Scans liquidation heatmaps for strong clusters that act as price magnets
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import ccxt
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist

@dataclass
class LiquidationCluster:
    """Represents a cluster of liquidations at a price level"""
    price_level: float
    liquidation_count: int
    total_notional: float  # Total value of liquidations
    side: str  # 'long' or 'short' (which side gets liquidated)
    strength: float  # Normalized strength (0-1)
    distance_from_price: float  # Distance from current price (%)
    cluster_id: int

@dataclass
class Position:
    """Active trading position"""
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    entry_time: datetime
    size: float
    leverage: float
    stop_loss: float
    take_profit: float
    target_cluster: Optional[LiquidationCluster] = None  # Target liquidation cluster

@dataclass
class Trade:
    """Completed trade record"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    size: float
    leverage: float
    pnl: float
    pnl_pct: float
    fees: float
    reason: str
    cluster_target: Optional[float] = None

class LiquidationHunter:
    """
    Autonomous liquidation hunter agent for PriveX perpetual futures
    Identifies strong liquidation clusters and trades toward them
    """
    
    def __init__(self,
                 initial_capital: float = 10000.0,
                 max_leverage: float = 20.0,
                 stop_loss_pct: float = 0.03,  # Tighter stops for liquidation hunting
                 take_profit_pct: float = 0.05,  # Target cluster zones
                 fee_rate: float = 0.0001,
                 min_cluster_strength: float = 0.6,  # Minimum cluster strength to trade
                 max_distance_pct: float = 0.10,  # Max 10% from current price
                 cluster_window_pct: float = 0.02):  # 2% window for clustering
        """
        Initialize liquidation hunter
        
        Args:
            initial_capital: Starting balance in USDT
            max_leverage: Maximum leverage per position
            stop_loss_pct: Stop loss as % of entry
            take_profit_pct: Take profit as % of entry
            fee_rate: Maker/taker fee rate
            min_cluster_strength: Minimum normalized cluster strength (0-1)
            max_distance_pct: Maximum distance from current price to consider cluster
            cluster_window_pct: Price window for clustering liquidations (%)
        """
        self.initial_capital = initial_capital
        self.max_leverage = max_leverage
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.fee_rate = fee_rate
        self.min_cluster_strength = min_cluster_strength
        self.max_distance_pct = max_distance_pct
        self.cluster_window_pct = cluster_window_pct
        
        # Runtime state
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.equity_curve = [initial_capital]
        self.order_history = []
        
        # Liquidation data cache
        self.liquidation_data: Dict[str, List[Dict]] = defaultdict(list)
        self.clusters: Dict[str, List[LiquidationCluster]] = {}
        
        # Exchange connection (for fetching liquidation data)
        self.exchange = None  # Will be set via set_exchange()
    
    def set_data_source(self, source: str = 'auto', **kwargs):
        """
        Set up liquidation data source
        
        Args:
            source: 'coinglass', 'exchange', 'orderbook', 'live_binance', or 'auto'
            **kwargs: Source-specific config:
                - coinglass_api_key: For Coinglass API
                - exchange_name: Exchange name ('binance', 'bybit', etc.)
                - api_key, api_secret: Exchange API credentials
                - live_heatmap: LiveLiquidationHeatmap instance (for 'live_binance')
                - symbols: List of symbols for live stream (for 'live_binance')
        """
        self.current_price_cache = {}  # Cache for orderbook estimation
        
        # Handle live Binance heatmap
        if source == 'live_binance':
            from live_liquidation_heatmap import LiveLiquidationHeatmap, LiveLiquidationDataFetcher
            
            if 'live_heatmap' in kwargs:
                # Use provided heatmap
                heatmap = kwargs['live_heatmap']
            else:
                # Create new heatmap
                heatmap = LiveLiquidationHeatmap(
                    cluster_window_pct=self.cluster_window_pct,
                    min_cluster_size=5,
                    time_decay_minutes=60,
                    update_interval=5.0
                )
                
                # Start stream
                symbols = kwargs.get('symbols', ['BTCUSDT', 'ETHUSDT'])
                heatmap.start_stream(symbols=symbols)
            
            # Create fetcher adapter
            self.data_aggregator = LiveLiquidationDataFetcher(heatmap)
            self.live_heatmap = heatmap  # Store reference
        else:
            # Use regular aggregator
            from liquidation_data_sources import LiquidationDataAggregator
            self.data_aggregator = LiquidationDataAggregator(source=source, **kwargs)
            self.live_heatmap = None
    
    def set_exchange(self, exchange_name: str = 'binance', api_key: str = None, 
                     api_secret: str = None):
        """
        Legacy method - use set_data_source() instead
        Kept for backward compatibility
        """
        self.set_data_source(
            source='exchange',
            exchange_name=exchange_name,
            api_key=api_key,
            api_secret=api_secret
        )
    
    def fetch_liquidation_data(self, symbol: str, limit: int = 1000, 
                              current_price: float = None) -> List[Dict]:
        """
        Fetch recent liquidation data from configured source
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT:USDT' or 'BTCUSDT')
            limit: Number of liquidations to fetch (for exchange APIs)
            current_price: Current price (needed for orderbook estimation and live heatmap)
            
        Returns:
            List of liquidation dictionaries with price, side, size, etc.
        """
        # Normalize symbol format (remove /USDT:USDT if present)
        normalized_symbol = symbol.replace('/USDT:USDT', '').replace('/', '').upper()
        
        # Use data aggregator if available
        if hasattr(self, 'data_aggregator'):
            # Live heatmap uses different fetch signature
            if hasattr(self.data_aggregator, 'fetch'):
                return self.data_aggregator.fetch(normalized_symbol, current_price)
            else:
                # Regular aggregator
                return self.data_aggregator.fetch(normalized_symbol, current_price)
        
        # Fallback to legacy exchange method
        if hasattr(self, 'exchange') and self.exchange:
            try:
                if hasattr(self.exchange, 'fetch_liquidations'):
                    liquidations = self.exchange.fetch_liquidations(symbol, limit=limit)
                    return liquidations
            except Exception as e:
                print(f"Error fetching liquidations: {e}")
        
        # Final fallback: mock data for testing
        return self._generate_mock_liquidations(symbol)
    
    def _generate_mock_liquidations(self, symbol: str) -> List[Dict]:
        """
        Generate mock liquidation data for testing
        In production, use set_data_source() with real API
        """
        return []
    
    def identify_clusters(self, liquidations: List[Dict], current_price: float) -> List[LiquidationCluster]:
        """
        Identify strong liquidation clusters from liquidation data
        
        Args:
            liquidations: List of liquidation dicts with 'price', 'side', 'size'
            current_price: Current market price
            
        Returns:
            List of LiquidationCluster objects sorted by strength
        """
        if not liquidations:
            return []
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(liquidations)
        
        if len(df) == 0:
            return []
        
        # Extract price levels and sides
        prices = df['price'].values if 'price' in df.columns else df['price'].values
        sides = df['side'].values if 'side' in df.columns else ['long'] * len(df)
        sizes = df['size'].values if 'size' in df.columns else df.get('notional', [1.0] * len(df))
        
        # Normalize prices relative to current price
        price_pcts = ((prices - current_price) / current_price) * 100
        
        # Filter by max distance
        valid_mask = np.abs(price_pcts) <= self.max_distance_pct * 100
        prices = prices[valid_mask]
        sides = sides[valid_mask] if isinstance(sides, np.ndarray) else [s for i, s in enumerate(sides) if valid_mask[i]]
        sizes = sizes[valid_mask] if isinstance(sizes, np.ndarray) else [s for i, s in enumerate(sizes) if valid_mask[i]]
        price_pcts = price_pcts[valid_mask]
        
        if len(prices) == 0:
            return []
        
        # Cluster liquidations by price (hierarchical clustering)
        # Use price percentage as feature
        price_data = price_pcts.reshape(-1, 1)
        
        # Calculate distance threshold based on cluster_window_pct
        distance_threshold = self.cluster_window_pct * 100  # Convert to percentage
        
        # Perform clustering
        if len(prices) > 1:
            try:
                linkage_matrix = linkage(price_data, method='ward')
                cluster_labels = fcluster(linkage_matrix, distance_threshold, criterion='distance')
            except:
                # Fallback: simple binning
                bins = np.arange(price_pcts.min(), price_pcts.max() + distance_threshold, distance_threshold)
                cluster_labels = np.digitize(price_pcts, bins)
        else:
            cluster_labels = [1]
        
        # Aggregate clusters
        cluster_dict = defaultdict(lambda: {'prices': [], 'sides': [], 'sizes': []})
        
        for i, label in enumerate(cluster_labels):
            cluster_dict[label]['prices'].append(prices[i])
            cluster_dict[label]['sides'].append(sides[i] if isinstance(sides, list) else sides[i])
            cluster_dict[label]['sizes'].append(sizes[i] if isinstance(sizes, list) else sizes[i])
        
        clusters = []
        max_count = max(len(c['prices']) for c in cluster_dict.values()) if cluster_dict else 1
        max_notional = max(sum(c['sizes']) for c in cluster_dict.values()) if cluster_dict else 1
        
        for cluster_id, data in cluster_dict.items():
            prices_in_cluster = np.array(data['prices'])
            sides_in_cluster = data['sides']
            sizes_in_cluster = np.array(data['sizes'])
            
            # Calculate cluster center (weighted by size)
            if len(sizes_in_cluster) > 0:
                total_notional = np.sum(sizes_in_cluster)
                weighted_price = np.average(prices_in_cluster, weights=sizes_in_cluster)
            else:
                total_notional = 0
                weighted_price = np.mean(prices_in_cluster)
            
            # Determine dominant side (which side gets liquidated)
            long_count = sum(1 for s in sides_in_cluster if s == 'long' or s == 'buy')
            short_count = len(sides_in_cluster) - long_count
            dominant_side = 'long' if long_count > short_count else 'short'
            
            # Calculate strength (normalized 0-1)
            count_strength = len(prices_in_cluster) / max_count if max_count > 0 else 0
            notional_strength = total_notional / max_notional if max_notional > 0 else 0
            strength = (count_strength * 0.5 + notional_strength * 0.5)  # Weighted average
            
            # Distance from current price
            distance_pct = abs((weighted_price - current_price) / current_price) * 100
            
            cluster = LiquidationCluster(
                price_level=weighted_price,
                liquidation_count=len(prices_in_cluster),
                total_notional=total_notional,
                side=dominant_side,
                strength=strength,
                distance_from_price=distance_pct,
                cluster_id=cluster_id
            )
            
            clusters.append(cluster)
        
        # Sort by strength (descending)
        clusters.sort(key=lambda x: x.strength, reverse=True)
        
        return clusters
    
    def find_best_cluster(self, symbol: str, current_price: float) -> Optional[LiquidationCluster]:
        """
        Find the strongest liquidation cluster to target
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT:USDT' or 'BTCUSDT')
            current_price: Current market price
            
        Returns:
            Best LiquidationCluster to target, or None
        """
        # Normalize symbol
        normalized_symbol = symbol.replace('/USDT:USDT', '').replace('/', '').upper()
        
        # Cache current price for orderbook estimation and live heatmap
        self.current_price_cache[symbol] = current_price
        
        # Update live heatmap price if using live source
        if hasattr(self, 'live_heatmap') and self.live_heatmap:
            self.live_heatmap.update_price(normalized_symbol, current_price)
        
        # Fetch latest liquidation data (pass current_price for orderbook estimation)
        liquidations = self.fetch_liquidation_data(symbol, current_price=current_price)
        
        # Identify clusters
        clusters = self.identify_clusters(liquidations, current_price)
        
        if not clusters:
            return None
        
        # Filter by minimum strength
        strong_clusters = [c for c in clusters if c.strength >= self.min_cluster_strength]
        
        if not strong_clusters:
            return None
        
        # Find cluster that price can move toward
        # If price is above a long liquidation cluster, we can short (price falls)
        # If price is below a short liquidation cluster, we can long (price rises)
        
        best_cluster = None
        best_score = 0
        
        for cluster in strong_clusters:
            # Calculate score based on:
            # 1. Cluster strength
            # 2. Distance (closer = better, but not too close)
            # 3. Direction (can we trade toward it?)
            
            # Check if we can trade toward this cluster
            can_trade = False
            if cluster.side == 'long' and current_price > cluster.price_level:
                # Long liquidations below price → short to target
                can_trade = True
            elif cluster.side == 'short' and current_price < cluster.price_level:
                # Short liquidations above price → long to target
                can_trade = True
            
            if not can_trade:
                continue
            
            # Score: strength * (1 - normalized_distance)
            # Prefer clusters 2-5% away (sweet spot)
            ideal_distance = 0.035  # 3.5%
            distance_score = 1.0 - min(abs(cluster.distance_from_price / 100 - ideal_distance) / ideal_distance, 1.0)
            
            score = cluster.strength * 0.7 + distance_score * 0.3
            
            if score > best_score:
                best_score = score
                best_cluster = cluster
        
        return best_cluster
    
    def generate_signal(self, symbol: str, current_price: float) -> Tuple[int, float, Optional[LiquidationCluster]]:
        """
        Generate trading signal based on liquidation clusters
        
        Args:
            symbol: Trading pair
            current_price: Current market price
            
        Returns:
            Tuple of (signal, strength, target_cluster)
            signal: 1 for long, -1 for short, 0 for no signal
            strength: Signal strength (0-1)
            target_cluster: Target liquidation cluster
        """
        cluster = self.find_best_cluster(symbol, current_price)
        
        if not cluster:
            return (0, 0.0, None)
        
        # Determine signal direction
        signal = 0
        if cluster.side == 'long' and current_price > cluster.price_level:
            # Long liquidations below → short
            signal = -1
        elif cluster.side == 'short' and current_price < cluster.price_level:
            # Short liquidations above → long
            signal = 1
        
        # Signal strength based on cluster strength and distance
        distance_factor = max(0, 1.0 - (cluster.distance_from_price / 100) / self.max_distance_pct)
        strength = cluster.strength * distance_factor
        
        return (signal, strength, cluster)
    
    def calculate_position_size(self, symbol: str, current_price: float, 
                               cluster: LiquidationCluster) -> float:
        """
        Calculate position size based on cluster strength and risk
        """
        # Base allocation: stronger clusters = larger positions
        base_allocation = 0.15  # 15% base
        strength_multiplier = cluster.strength  # 0-1
        
        allocation = base_allocation * (0.5 + strength_multiplier * 0.5)  # 7.5% to 15%
        
        position_capital = self.capital * allocation * self.max_leverage
        position_size = position_capital / current_price
        
        return position_size
    
    def enter_position(self, symbol: str, signal: int, price: float,
                       time: datetime, cluster: LiquidationCluster) -> Optional[Position]:
        """
        Enter a new position targeting a liquidation cluster
        """
        # Don't re-enter if position exists
        if symbol in self.positions:
            return None
        
        # Calculate position sizing
        size = self.calculate_position_size(symbol, price, cluster)
        if size <= 0:
            return None
        
        # Apply slippage
        slippage = price * 0.0005  # 5 bps
        entry_price = price + slippage if signal > 0 else price - slippage
        
        # Calculate stop/TP relative to cluster
        # Stop loss: opposite direction from cluster
        # Take profit: near cluster level
        
        if signal > 0:  # Long
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            # TP near cluster (but not exactly at it - exit before)
            cluster_distance_pct = abs((cluster.price_level - entry_price) / entry_price)
            take_profit = min(
                entry_price * (1 + self.take_profit_pct),
                cluster.price_level * 0.995  # 0.5% before cluster
            )
        else:  # Short
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            cluster_distance_pct = abs((cluster.price_level - entry_price) / entry_price)
            take_profit = max(
                entry_price * (1 - self.take_profit_pct),
                cluster.price_level * 1.005  # 0.5% before cluster
            )
        
        position = Position(
            symbol=symbol,
            side='long' if signal > 0 else 'short',
            entry_price=entry_price,
            entry_time=time,
            size=size,
            leverage=self.max_leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            target_cluster=cluster
        )
        
        # Deduct fees
        notional = size * entry_price
        fees = notional * self.fee_rate
        self.capital -= fees
        
        # Record
        self.positions[symbol] = position
        self.order_history.append({
            'time': time,
            'symbol': symbol,
            'action': 'ENTER',
            'side': position.side,
            'price': entry_price,
            'size': size,
            'leverage': self.max_leverage,
            'cluster_target': cluster.price_level,
            'cluster_strength': cluster.strength
        })
        
        return position
    
    def exit_position(self, symbol: str, price: float, time: datetime,
                     reason: str = 'manual') -> Optional[Trade]:
        """Exit an open position"""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Apply slippage
        slippage = price * 0.0005
        exit_price = price - slippage if position.side == 'long' else price + slippage
        
        # Calculate P&L
        if position.side == 'long':
            pnl = (exit_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - exit_price) * position.size
        
        pnl_pct = (pnl / (position.entry_price * position.size)) * 100
        
        # Deduct fees
        notional = position.size * exit_price
        fees = notional * self.fee_rate
        self.capital += pnl - fees
        
        # Record trade
        cluster_target = position.target_cluster.price_level if position.target_cluster else None
        
        trade = Trade(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=time,
            size=position.size,
            leverage=position.leverage,
            pnl=pnl,
            pnl_pct=pnl_pct,
            fees=fees,
            reason=reason,
            cluster_target=cluster_target
        )
        
        self.closed_trades.append(trade)
        del self.positions[symbol]
        
        self.order_history.append({
            'time': time,
            'symbol': symbol,
            'action': 'EXIT',
            'reason': reason,
            'price': exit_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'cluster_target': cluster_target
        })
        
        return trade
    
    def check_positions(self, current_prices: Dict[str, float],
                       current_time: datetime) -> List[Trade]:
        """
        Check all open positions for stop/TP hits or cluster proximity
        """
        closed = []
        
        for symbol, position in list(self.positions.items()):
            price = current_prices.get(symbol)
            if price is None:
                continue
            
            # Check stop loss
            if position.side == 'long' and price <= position.stop_loss:
                trade = self.exit_position(symbol, price, current_time, 'sl')
                if trade:
                    closed.append(trade)
                continue
            
            if position.side == 'short' and price >= position.stop_loss:
                trade = self.exit_position(symbol, price, current_time, 'sl')
                if trade:
                    closed.append(trade)
                continue
            
            # Check take profit
            if position.side == 'long' and price >= position.take_profit:
                trade = self.exit_position(symbol, price, current_time, 'tp')
                if trade:
                    closed.append(trade)
                continue
            
            if position.side == 'short' and price <= position.take_profit:
                trade = self.exit_position(symbol, price, current_time, 'tp')
                if trade:
                    closed.append(trade)
                continue
            
            # Check if price reached cluster (exit before cluster to avoid reversal)
            if position.target_cluster:
                cluster_price = position.target_cluster.price_level
                if position.side == 'long':
                    # Long targeting short liquidations above
                    if price >= cluster_price * 0.995:  # 0.5% before cluster
                        trade = self.exit_position(symbol, price, current_time, 'cluster_reached')
                        if trade:
                            closed.append(trade)
                        continue
                else:  # Short
                    # Short targeting long liquidations below
                    if price <= cluster_price * 1.005:  # 0.5% before cluster
                        trade = self.exit_position(symbol, price, current_time, 'cluster_reached')
                        if trade:
                            closed.append(trade)
                        continue
        
        return closed
    
    def get_status(self) -> Dict:
        """Get agent status"""
        total_pnl = sum(t.pnl for t in self.closed_trades)
        
        return {
            'capital': self.capital,
            'initial_capital': self.initial_capital,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / self.initial_capital) * 100,
            'open_positions': len(self.positions),
            'closed_trades': len(self.closed_trades),
            'positions': {
                s: {
                    **asdict(p),
                    'target_cluster_price': p.target_cluster.price_level if p.target_cluster else None
                }
                for s, p in self.positions.items()
            }
        }


if __name__ == '__main__':
    hunter = LiquidationHunter(
        initial_capital=10000.0,
        max_leverage=20.0,
        stop_loss_pct=0.03,
        take_profit_pct=0.05,
        min_cluster_strength=0.6
    )
    
    print("=" * 70)
    print("PRIVEX LIQUIDATION HUNTER")
    print("=" * 70)
    print("\nStrategy: Identify strong liquidation clusters and trade toward them")
    print("\nKey Features:")
    print("  • Scans liquidation heatmaps for clusters")
    print("  • Strong clusters act as price magnets")
    print("  • Enters positions anticipating movement toward clusters")
    print("  • Exits before cluster to avoid reversals")
    print("\n" + "=" * 70)
    print("Agent Ready for PriveX Integration")
    print("=" * 70)
