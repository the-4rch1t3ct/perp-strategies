#!/usr/bin/env python3
"""
Live Liquidation Cluster Heatmap for Binance Futures
Builds real-time liquidation clusters from Binance WebSocket streams
"""

try:
    import websocket
except ImportError:
    print("Warning: websocket-client not installed. Install with: pip install websocket-client")
    websocket = None

import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from dataclasses import dataclass, asdict

@dataclass
class LiquidationEvent:
    """Real-time liquidation event from Binance"""
    symbol: str
    side: str  # 'long' or 'short'
    price: float
    quantity: float
    notional: float  # USD value
    timestamp: datetime
    order_id: Optional[str] = None

@dataclass
class LiveCluster:
    """Live liquidation cluster"""
    price_level: float
    side: str
    liquidation_count: int
    total_notional: float
    strength: float  # 0-1
    distance_from_price: float  # %
    last_updated: datetime
    cluster_id: int

class BinanceLiquidationStream:
    """
    Real-time liquidation stream from Binance WebSocket
    """
    
    WS_BASE_URL = "wss://fstream.binance.com"
    
    def __init__(self, symbols: List[str] = None, callback=None):
        """
        Initialize Binance liquidation stream
        
        Args:
            symbols: List of symbols to monitor (e.g., ['BTCUSDT', 'ETHUSDT'])
                     If None, uses all-market stream
            callback: Function to call with each liquidation event
        """
        self.symbols = symbols
        self.callback = callback
        self.ws = None
        self.running = False
        self.reconnect_interval = 5
        self.liquidation_buffer = deque(maxlen=10000)  # Keep last 10k liquidations
        
    def _on_message(self, ws, message):
        """Handle WebSocket message"""
        try:
            data = json.loads(message)
            
            # Binance liquidation stream formats:
            # 1. Combined stream: {"stream":"btcusdt@forceOrder","data":{"e":"forceOrder","E":...,"o":{...}}}
            # 2. Single stream: {"e":"forceOrder","E":123456789,"o":{...}}
            
            # Extract the actual liquidation order data
            if 'stream' in data and 'data' in data:
                # Combined stream format - data contains the event
                event = data['data']
                if event.get('e') == 'forceOrder' and 'o' in event:
                    event_data = event['o']
                else:
                    event_data = event
            elif 'e' in data and data.get('e') == 'forceOrder':
                # Single stream format - liquidation data is in 'o' field
                event_data = data.get('o', {})
            else:
                # Try direct format (fallback)
                event_data = data
            
            # Parse liquidation event (Binance format)
            # Fields: s=symbol, S=side (BUY/SELL), p=price, q=quantity, T=trade time
            symbol = event_data.get('s', '').upper()
            side_str = event_data.get('S', '').upper()  # BUY = long liquidation, SELL = short liquidation
            price_str = event_data.get('p', '0')
            quantity_str = event_data.get('q', '0')
            
            try:
                price = float(price_str) if price_str else 0
                quantity = float(quantity_str) if quantity_str else 0
            except (ValueError, TypeError):
                price = 0
                quantity = 0
            
            timestamp_ms = event_data.get('T', data.get('E', int(time.time() * 1000)))
            
            if price > 0 and quantity > 0 and symbol:
                # Determine side: BUY = long position liquidated (price fell), SELL = short liquidated (price rose)
                side = 'long' if side_str == 'BUY' else 'short'
                notional = quantity * price
                
                liquidation = LiquidationEvent(
                    symbol=symbol,
                    side=side,
                    price=price,
                    quantity=quantity,
                    notional=notional,
                    timestamp=datetime.fromtimestamp(timestamp_ms / 1000),
                    order_id=None
                )
                
                # Add to buffer
                self.liquidation_buffer.append(liquidation)
                
                # Debug: print first few liquidations
                if len(self.liquidation_buffer) <= 10:
                    print(f"✅ Liquidation: {symbol} {side} @ ${price:.2f} (qty: {quantity:.6f}, notional: ${notional:.2f})")
                
                # Call callback if provided
                if self.callback:
                    self.callback(liquidation)
            else:
                # Debug: log malformed messages (only first few)
                if len(self.liquidation_buffer) < 5:
                    print(f"⚠️  Skipped: symbol={symbol}, price={price_str}, qty={quantity_str}, side={side_str}")
                    
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            if len(self.liquidation_buffer) < 3:
                import traceback
                traceback.print_exc()
    
    def _on_error(self, ws, error):
        """Handle WebSocket error"""
        print(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print("WebSocket closed")
        if self.running:
            # Reconnect after delay
            time.sleep(self.reconnect_interval)
            self.start()
    
    def _on_open(self, ws):
        """Handle WebSocket open"""
        print("✅ WebSocket connected to Binance liquidation stream")
        print(f"   Monitoring {len(self.symbols) if self.symbols else 'all'} symbols")
    
    def start(self):
        """Start WebSocket connection"""
        if websocket is None:
            raise ImportError("websocket-client not installed. Install with: pip install websocket-client")
        
        if self.running:
            return
        
        self.running = True
        
        # Build stream name
        # Binance Futures liquidation stream format:
        # Single: wss://fstream.binance.com/ws/btcusdt@forceOrder
        # Multiple: wss://fstream.binance.com/stream?streams=btcusdt@forceOrder/ethusdt@forceOrder
        # All market: wss://fstream.binance.com/stream?streams=!forceOrder@arr
        if self.symbols:
            if len(self.symbols) == 1:
                # Single symbol stream
                symbol = self.symbols[0].lower()
                url = f"{self.WS_BASE_URL}/ws/{symbol}@forceOrder"
            else:
                # Multiple symbol-specific streams
                streams = [f"{symbol.lower()}@forceOrder" for symbol in self.symbols]
                stream_path = "/".join(streams)
                url = f"{self.WS_BASE_URL}/stream?streams={stream_path}"
        else:
            # All-market stream
            url = f"{self.WS_BASE_URL}/stream?streams=!forceOrder@arr"
        
        print(f"Connecting to Binance liquidation stream: {url}")
        
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Run in separate thread
        def run_forever():
            self.ws.run_forever()
        
        thread = threading.Thread(target=run_forever, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
    
    def get_recent_liquidations(self, symbol: str = None, 
                               minutes: int = 60) -> List[LiquidationEvent]:
        """
        Get recent liquidations from buffer
        
        Args:
            symbol: Filter by symbol (None = all symbols)
            minutes: Minutes of history
            
        Returns:
            List of LiquidationEvent objects
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        liquidations = [
            liq for liq in self.liquidation_buffer
            if liq.timestamp >= cutoff_time and (symbol is None or liq.symbol == symbol)
        ]
        
        return liquidations


class LiveLiquidationHeatmap:
    """
    Builds live liquidation clusters from real-time Binance data
    """
    
    def __init__(self, 
                 cluster_window_pct: float = 0.02,
                 min_cluster_size: int = 5,
                 time_decay_minutes: int = 60,
                 update_interval: float = 5.0):
        """
        Initialize live heatmap
        
        Args:
            cluster_window_pct: Price window for clustering (%)
            min_cluster_size: Minimum liquidations per cluster
            time_decay_minutes: Minutes for time decay weighting
            update_interval: Seconds between cluster updates
        """
        self.cluster_window_pct = cluster_window_pct
        self.min_cluster_size = min_cluster_size
        self.time_decay_minutes = time_decay_minutes
        self.update_interval = update_interval
        
        self.stream = None
        self.clusters: Dict[str, List[LiveCluster]] = {}
        self.current_prices: Dict[str, float] = {}
        self.last_update: Dict[str, datetime] = {}
        
    def start_stream(self, symbols: List[str] = None):
        """
        Start live liquidation stream
        
        Args:
            symbols: Symbols to monitor (None = all symbols)
        """
        def on_liquidation(liquidation: LiquidationEvent):
            """Handle new liquidation"""
            # Update clusters periodically
            symbol = liquidation.symbol
            if symbol not in self.last_update or \
               (datetime.now() - self.last_update[symbol]).total_seconds() >= self.update_interval:
                self._update_clusters(symbol)
        
        self.stream = BinanceLiquidationStream(symbols=symbols, callback=on_liquidation)
        self.stream.start()
    
    def stop_stream(self):
        """Stop live stream"""
        if self.stream:
            self.stream.stop()
    
    def update_price(self, symbol: str, price: float):
        """Update current price for a symbol"""
        self.current_prices[symbol] = price
    
    def _update_clusters(self, symbol: str):
        """Update clusters for a symbol"""
        if symbol not in self.current_prices:
            return
        
        current_price = self.current_prices[symbol]
        
        # Get recent liquidations
        liquidations = self.stream.get_recent_liquidations(
            symbol=symbol,
            minutes=self.time_decay_minutes // 60
        )
        
        if len(liquidations) < self.min_cluster_size:
            self.clusters[symbol] = []
            return
        
        # Build clusters
        clusters = self._build_clusters(liquidations, current_price)
        self.clusters[symbol] = clusters
        self.last_update[symbol] = datetime.now()
    
    def _build_clusters(self, liquidations: List[LiquidationEvent],
                       current_price: float) -> List[LiveCluster]:
        """
        Build clusters from liquidation events
        
        Args:
            liquidations: List of LiquidationEvent objects
            current_price: Current market price
            
        Returns:
            List of LiveCluster objects
        """
        if not liquidations:
            return []
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'price': liq.price,
            'side': liq.side,
            'notional': liq.notional,
            'timestamp': liq.timestamp
        } for liq in liquidations])
        
        # Calculate time decay weights
        now = datetime.now()
        df['age_minutes'] = (now - df['timestamp']).dt.total_seconds() / 60
        df['time_weight'] = np.exp(-df['age_minutes'] / self.time_decay_minutes)
        
        # Filter by distance
        df['distance_pct'] = abs((df['price'] - current_price) / current_price) * 100
        max_distance = 10.0  # 10% max
        df = df[df['distance_pct'] <= max_distance].copy()
        
        if len(df) == 0:
            return []
        
        # Separate by side
        long_liq = df[df['side'] == 'long'].copy()
        short_liq = df[df['side'] == 'short'].copy()
        
        clusters = []
        
        # Build clusters for each side
        if len(long_liq) > 0:
            long_clusters = self._cluster_by_price(long_liq, current_price, 'long')
            clusters.extend(long_clusters)
        
        if len(short_liq) > 0:
            short_clusters = self._cluster_by_price(short_liq, current_price, 'short')
            clusters.extend(short_clusters)
        
        # Sort by strength
        clusters.sort(key=lambda x: x.strength, reverse=True)
        
        return clusters
    
    def _cluster_by_price(self, df: pd.DataFrame, current_price: float,
                         side: str) -> List[LiveCluster]:
        """Cluster liquidations by price level"""
        if len(df) < self.min_cluster_size:
            return []
        
        prices = df['price'].values
        price_pcts = ((prices - current_price) / current_price) * 100
        
        distance_threshold = self.cluster_window_pct * 100
        
        if len(prices) > 1:
            try:
                price_data = price_pcts.reshape(-1, 1)
                linkage_matrix = linkage(price_data, method='ward')
                cluster_labels = fcluster(linkage_matrix, distance_threshold,
                                         criterion='distance')
            except:
                bins = np.arange(price_pcts.min(),
                               price_pcts.max() + distance_threshold,
                               distance_threshold)
                cluster_labels = np.digitize(price_pcts, bins)
        else:
            cluster_labels = [1]
        
        cluster_dict = defaultdict(lambda: {
            'prices': [],
            'notionals': [],
            'time_weights': []
        })
        
        for i, label in enumerate(cluster_labels):
            cluster_dict[label]['prices'].append(prices[i])
            cluster_dict[label]['notionals'].append(df.iloc[i]['notional'])
            cluster_dict[label]['time_weights'].append(df.iloc[i]['time_weight'])
        
        clusters = []
        
        all_counts = [len(c['prices']) for c in cluster_dict.values()]
        all_notionals = [sum(c['notionals']) for c in cluster_dict.values()]
        max_count = max(all_counts) if all_counts else 1
        max_notional = max(all_notionals) if all_notionals else 1
        
        for cluster_id, data in cluster_dict.items():
            if len(data['prices']) < self.min_cluster_size:
                continue
            
            prices_in_cluster = np.array(data['prices'])
            notionals_in_cluster = np.array(data['notionals'])
            time_weights = np.array(data['time_weights'])
            
            weights = notionals_in_cluster * time_weights
            if weights.sum() > 0:
                weighted_price = np.average(prices_in_cluster, weights=weights)
            else:
                weighted_price = np.mean(prices_in_cluster)
            
            total_notional = (notionals_in_cluster * time_weights).sum()
            
            count_strength = len(prices_in_cluster) / max_count if max_count > 0 else 0
            notional_strength = total_notional / max_notional if max_notional > 0 else 0
            strength = (count_strength * 0.4 + notional_strength * 0.6)
            
            distance_pct = abs((weighted_price - current_price) / current_price) * 100
            
            cluster = LiveCluster(
                price_level=weighted_price,
                side=side,
                liquidation_count=len(prices_in_cluster),
                total_notional=total_notional,
                strength=strength,
                distance_from_price=distance_pct,
                last_updated=datetime.now(),
                cluster_id=cluster_id
            )
            
            clusters.append(cluster)
        
        return clusters
    
    def get_clusters(self, symbol: str) -> List[LiveCluster]:
        """
        Get current clusters for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of LiveCluster objects
        """
        # Update if needed
        if symbol not in self.last_update or \
           (datetime.now() - self.last_update.get(symbol, datetime.min)).total_seconds() >= self.update_interval:
            self._update_clusters(symbol)
        
        return self.clusters.get(symbol, [])
    
    def get_best_cluster(self, symbol: str, min_strength: float = 0.6) -> Optional[LiveCluster]:
        """
        Get best cluster for trading
        
        Args:
            symbol: Trading symbol
            min_strength: Minimum cluster strength
            
        Returns:
            Best LiveCluster or None
        """
        clusters = self.get_clusters(symbol)
        
        if not clusters:
            return None
        
        current_price = self.current_prices.get(symbol)
        if not current_price:
            return None
        
        # Filter by strength and tradability
        strong_clusters = [c for c in clusters if c.strength >= min_strength]
        
        if not strong_clusters:
            return None
        
        # Find cluster we can trade toward
        best_cluster = None
        best_score = 0
        
        for cluster in strong_clusters:
            can_trade = False
            if cluster.side == 'long' and current_price > cluster.price_level:
                can_trade = True  # Short toward long liquidations
            elif cluster.side == 'short' and current_price < cluster.price_level:
                can_trade = True  # Long toward short liquidations
            
            if not can_trade:
                continue
            
            ideal_distance = 0.035  # 3.5%
            distance_score = 1.0 - min(abs(cluster.distance_from_price / 100 - ideal_distance) / ideal_distance, 1.0)
            score = cluster.strength * 0.7 + distance_score * 0.3
            
            if score > best_score:
                best_score = score
                best_cluster = cluster
        
        return best_cluster


# Integration with liquidation hunter
class LiveLiquidationDataFetcher:
    """
    Adapter to use live heatmap with liquidation hunter
    """
    
    def __init__(self, heatmap: LiveLiquidationHeatmap):
        """
        Initialize fetcher
        
        Args:
            heatmap: LiveLiquidationHeatmap instance
        """
        self.heatmap = heatmap
    
    def fetch(self, symbol: str, current_price: float = None) -> List[Dict]:
        """
        Fetch liquidation data in format expected by liquidation hunter
        
        Args:
            symbol: Trading symbol
            current_price: Current price (updates heatmap)
            
        Returns:
            List of liquidation dicts
        """
        if current_price:
            self.heatmap.update_price(symbol, current_price)
        
        clusters = self.heatmap.get_clusters(symbol)
        
        # Convert clusters to liquidation data points
        liquidations = []
        for cluster in clusters:
            # Create representative data points
            count = min(cluster.liquidation_count, 20)  # Max 20 points per cluster
            avg_size = cluster.total_notional / cluster.liquidation_count if cluster.liquidation_count > 0 else 0
            
            for _ in range(count):
                liquidations.append({
                    'price': cluster.price_level,
                    'side': cluster.side,
                    'size': avg_size / cluster.price_level if cluster.price_level > 0 else 0,
                    'notional': avg_size
                })
        
        return liquidations


# Example usage
if __name__ == '__main__':
    print("=" * 70)
    print("LIVE LIQUIDATION HEATMAP FOR BINANCE FUTURES")
    print("=" * 70)
    print("\nBuilding real-time liquidation clusters from Binance WebSocket")
    print("\n" + "=" * 70)
    
    # Initialize heatmap
    heatmap = LiveLiquidationHeatmap(
        cluster_window_pct=0.02,
        min_cluster_size=5,
        time_decay_minutes=60,
        update_interval=5.0
    )
    
    # Symbols to monitor
    symbols = ['BTCUSDT', 'ETHUSDT']
    
    print(f"\nStarting live stream for: {', '.join(symbols)}")
    print("Connecting to Binance WebSocket...")
    
    # Start stream
    heatmap.start_stream(symbols=symbols)
    
    # Get current prices (you'd fetch this from Binance API)
    # For example:
    heatmap.update_price('BTCUSDT', 90000.0)
    heatmap.update_price('ETHUSDT', 3000.0)
    
    print("\nWaiting for liquidations...")
    print("Clusters will update every 5 seconds")
    print("\nPress Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(5)
            
            for symbol in symbols:
                clusters = heatmap.get_clusters(symbol)
                current_price = heatmap.current_prices.get(symbol)
                
                if clusters and current_price:
                    print(f"\n{symbol} @ ${current_price:,.2f}")
                    print(f"Found {len(clusters)} clusters:")
                    
                    for i, cluster in enumerate(clusters[:3], 1):  # Show top 3
                        print(f"  {i}. {cluster.side.upper()} @ ${cluster.price_level:,.2f} "
                              f"(strength: {cluster.strength:.2f}, "
                              f"count: {cluster.liquidation_count}, "
                              f"distance: {cluster.distance_from_price:.2f}%)")
                    
                    # Get best cluster for trading
                    best = heatmap.get_best_cluster(symbol, min_strength=0.6)
                    if best:
                        print(f"  → Best cluster: {best.side.upper()} @ ${best.price_level:,.2f}")
    
    except KeyboardInterrupt:
        print("\n\nStopping stream...")
        heatmap.stop_stream()
        print("Done!")
