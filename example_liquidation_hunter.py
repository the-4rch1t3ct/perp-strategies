#!/usr/bin/env python3
"""
Example usage of Liquidation Hunter Agent
Demonstrates how to scan for clusters and generate signals
"""

from liquidation_hunter import LiquidationHunter, LiquidationCluster
from datetime import datetime
import pandas as pd
import numpy as np

def create_mock_liquidation_data(symbol: str, current_price: float, 
                                 num_liquidations: int = 200) -> list:
    """
    Create mock liquidation data for testing
    In production, replace with real API calls
    """
    liquidations = []
    
    # Simulate liquidations around certain price levels (clusters)
    cluster_levels = [
        current_price * 0.95,  # 5% below (long liquidations)
        current_price * 0.97,  # 3% below
        current_price * 1.03,  # 3% above (short liquidations)
        current_price * 1.05,  # 5% above
    ]
    
    for i in range(num_liquidations):
        # Randomly assign to a cluster
        cluster_price = np.random.choice(cluster_levels)
        
        # Add some noise around cluster
        noise = np.random.normal(0, cluster_price * 0.002)  # 0.2% noise
        price = cluster_price + noise
        
        # Determine side based on price relative to current
        if price < current_price:
            side = 'long'  # Longs get liquidated below price
        else:
            side = 'short'  # Shorts get liquidated above price
        
        # Random size
        size = np.random.uniform(1000, 50000)
        
        liquidations.append({
            'price': price,
            'side': side,
            'size': size,
            'notional': size * price,
            'timestamp': datetime.now()
        })
    
    return liquidations

def example_basic_usage():
    """Basic usage example"""
    print("=" * 70)
    print("LIQUIDATION HUNTER - Basic Usage Example")
    print("=" * 70)
    
    # Initialize hunter
    hunter = LiquidationHunter(
        initial_capital=10000.0,
        max_leverage=20.0,
        stop_loss_pct=0.03,
        take_profit_pct=0.05,
        min_cluster_strength=0.6,
        max_distance_pct=0.10
    )
    
    # Mock current price
    symbol = '1000000MOG/USDT:USDT'
    current_price = 0.00001234
    
    print(f"\nSymbol: {symbol}")
    print(f"Current Price: ${current_price:.8f}")
    
    # Generate mock liquidation data
    print("\nGenerating mock liquidation data...")
    liquidations = create_mock_liquidation_data(symbol, current_price, num_liquidations=200)
    print(f"Generated {len(liquidations)} liquidations")
    
    # Override fetch method for testing
    hunter.fetch_liquidation_data = lambda s, limit=1000: liquidations
    
    # Identify clusters
    print("\nIdentifying clusters...")
    clusters = hunter.identify_clusters(liquidations, current_price)
    
    print(f"\nFound {len(clusters)} clusters:")
    print("-" * 70)
    for i, cluster in enumerate(clusters[:5], 1):  # Show top 5
        print(f"\nCluster {i}:")
        print(f"  Price Level: ${cluster.price_level:.8f}")
        print(f"  Distance: {cluster.distance_from_price:.2f}%")
        print(f"  Side: {cluster.side} liquidations")
        print(f"  Count: {cluster.liquidation_count}")
        print(f"  Total Notional: ${cluster.total_notional:,.0f}")
        print(f"  Strength: {cluster.strength:.2f}")
    
    # Generate signal
    print("\n" + "=" * 70)
    print("Generating Trading Signal...")
    print("=" * 70)
    
    signal, strength, target_cluster = hunter.generate_signal(symbol, current_price)
    
    if signal == 0:
        print("\nNo signal generated (no strong clusters found)")
    else:
        side_str = "LONG" if signal > 0 else "SHORT"
        print(f"\nSignal: {side_str}")
        print(f"Strength: {strength:.2f}")
        if target_cluster:
            print(f"\nTarget Cluster:")
            print(f"  Price Level: ${target_cluster.price_level:.8f}")
            print(f"  Distance: {target_cluster.distance_from_price:.2f}%")
            print(f"  Side: {target_cluster.side} liquidations")
            print(f"  Strength: {target_cluster.strength:.2f}")
            
            # Calculate expected entry/exit
            if signal > 0:  # Long
                entry = current_price
                target = target_cluster.price_level
                profit_pct = ((target * 0.995 - entry) / entry) * 100
                print(f"\nExpected Entry: ${entry:.8f}")
                print(f"Expected Target: ${target * 0.995:.8f} (0.5% before cluster)")
                print(f"Expected Profit: {profit_pct:.2f}%")
            else:  # Short
                entry = current_price
                target = target_cluster.price_level
                profit_pct = ((entry - target * 1.005) / entry) * 100
                print(f"\nExpected Entry: ${entry:.8f}")
                print(f"Expected Target: ${target * 1.005:.8f} (0.5% before cluster)")
                print(f"Expected Profit: {profit_pct:.2f}%")

def example_position_management():
    """Example of position management"""
    print("\n" + "=" * 70)
    print("POSITION MANAGEMENT EXAMPLE")
    print("=" * 70)
    
    hunter = LiquidationHunter(
        initial_capital=10000.0,
        max_leverage=20.0,
        stop_loss_pct=0.03,
        take_profit_pct=0.05
    )
    
    symbol = 'MEME/USDT:USDT'
    current_price = 0.025
    
    # Generate mock data
    liquidations = create_mock_liquidation_data(symbol, current_price)
    hunter.fetch_liquidation_data = lambda s, limit=1000: liquidations
    
    # Generate signal and enter
    signal, strength, cluster = hunter.generate_signal(symbol, current_price)
    
    if signal != 0 and cluster:
        print(f"\nEntering {('LONG' if signal > 0 else 'SHORT')} position...")
        position = hunter.enter_position(
            symbol=symbol,
            signal=signal,
            price=current_price,
            time=datetime.now(),
            cluster=cluster
        )
        
        if position:
            print(f"\nPosition Opened:")
            print(f"  Side: {position.side}")
            print(f"  Entry: ${position.entry_price:.6f}")
            print(f"  Size: {position.size:.2f}")
            print(f"  Stop Loss: ${position.stop_loss:.6f}")
            print(f"  Take Profit: ${position.take_profit:.6f}")
            print(f"  Target Cluster: ${position.target_cluster.price_level:.6f}")
            
            # Simulate price movement
            print("\nSimulating price movement...")
            if position.side == 'long':
                # Price moves up toward cluster
                prices = np.linspace(current_price, cluster.price_level * 0.995, 10)
            else:
                # Price moves down toward cluster
                prices = np.linspace(current_price, cluster.price_level * 1.005, 10)
            
            for i, price in enumerate(prices):
                closed = hunter.check_positions(
                    {symbol: price},
                    datetime.now()
                )
                
                if closed:
                    trade = closed[0]
                    print(f"\nPosition Closed:")
                    print(f"  Exit Price: ${trade.exit_price:.6f}")
                    print(f"  Reason: {trade.reason}")
                    print(f"  P&L: ${trade.pnl:.2f} ({trade.pnl_pct:.2f}%)")
                    print(f"  Cluster Target: ${trade.cluster_target:.6f}")
                    break
                
                if i == len(prices) - 1:
                    print(f"  Price: ${price:.6f} (still open)")
            
            # Get status
            status = hunter.get_status()
            print(f"\nFinal Status:")
            print(f"  Capital: ${status['capital']:.2f}")
            print(f"  Total P&L: ${status['total_pnl']:.2f} ({status['total_pnl_pct']:.2f}%)")
            print(f"  Closed Trades: {status['closed_trades']}")

if __name__ == '__main__':
    example_basic_usage()
    example_position_management()
    
    print("\n" + "=" * 70)
    print("Example Complete!")
    print("=" * 70)
    print("\nNext Steps:")
    print("1. Set up real liquidation data source (exchange API)")
    print("2. Test with paper trading")
    print("3. Optimize parameters (min_cluster_strength, max_distance_pct)")
    print("4. Deploy to PriveX")
    print("\nSee LIQUIDATION_HUNTER_GUIDE.md for full documentation")
