#!/usr/bin/env python3
"""
Liquidation Data Sources Module
Supports multiple sources for liquidation heatmap data:
1. Coinglass API (best quality, paid)
2. Exchange APIs (Binance, Bybit via CCXT)
3. WebSocket streams (Bybit)
4. Order book estimation (fallback)
"""

import requests
import ccxt
import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class LiquidationDataPoint:
    """Single liquidation data point"""
    price: float
    side: str  # 'long' or 'short'
    size: float  # Position size
    notional: float  # USD value
    timestamp: datetime
    exchange: str = 'unknown'

class CoinglassLiquidationFetcher:
    """
    Fetches liquidation heatmap data from Coinglass API
    NOTE: Heatmap models require Professional tier ($879/mo)
    Use AffordableCoinglassFetcher for lower tiers ($29-$299/mo)
    """
    
    BASE_URL = "https://open-api.coinglass.com"
    
    def __init__(self, api_key: str):
        """
        Initialize Coinglass fetcher
        
        Args:
            api_key: Coinglass API key (get from coinglass.com/pricing)
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'coinglassSecret': api_key,
            'Content-Type': 'application/json'
        })
    
    def fetch_heatmap(self, symbol: str, exchange: str = 'binance') -> List[LiquidationDataPoint]:
        """
        Fetch liquidation heatmap data
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            exchange: Exchange name ('binance', 'bybit', etc.)
            
        Returns:
            List of LiquidationDataPoint objects
        """
        try:
            # Coinglass API endpoint for liquidation heatmap
            # Model 1: Pair liquidation heatmap on chart
            url = f"{self.BASE_URL}/api/futures/liquidation/heatmap/model1"
            
            params = {
                'symbol': symbol,
                'exchange': exchange,
                'timeType': '1'  # 1=1h, 2=4h, 3=1d
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse Coinglass response format
            # Format varies - check docs.coinglass.com for exact structure
            liquidations = []
            
            if 'data' in data:
                heatmap_data = data['data']
                
                # Coinglass returns price levels with liquidation volumes
                # Structure: [{'price': float, 'longLiquidation': float, 'shortLiquidation': float}, ...]
                if isinstance(heatmap_data, list):
                    for item in heatmap_data:
                        price = item.get('price', 0)
                        
                        # Long liquidations (price below current = longs get liquidated)
                        long_liq = item.get('longLiquidation', 0) or item.get('long', 0)
                        if long_liq > 0:
                            liquidations.append(LiquidationDataPoint(
                                price=price,
                                side='long',
                                size=long_liq,
                                notional=long_liq * price,
                                timestamp=datetime.now(),
                                exchange=exchange
                            ))
                        
                        # Short liquidations (price above current = shorts get liquidated)
                        short_liq = item.get('shortLiquidation', 0) or item.get('short', 0)
                        if short_liq > 0:
                            liquidations.append(LiquidationDataPoint(
                                price=price,
                                side='short',
                                size=short_liq,
                                notional=short_liq * price,
                                timestamp=datetime.now(),
                                exchange=exchange
                            ))
            
            return liquidations
            
        except Exception as e:
            print(f"Error fetching Coinglass data: {e}")
            return []
    
    def fetch_liquidation_history(self, symbol: str, exchange: str = 'binance',
                                 hours: int = 24) -> List[LiquidationDataPoint]:
        """
        Fetch historical liquidation data
        
        Args:
            symbol: Trading pair
            exchange: Exchange name
            hours: Number of hours of history
            
        Returns:
            List of LiquidationDataPoint objects
        """
        try:
            url = f"{self.BASE_URL}/api/futures/liquidation/history"
            
            params = {
                'symbol': symbol,
                'exchange': exchange,
                'timeType': '1',  # 1h intervals
                'limit': hours
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            liquidations = []
            
            if 'data' in data and isinstance(data['data'], list):
                for item in data['data']:
                    price = item.get('price', 0)
                    side = 'long' if item.get('side', '').lower() == 'buy' else 'short'
                    size = item.get('size', 0) or item.get('qty', 0)
                    
                    if price > 0 and size > 0:
                        liquidations.append(LiquidationDataPoint(
                            price=price,
                            side=side,
                            size=size,
                            notional=size * price,
                            timestamp=datetime.fromtimestamp(item.get('time', 0) / 1000),
                            exchange=exchange
                        ))
            
            return liquidations
            
        except Exception as e:
            print(f"Error fetching Coinglass history: {e}")
            return []

class ExchangeLiquidationFetcher:
    """
    Fetches liquidation data directly from exchanges via CCXT
    Supports: Binance, Bybit, OKX, BitMEX
    """
    
    def __init__(self, exchange_name: str = 'binance', api_key: str = None,
                 api_secret: str = None):
        """
        Initialize exchange fetcher
        
        Args:
            exchange_name: Exchange name ('binance', 'bybit', etc.)
            api_key: Optional API key
            api_secret: Optional API secret
        """
        exchange_class = getattr(ccxt, exchange_name)
        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        }
        if api_key and api_secret:
            config['apiKey'] = api_key
            config['secret'] = api_secret
        
        self.exchange = exchange_class(config)
        self.exchange_name = exchange_name
    
    def fetch_liquidations(self, symbol: str, limit: int = 1000) -> List[LiquidationDataPoint]:
        """
        Fetch recent liquidations from exchange
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT:USDT')
            limit: Maximum number of liquidations
            
        Returns:
            List of LiquidationDataPoint objects
        """
        liquidations = []
        
        try:
            # Try CCXT fetch_liquidations method
            if hasattr(self.exchange, 'fetch_liquidations'):
                raw_data = self.exchange.fetch_liquidations(symbol, limit=limit)
                
                for item in raw_data:
                    price = item.get('price', 0)
                    side = item.get('side', 'long')
                    size = item.get('amount', 0) or item.get('size', 0)
                    
                    # Normalize side
                    if isinstance(side, str):
                        side = 'long' if side.lower() in ['buy', 'long'] else 'short'
                    else:
                        side = 'long' if side == 1 else 'short'
                    
                    if price > 0 and size > 0:
                        liquidations.append(LiquidationDataPoint(
                            price=price,
                            side=side,
                            size=size,
                            notional=size * price,
                            timestamp=datetime.fromtimestamp(item.get('timestamp', 0) / 1000),
                            exchange=self.exchange_name
                        ))
            
        except Exception as e:
            print(f"Error fetching liquidations from {self.exchange_name}: {e}")
        
        return liquidations
    
    async def watch_liquidations_websocket(self, symbol: str,
                                          callback) -> None:
        """
        Watch liquidations via WebSocket (Bybit, OKX support this)
        
        Args:
            symbol: Trading pair
            callback: Function to call with each liquidation
        """
        try:
            if hasattr(self.exchange, 'watch_liquidations'):
                async for liquidation in self.exchange.watch_liquidations(symbol):
                    price = liquidation.get('price', 0)
                    side = liquidation.get('side', 'long')
                    size = liquidation.get('amount', 0)
                    
                    data_point = LiquidationDataPoint(
                        price=price,
                        side=side,
                        size=size,
                        notional=size * price,
                        timestamp=datetime.now(),
                        exchange=self.exchange_name
                    )
                    
                    callback(data_point)
        except Exception as e:
            print(f"Error watching liquidations: {e}")

class OrderBookLiquidationEstimator:
    """
    Estimates liquidation levels from order book depth
    Fallback method when liquidation APIs aren't available
    """
    
    def __init__(self, exchange_name: str = 'binance', api_key: str = None,
                 api_secret: str = None):
        """Initialize order book estimator"""
        exchange_class = getattr(ccxt, exchange_name)
        config = {'enableRateLimit': True}
        if api_key and api_secret:
            config['apiKey'] = api_key
            config['secret'] = api_secret
        
        self.exchange = exchange_class(config)
        self.exchange_name = exchange_name
    
    def estimate_liquidations(self, symbol: str, current_price: float,
                             leverage_range: Tuple[float, float] = (5.0, 20.0),
                             price_range_pct: float = 0.10) -> List[LiquidationDataPoint]:
        """
        Estimate liquidation levels from order book
        
        Args:
            symbol: Trading pair
            current_price: Current market price
            leverage_range: Range of leverage to consider (min, max)
            price_range_pct: Price range to analyze (%)
            
        Returns:
            List of estimated LiquidationDataPoint objects
        """
        liquidations = []
        
        try:
            # Fetch order book
            orderbook = self.exchange.fetch_order_book(symbol, limit=100)
            
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            # Analyze order book depth
            # Large orders at certain levels might indicate stop-loss clusters
            
            # Check bids (potential long liquidation levels)
            for price, size in bids:
                price_diff_pct = abs((price - current_price) / current_price)
                
                if price_diff_pct <= price_range_pct and size > 0:
                    # Estimate: large orders below price = potential long liquidations
                    # (if price falls, longs get liquidated)
                    estimated_size = size * 0.1  # Conservative estimate
                    
                    liquidations.append(LiquidationDataPoint(
                        price=price,
                        side='long',
                        size=estimated_size,
                        notional=estimated_size * price,
                        timestamp=datetime.now(),
                        exchange=self.exchange_name
                    ))
            
            # Check asks (potential short liquidation levels)
            for price, size in asks:
                price_diff_pct = abs((price - current_price) / current_price)
                
                if price_diff_pct <= price_range_pct and size > 0:
                    # Large orders above price = potential short liquidations
                    estimated_size = size * 0.1
                    
                    liquidations.append(LiquidationDataPoint(
                        price=price,
                        side='short',
                        size=estimated_size,
                        notional=estimated_size * price,
                        timestamp=datetime.now(),
                        exchange=self.exchange_name
                    ))
        
        except Exception as e:
            print(f"Error estimating liquidations from order book: {e}")
        
        return liquidations

# Import affordable fetcher
try:
    from liquidation_cluster_builder import AffordableCoinglassFetcher
except ImportError:
    AffordableCoinglassFetcher = None

class LiquidationDataAggregator:
    """
    Aggregates liquidation data from multiple sources
    Provides unified interface for liquidation hunter
    """
    
    def __init__(self, source: str = 'coinglass', **kwargs):
        """
        Initialize aggregator
        
        Args:
            source: Data source ('coinglass', 'exchange', 'orderbook', 'auto')
            **kwargs: Source-specific config (api_key, exchange_name, etc.)
        """
        self.source = source
        self.fetchers = {}
        
        # Initialize fetchers based on source
        if source == 'coinglass' or source == 'auto':
            if 'coinglass_api_key' in kwargs:
                # Use affordable fetcher (builds clusters from history)
                # Instead of expensive heatmap models
                if AffordableCoinglassFetcher:
                    self.fetchers['coinglass'] = AffordableCoinglassFetcher(
                        kwargs['coinglass_api_key']
                    )
                else:
                    # Fallback to regular fetcher (requires Professional tier)
                    self.fetchers['coinglass'] = CoinglassLiquidationFetcher(
                        kwargs['coinglass_api_key']
                    )
        
        if source == 'exchange' or source == 'auto':
            exchange_name = kwargs.get('exchange_name', 'binance')
            self.fetchers['exchange'] = ExchangeLiquidationFetcher(
                exchange_name=exchange_name,
                api_key=kwargs.get('api_key'),
                api_secret=kwargs.get('api_secret')
            )
        
        if source == 'orderbook' or source == 'auto':
            exchange_name = kwargs.get('exchange_name', 'binance')
            self.fetchers['orderbook'] = OrderBookLiquidationEstimator(
                exchange_name=exchange_name,
                api_key=kwargs.get('api_key'),
                api_secret=kwargs.get('api_secret')
            )
    
    def fetch(self, symbol: str, current_price: float = None) -> List[Dict]:
        """
        Fetch liquidation data from configured sources
        
        Args:
            symbol: Trading pair
            current_price: Current price (for orderbook estimation)
            
        Returns:
            List of liquidation dicts compatible with liquidation_hunter
        """
        all_liquidations = []
        
        # Try sources in priority order
        if 'coinglass' in self.fetchers:
            try:
                fetcher = self.fetchers['coinglass']
                
                # Check if it's the affordable fetcher (has get_clusters method)
                if hasattr(fetcher, 'get_clusters') and current_price:
                    # Use affordable method: build clusters from history
                    clusters = fetcher.get_clusters(symbol, current_price)
                    
                    # Convert clusters to liquidation data points
                    for cluster in clusters:
                        # Create multiple data points to represent cluster
                        price = cluster['price_level']
                        count = cluster['liquidation_count']
                        side = cluster['side']
                        avg_size = cluster.get('avg_size', cluster['total_notional'] / count if count > 0 else 0)
                        
                        # Create representative data points
                        for _ in range(min(count, 10)):  # Max 10 points per cluster
                            all_liquidations.append({
                                'price': price,
                                'side': side,
                                'size': avg_size,
                                'notional': avg_size * price
                            })
                elif hasattr(fetcher, 'fetch_heatmap'):
                    # Professional tier heatmap (expensive)
                    data_points = fetcher.fetch_heatmap(symbol)
                    all_liquidations.extend([{
                        'price': dp.price,
                        'side': dp.side,
                        'size': dp.size,
                        'notional': dp.notional
                    } for dp in data_points])
                
                if all_liquidations:
                    return all_liquidations
            except Exception as e:
                print(f"Coinglass fetch failed: {e}")
        
        if 'exchange' in self.fetchers:
            try:
                data_points = self.fetchers['exchange'].fetch_liquidations(symbol)
                all_liquidations.extend([{
                    'price': dp.price,
                    'side': dp.side,
                    'size': dp.size,
                    'notional': dp.notional
                } for dp in data_points])
                
                if all_liquidations:
                    return all_liquidations
            except Exception as e:
                print(f"Exchange fetch failed: {e}")
        
        if 'orderbook' in self.fetchers and current_price:
            try:
                data_points = self.fetchers['orderbook'].estimate_liquidations(
                    symbol, current_price
                )
                all_liquidations.extend([{
                    'price': dp.price,
                    'side': dp.side,
                    'size': dp.size,
                    'notional': dp.notional
                } for dp in data_points])
            except Exception as e:
                print(f"Orderbook estimation failed: {e}")
        
        return all_liquidations


# Example usage
if __name__ == '__main__':
    print("=" * 70)
    print("LIQUIDATION DATA SOURCES")
    print("=" * 70)
    
    print("\n1. Coinglass API (Best Quality - Paid)")
    print("   - Cost: $35/month+")
    print("   - Quality: Excellent")
    print("   - Coverage: All major exchanges")
    print("   - API Docs: docs.coinglass.com")
    
    print("\n2. Exchange APIs (Free)")
    print("   - Binance: Limited liquidation data")
    print("   - Bybit: WebSocket liquidation stream")
    print("   - OKX: Good liquidation API")
    print("   - Via CCXT library")
    
    print("\n3. Order Book Estimation (Free Fallback)")
    print("   - Estimates from order book depth")
    print("   - Less accurate but always available")
    print("   - Good for testing")
    
    print("\n" + "=" * 70)
    print("RECOMMENDED SETUP")
    print("=" * 70)
    print("\nFor Production:")
    print("  • Use Coinglass API ($35/month) - best data quality")
    print("  • Fallback to exchange APIs if Coinglass fails")
    print("\nFor Testing:")
    print("  • Use exchange APIs (free)")
    print("  • Or order book estimation (free)")
    print("\nSee LIQUIDATION_DATA_SOURCES_GUIDE.md for integration details")
