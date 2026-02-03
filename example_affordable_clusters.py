#!/usr/bin/env python3
"""
Example: Using Affordable Liquidation Clusters
Shows how to use Coinglass history ($29-$299/mo) instead of expensive heatmap models ($879/mo)
"""

from liquidation_cluster_builder import AffordableCoinglassFetcher, LiquidationClusterBuilder
from liquidation_hunter import LiquidationHunter
from datetime import datetime

def example_affordable_coinglass():
    """Example using affordable Coinglass history"""
    print("=" * 70)
    print("AFFORDABLE COINGLASS CLUSTERS")
    print("=" * 70)
    print("\nInstead of $879/mo Professional tier heatmap models,")
    print("we use $29-$299/mo liquidation history + build clusters!")
    print("\n" + "-" * 70)
    
    # Initialize affordable fetcher
    # Requires Coinglass API key from Hobbyist ($29/mo) or Startup ($79/mo) plan
    api_key = 'your_coinglass_api_key'  # Get from coinglass.com/pricing
    
    fetcher = AffordableCoinglassFetcher(api_key)
    
    symbol = 'BTCUSDT'
    current_price = 90000.0
    
    print(f"\nFetching clusters for {symbol} @ ${current_price:,.0f}")
    print("Using liquidation history (available in lower tiers)...")
    
    # Get clusters (built from history)
    clusters = fetcher.get_clusters(
        symbol=symbol,
        current_price=current_price,
        exchange='binance',
        hours=24  # Last 24 hours
    )
    
    print(f"\nFound {len(clusters)} clusters:")
    print("-" * 70)
    
    for i, cluster in enumerate(clusters[:5], 1):  # Show top 5
        print(f"\nCluster {i}:")
        print(f"  Price Level: ${cluster['price_level']:,.2f}")
        print(f"  Distance: {cluster['distance_from_price']:.2f}%")
        print(f"  Side: {cluster['side']} liquidations")
        print(f"  Count: {cluster['liquidation_count']}")
        print(f"  Total Notional: ${cluster['total_notional']:,.0f}")
        print(f"  Strength: {cluster['strength']:.2f}")
    
    return clusters

def example_free_exchange_api():
    """Example using free exchange APIs"""
    print("\n" + "=" * 70)
    print("FREE EXCHANGE API CLUSTERS")
    print("=" * 70)
    print("\nUsing Bybit WebSocket (100% free!)")
    print("-" * 70)
    
    from liquidation_data_sources import ExchangeLiquidationFetcher
    from liquidation_cluster_builder import LiquidationClusterBuilder
    
    # Initialize exchange fetcher (free)
    fetcher = ExchangeLiquidationFetcher('bybit')
    
    # Initialize cluster builder
    cluster_builder = LiquidationClusterBuilder()
    
    symbol = 'BTCUSDT'
    current_price = 90000.0
    
    print(f"\nFetching liquidations for {symbol}...")
    
    # Fetch liquidations (free)
    liquidations = fetcher.fetch_liquidations(symbol, limit=1000)
    
    print(f"Fetched {len(liquidations)} liquidations")
    
    if liquidations:
        # Build clusters from liquidations
        clusters = cluster_builder.build_clusters_from_history(
            liquidations, current_price, lookback_hours=24
        )
        
        print(f"\nBuilt {len(clusters)} clusters:")
        print("-" * 70)
        
        for i, cluster in enumerate(clusters[:5], 1):
            print(f"\nCluster {i}:")
            print(f"  Price Level: ${cluster['price_level']:,.2f}")
            print(f"  Side: {cluster['side']}")
            print(f"  Strength: {cluster['strength']:.2f}")
            print(f"  Count: {cluster['liquidation_count']}")
    
    return clusters if liquidations else []

def example_with_liquidation_hunter():
    """Example integrating with liquidation hunter"""
    print("\n" + "=" * 70)
    print("INTEGRATION WITH LIQUIDATION HUNTER")
    print("=" * 70)
    
    # Initialize hunter
    hunter = LiquidationHunter(
        initial_capital=10000.0,
        max_leverage=20.0,
        stop_loss_pct=0.03,
        take_profit_pct=0.05
    )
    
    # Option 1: Affordable Coinglass
    print("\nOption 1: Using affordable Coinglass ($29-$299/mo)")
    print("-" * 70)
    hunter.set_data_source(
        source='coinglass',
        coinglass_api_key='your_key'  # Hobbyist or Startup plan
    )
    
    symbol = 'BTC/USDT:USDT'
    current_price = 90000.0
    
    signal, strength, cluster = hunter.generate_signal(symbol, current_price)
    
    if signal != 0:
        print(f"\nSignal: {'LONG' if signal > 0 else 'SHORT'}")
        print(f"Strength: {strength:.2f}")
        if cluster:
            print(f"Target Cluster: ${cluster.price_level:,.2f}")
            print(f"Cluster Strength: {cluster.strength:.2f}")
    
    # Option 2: Free Exchange API
    print("\n" + "-" * 70)
    print("Option 2: Using free exchange API ($0/mo)")
    print("-" * 70)
    hunter.set_data_source(
        source='exchange',
        exchange_name='bybit'  # Free!
    )
    
    signal, strength, cluster = hunter.generate_signal(symbol, current_price)
    
    if signal != 0:
        print(f"\nSignal: {'LONG' if signal > 0 else 'SHORT'}")
        print(f"Strength: {strength:.2f}")
        if cluster:
            print(f"Target Cluster: ${cluster.price_level:,.2f}")

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("AFFORDABLE LIQUIDATION CLUSTER EXAMPLES")
    print("=" * 70)
    print("\nThese examples show how to get liquidation clusters")
    print("without paying $879/month for Professional tier!")
    print("\n" + "=" * 70)
    
    # Example 1: Affordable Coinglass (requires API key)
    # Uncomment when you have API key:
    # example_affordable_coinglass()
    
    # Example 2: Free exchange API
    example_free_exchange_api()
    
    # Example 3: Integration with hunter
    # Uncomment when you have API key:
    # example_with_liquidation_hunter()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\n✅ Affordable Option: Coinglass History ($29-$299/mo)")
    print("   - Builds clusters from liquidation history")
    print("   - Same result as $879/mo heatmap models!")
    print("\n✅ Free Option: Exchange APIs ($0/mo)")
    print("   - Bybit WebSocket (best free option)")
    print("   - OKX API (also free)")
    print("\n✅ Both work with liquidation hunter!")
    print("\nSee AFFORDABLE_LIQUIDATION_OPTIONS.md for full details")
