#!/usr/bin/env python3
"""
Example: Live Liquidation Heatmap Integration
Shows how to use live Binance liquidation stream with liquidation hunter
"""

import time
from live_liquidation_heatmap import LiveLiquidationHeatmap
from liquidation_hunter import LiquidationHunter
from datetime import datetime

def example_live_heatmap_standalone():
    """Example using live heatmap standalone"""
    print("=" * 70)
    print("LIVE LIQUIDATION HEATMAP - STANDALONE")
    print("=" * 70)
    
    # Initialize heatmap
    heatmap = LiveLiquidationHeatmap(
        cluster_window_pct=0.02,  # 2% clustering window
        min_cluster_size=5,  # Minimum 5 liquidations per cluster
        time_decay_minutes=60,  # 60-minute time decay
        update_interval=5.0  # Update clusters every 5 seconds
    )
    
    # Symbols to monitor
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    
    print(f"\nStarting live stream for: {', '.join(symbols)}")
    print("Connecting to Binance WebSocket...")
    
    # Start stream
    heatmap.start_stream(symbols=symbols)
    
    # Set current prices (you'd fetch these from Binance API in production)
    heatmap.update_price('BTCUSDT', 90000.0)
    heatmap.update_price('ETHUSDT', 3000.0)
    heatmap.update_price('SOLUSDT', 150.0)
    
    print("\nWaiting for liquidations...")
    print("Clusters update every 5 seconds")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        for i in range(12):  # Run for 1 minute (12 * 5 seconds)
            time.sleep(5)
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Update {i+1}")
            print("-" * 70)
            
            for symbol in symbols:
                clusters = heatmap.get_clusters(symbol)
                current_price = heatmap.current_prices.get(symbol)
                
                if clusters and current_price:
                    print(f"\n{symbol} @ ${current_price:,.2f}")
                    print(f"  Found {len(clusters)} clusters:")
                    
                    for j, cluster in enumerate(clusters[:3], 1):  # Show top 3
                        print(f"    {j}. {cluster.side.upper()} @ ${cluster.price_level:,.2f}")
                        print(f"       Strength: {cluster.strength:.2f} | "
                              f"Count: {cluster.liquidation_count} | "
                              f"Distance: {cluster.distance_from_price:.2f}%")
                    
                    # Get best cluster for trading
                    best = heatmap.get_best_cluster(symbol, min_strength=0.6)
                    if best:
                        print(f"  → Best trading cluster: {best.side.upper()} @ ${best.price_level:,.2f}")
                        print(f"     Strength: {best.strength:.2f} | "
                              f"Total Notional: ${best.total_notional:,.0f}")
                else:
                    print(f"\n{symbol}: No clusters yet (waiting for liquidations...)")
        
        print("\n" + "=" * 70)
        print("Stopping stream...")
        heatmap.stop_stream()
        
    except KeyboardInterrupt:
        print("\n\nStopping stream...")
        heatmap.stop_stream()
        print("Done!")

def example_live_heatmap_with_hunter():
    """Example integrating live heatmap with liquidation hunter"""
    print("\n" + "=" * 70)
    print("LIVE HEATMAP + LIQUIDATION HUNTER")
    print("=" * 70)
    
    # Initialize liquidation hunter
    hunter = LiquidationHunter(
        initial_capital=10000.0,
        max_leverage=20.0,
        stop_loss_pct=0.03,
        take_profit_pct=0.05,
        min_cluster_strength=0.6
    )
    
    # Set up live Binance heatmap as data source
    symbols = ['BTCUSDT', 'ETHUSDT']
    
    print(f"\nSetting up live Binance heatmap for: {', '.join(symbols)}")
    
    hunter.set_data_source(
        source='live_binance',
        symbols=symbols  # Symbols to monitor
    )
    
    print("Live stream started!")
    print("\nWaiting for liquidations to build clusters...")
    print("Then generating trading signals...\n")
    
    # Set current prices
    current_prices = {
        'BTCUSDT': 90000.0,
        'ETHUSDT': 3000.0
    }
    
    try:
        for i in range(12):  # Run for 1 minute
            time.sleep(5)
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Update {i+1}")
            print("-" * 70)
            
            for symbol_ccxt in ['BTC/USDT:USDT', 'ETH/USDT:USDT']:
                # Normalize symbol
                symbol_normalized = symbol_ccxt.replace('/USDT:USDT', '').replace('/', '').upper()
                current_price = current_prices.get(symbol_normalized)
                
                if not current_price:
                    continue
                
                # Generate signal using live clusters
                signal, strength, cluster = hunter.generate_signal(symbol_ccxt, current_price)
                
                if signal != 0:
                    side_str = "LONG" if signal > 0 else "SHORT"
                    print(f"\n{symbol_ccxt} @ ${current_price:,.2f}")
                    print(f"  Signal: {side_str}")
                    print(f"  Strength: {strength:.2f}")
                    
                    if cluster:
                        print(f"  Target Cluster: ${cluster.price_level:,.2f}")
                        print(f"  Cluster Strength: {cluster.strength:.2f}")
                        print(f"  Distance: {cluster.distance_from_price:.2f}%")
                        print(f"  Side: {cluster.side.upper()} liquidations")
                else:
                    print(f"\n{symbol_ccxt}: No signal (waiting for strong clusters...)")
        
        print("\n" + "=" * 70)
        print("Stopping...")
        if hasattr(hunter, 'live_heatmap') and hunter.live_heatmap:
            hunter.live_heatmap.stop_stream()
        
    except KeyboardInterrupt:
        print("\n\nStopping...")
        if hasattr(hunter, 'live_heatmap') and hunter.live_heatmap:
            hunter.live_heatmap.stop_stream()

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("LIVE LIQUIDATION HEATMAP EXAMPLES")
    print("=" * 70)
    print("\nBuilding real-time liquidation clusters from Binance WebSocket")
    print("No API keys needed - uses public WebSocket stream!")
    print("\n" + "=" * 70)
    
    # Example 1: Standalone heatmap
    example_live_heatmap_standalone()
    
    # Example 2: With liquidation hunter
    # Uncomment to run:
    # example_live_heatmap_with_hunter()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\n✅ Live Binance liquidation stream (100% free)")
    print("✅ Real-time cluster building")
    print("✅ Works with liquidation hunter")
    print("✅ No API keys needed")
    print("\nSee live_liquidation_heatmap.py for full implementation")
