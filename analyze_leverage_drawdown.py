#!/usr/bin/env python3
"""
Analyze leverage usage, drawdown calculation, and optimization opportunities
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path

# Load results
results_file = Path('research/backtest_all_memecoins_5m_20260126_221800.json')
with open(results_file, 'r') as f:
    results = json.load(f)

print("="*80)
print("LEVERAGE & DRAWDOWN ANALYSIS")
print("="*80)

# Remove summary
symbols = {k: v for k, v in results.items() if k != '_summary'}

print(f"\nTotal symbols: {len(symbols)}")
print(f"Current leverage: 20x (max)")

# Analyze trade patterns
print(f"\n{'='*80}")
print("TRADE PATTERN ANALYSIS")
print(f"{'='*80}")

high_return_symbols = []
for symbol, data in symbols.items():
    if data['total_return'] > 100:
        high_return_symbols.append((symbol, data))

print(f"\nSymbols with >100% return: {len(high_return_symbols)}")
for sym, data in sorted(high_return_symbols, key=lambda x: x[1]['total_return'], reverse=True)[:5]:
    print(f"\n{sym}:")
    print(f"  Return: {data['total_return']:.2f}%")
    print(f"  Trades: {data['total_trades']}")
    print(f"  Win Rate: {data['win_rate']*100:.1f}%")
    print(f"  Max Drawdown: {data['max_drawdown']:.2f}%")
    print(f"  Avg Win: ${data['avg_win']:.2f}")
    print(f"  Avg Loss: ${data['avg_loss']:.2f}")
    
    # Estimate actual leverage used
    if data['total_trades'] > 0 and data['avg_win'] > 0:
        # Rough estimate: if we made $12k on a $10k account with 20x leverage
        # and 25% position size, that's about 2.4% price move
        # P&L = notional * price_change * leverage
        # $12k = ($2.5k * 0.024) * leverage
        # leverage ≈ 200, which doesn't make sense...
        # Let me recalculate: with 20x leverage and 25% position:
        # notional = $10k * 0.25 * 20 = $50k
        # If price moves 2.4%, P&L = $50k * 0.024 = $1.2k
        # But we're seeing $12k wins, so either:
        # 1. Multiple trades compounding
        # 2. Larger position sizes
        # 3. Larger price moves
        
        # More likely: with 20x leverage, 25% position, a 5% move = $2.5k profit
        # To get $12k profit, need either:
        # - 4.8% move with larger position (unlikely)
        # - Multiple winning trades compounding
        
        print(f"  P&L per trade: ${data['total_pnl']/data['total_trades']:.2f}")

print(f"\n{'='*80}")
print("DRAWDOWN ANALYSIS")
print(f"{'='*80}")

print("\nWhy drawdown is low despite high returns:")
print("1. Very few trades (1-4 per symbol)")
print("2. Most winning trades exit quickly (take profit hit)")
print("3. Drawdown calculated on sparse equity curve")
print("4. With 20x leverage, small price moves = large returns")
print("5. Strategy exits on stop loss quickly, preventing large drawdowns")

# Calculate actual leverage impact
print(f"\n{'='*80}")
print("LEVERAGE IMPACT SIMULATION")
print(f"{'='*80}")

# Simulate: 20x leverage, 25% position, 2% price move
capital = 10000
position_pct = 0.25
leverage = 20
price_move = 0.02  # 2%

notional = capital * position_pct * leverage
pnl = notional * price_move

print(f"\nExample trade:")
print(f"  Capital: ${capital:,.2f}")
print(f"  Position size: {position_pct*100}%")
print(f"  Leverage: {leverage}x")
print(f"  Notional: ${notional:,.2f}")
print(f"  Price move: {price_move*100:.2f}%")
print(f"  P&L: ${pnl:,.2f} ({pnl/capital*100:.2f}% return)")

# With compounding
print(f"\nWith 2 winning trades (compounding):")
capital_after_1 = capital + pnl
notional_2 = capital_after_1 * position_pct * leverage
pnl_2 = notional_2 * price_move
total_return = ((capital + pnl + pnl_2) / capital - 1) * 100

print(f"  After trade 1: ${capital_after_1:,.2f}")
print(f"  Trade 2 P&L: ${pnl_2:,.2f}")
print(f"  Total return: {total_return:.2f}%")

print(f"\n{'='*80}")
print("OPTIMIZATION RECOMMENDATIONS")
print(f"{'='*80}")

print("\n1. INCREASE TRADE VOLUME:")
print("   - Lower momentum threshold: 0.005 → 0.003 (0.3%)")
print("   - Lower signal strength: 0.2 → 0.15")
print("   - Reduce volume multiplier: 1.1 → 1.05")
print("   - Make more filters optional (require 1 of 4 instead of 2 of 4)")

print("\n2. OPTIMIZE LEVERAGE:")
print("   - Use dynamic leverage based on signal strength:")
print("     * Strong signals (>0.7): 20x")
print("     * Medium signals (0.4-0.7): 15x")
print("     * Weak signals (0.2-0.4): 10x")
print("   - This increases volume while managing risk")

print("\n3. IMPROVE WIN RATE:")
print("   - Add trend confirmation (multiple timeframe)")
print("   - Tighter entry filters (but more frequent)")
print("   - Better exit timing (trailing stops)")

print("\n4. REALISTIC DRAWDOWN EXPECTATIONS:")
print("   - Current low drawdown is due to few trades")
print("   - With more trades, expect 5-10% drawdown")
print("   - This is still acceptable for 100%+ returns")

print("\n5. VOLUME FARMING OPTIMIZATION:")
print("   - Target: 200-500 trades/month across portfolio")
print("   - Current: ~42 trades in 6 days = ~210/month (good!)")
print("   - But need more consistent distribution")
print("   - Consider: Lower timeframe (3m) or more symbols")
