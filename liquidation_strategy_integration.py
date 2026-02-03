#!/usr/bin/env python3
"""
Liquidation Strategy Integration
Example integration of liquidation heatmap data with trading agent
"""

import httpx
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TradingSignal:
    """Trading signal based on liquidation clusters"""
    symbol: str
    signal: str  # "LONG", "SHORT", "NEUTRAL"
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.0
    risk_reward: Optional[float] = None
    reason: str = ""
    cluster_data: Optional[Dict] = None

class LiquidationStrategy:
    """
    Trading strategy based on liquidation cluster data
    """
    
    def __init__(self, api_base: str = "https://api.wagmi-global.eu"):
        self.api_base = api_base
        self.client = httpx.Client(timeout=10)
    
    def get_clusters(self, symbol: str, min_strength: float = 0.5, max_distance: float = 5.0) -> Dict:
        """Fetch liquidation clusters for a symbol"""
        try:
            response = self.client.get(
                f"{self.api_base}/api/heatmap/{symbol}",
                params={
                    "min_strength": min_strength,
                    "max_distance": max_distance
                }
            )
            return response.json()
        except Exception as e:
            print(f"Error fetching clusters: {e}")
            return {"success": False, "clusters": []}
    
    def get_best_cluster(self, symbol: str, min_strength: float = 0.6) -> Optional[Dict]:
        """Get the strongest trading cluster"""
        try:
            response = self.client.get(
                f"{self.api_base}/api/heatmap/{symbol}/best",
                params={"min_strength": min_strength}
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching best cluster: {e}")
        return None
    
    def analyze_clusters(self, symbol: str) -> TradingSignal:
        """
        Analyze clusters and generate trading signal
        
        Strategy Logic:
        1. Find strongest clusters near current price
        2. Long clusters below = support (enter LONG)
        3. Short clusters above = resistance (enter SHORT)
        4. Calculate risk/reward based on cluster distances
        """
        data = self.get_clusters(symbol, min_strength=0.4, max_distance=5.0)
        
        if not data.get('success') or not data.get('clusters'):
            return TradingSignal(
                symbol=symbol,
                signal="NEUTRAL",
                entry_price=0.0,
                reason="No clusters found"
            )
        
        current_price = data['current_price']
        clusters = data['clusters']
        
        # Separate by side and position relative to price
        long_clusters_below = [
            c for c in clusters 
            if c['side'] == 'long' and c['price_level'] < current_price
        ]
        short_clusters_above = [
            c for c in clusters 
            if c['side'] == 'short' and c['price_level'] > current_price
        ]
        
        # Sort by strength
        long_clusters_below.sort(key=lambda x: x['strength'], reverse=True)
        short_clusters_above.sort(key=lambda x: x['strength'], reverse=True)
        
        # Strategy 1: Trade towards strong clusters (liquidation hunt)
        if short_clusters_above and short_clusters_above[0]['strength'] >= 0.6:
            strongest_short = short_clusters_above[0]
            distance = strongest_short['distance_from_price']
            
            if distance < 2.0:  # Within 2% - good entry
                # Enter LONG, target the short liquidation cluster
                entry = current_price
                stop_loss = current_price * 0.98  # 2% stop
                take_profit = strongest_short['price_level'] * 1.005  # Just above cluster
                
                risk = entry - stop_loss
                reward = take_profit - entry
                risk_reward = reward / risk if risk > 0 else 0
                
                return TradingSignal(
                    symbol=symbol,
                    signal="LONG",
                    entry_price=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=strongest_short['strength'],
                    risk_reward=risk_reward,
                    reason=f"Strong short liquidation cluster at ${strongest_short['price_level']:.2f} "
                           f"(strength: {strongest_short['strength']:.2f}, "
                           f"OI: ${strongest_short['total_notional']:,.0f})",
                    cluster_data=strongest_short
                )
        
        if long_clusters_below and long_clusters_below[0]['strength'] >= 0.6:
            strongest_long = long_clusters_below[0]
            distance = strongest_long['distance_from_price']
            
            if distance < 2.0:  # Within 2% - good entry
                # Enter SHORT, target the long liquidation cluster
                entry = current_price
                stop_loss = current_price * 1.02  # 2% stop
                take_profit = strongest_long['price_level'] * 0.995  # Just below cluster
                
                risk = stop_loss - entry
                reward = entry - take_profit
                risk_reward = reward / risk if risk > 0 else 0
                
                return TradingSignal(
                    symbol=symbol,
                    signal="SHORT",
                    entry_price=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=strongest_long['strength'],
                    risk_reward=risk_reward,
                    reason=f"Strong long liquidation cluster at ${strongest_long['price_level']:.2f} "
                           f"(strength: {strongest_long['strength']:.2f}, "
                           f"OI: ${strongest_long['total_notional']:,.0f})",
                    cluster_data=strongest_long
                )
        
        # Strategy 2: Support/Resistance bounce
        if long_clusters_below:
            nearest_support = max(long_clusters_below, key=lambda x: x['price_level'])
            if nearest_support['strength'] >= 0.5:
                # Price near support, potential bounce
                distance_pct = ((current_price - nearest_support['price_level']) / current_price) * 100
                if distance_pct < 0.5:  # Within 0.5% of support
                    return TradingSignal(
                        symbol=symbol,
                        signal="LONG",
                        entry_price=current_price,
                        stop_loss=nearest_support['price_level'] * 0.998,
                        take_profit=current_price * 1.02,
                        confidence=nearest_support['strength'] * 0.8,
                        reason=f"Bounce from support cluster at ${nearest_support['price_level']:.2f}",
                        cluster_data=nearest_support
                    )
        
        if short_clusters_above:
            nearest_resistance = min(short_clusters_above, key=lambda x: x['price_level'])
            if nearest_resistance['strength'] >= 0.5:
                # Price near resistance, potential rejection
                distance_pct = ((nearest_resistance['price_level'] - current_price) / current_price) * 100
                if distance_pct < 0.5:  # Within 0.5% of resistance
                    return TradingSignal(
                        symbol=symbol,
                        signal="SHORT",
                        entry_price=current_price,
                        stop_loss=nearest_resistance['price_level'] * 1.002,
                        take_profit=current_price * 0.98,
                        confidence=nearest_resistance['strength'] * 0.8,
                        reason=f"Rejection from resistance cluster at ${nearest_resistance['price_level']:.2f}",
                        cluster_data=nearest_resistance
                    )
        
        return TradingSignal(
            symbol=symbol,
            signal="NEUTRAL",
            entry_price=current_price,
            reason="No strong trading opportunities found"
        )
    
    def get_support_resistance_levels(self, symbol: str) -> Dict:
        """Get key support and resistance levels"""
        data = self.get_clusters(symbol, min_strength=0.3, max_distance=10.0)
        
        if not data.get('success'):
            return {"support": [], "resistance": [], "current_price": 0}
        
        current_price = data['current_price']
        clusters = data['clusters']
        
        # Support levels (long clusters below price, sorted by price descending)
        support = sorted(
            [c for c in clusters if c['side'] == 'long' and c['price_level'] < current_price],
            key=lambda x: x['price_level'],
            reverse=True
        )[:5]  # Top 5 support levels
        
        # Resistance levels (short clusters above price, sorted by price ascending)
        resistance = sorted(
            [c for c in clusters if c['side'] == 'short' and c['price_level'] > current_price],
            key=lambda x: x['price_level']
        )[:5]  # Top 5 resistance levels
        
        return {
            "support": [
                {
                    "price": c['price_level'],
                    "strength": c['strength'],
                    "oi": c['total_notional']
                } for c in support
            ],
            "resistance": [
                {
                    "price": c['price_level'],
                    "strength": c['strength'],
                    "oi": c['total_notional']
                } for c in resistance
            ],
            "current_price": current_price
        }
    
    def get_market_sentiment(self, symbol: str) -> Dict:
        """Analyze market sentiment from OI data"""
        try:
            response = self.client.get(f"{self.api_base}/api/stats")
            stats = response.json()
            
            oi_summary = stats.get('stats', {}).get('debug', {}).get('open_interest_summary', {})
            
            if symbol in oi_summary:
                oi_data = oi_summary[symbol]
                long_short_ratio = oi_data.get('long_short_ratio', 1.0)
                total_oi = oi_data.get('total_oi_usd', 0)
                
                # Determine sentiment
                if long_short_ratio > 1.2:
                    sentiment = "BULLISH_BIAS"  # More longs = bullish
                    bias_strength = "HIGH" if long_short_ratio > 1.5 else "MODERATE"
                elif long_short_ratio < 0.8:
                    sentiment = "BEARISH_BIAS"  # More shorts = bearish
                    bias_strength = "HIGH" if long_short_ratio < 0.67 else "MODERATE"
                else:
                    sentiment = "NEUTRAL"
                    bias_strength = "LOW"
                
                return {
                    "sentiment": sentiment,
                    "bias_strength": bias_strength,
                    "long_short_ratio": long_short_ratio,
                    "total_oi_usd": total_oi,
                    "interpretation": self._interpret_sentiment(sentiment, long_short_ratio)
                }
        except Exception as e:
            print(f"Error getting market sentiment: {e}")
        
        return {"sentiment": "UNKNOWN", "bias_strength": "UNKNOWN"}
    
    def _interpret_sentiment(self, sentiment: str, ratio: float) -> str:
        """Interpret sentiment for trading"""
        if sentiment == "BULLISH_BIAS":
            return f"More long positions ({ratio:.2f}:1) - Short liquidations more likely on price rise"
        elif sentiment == "BEARISH_BIAS":
            return f"More short positions ({1/ratio:.2f}:1) - Long liquidations more likely on price fall"
        else:
            return "Balanced long/short ratio - No clear bias"
    
    def generate_trading_plan(self, symbol: str) -> Dict:
        """
        Generate complete trading plan with signals, levels, and sentiment
        """
        signal = self.analyze_clusters(symbol)
        levels = self.get_support_resistance_levels(symbol)
        sentiment = self.get_market_sentiment(symbol)
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "signal": {
                "direction": signal.signal,
                "entry": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "confidence": signal.confidence,
                "risk_reward": signal.risk_reward,
                "reason": signal.reason
            },
            "levels": levels,
            "sentiment": sentiment,
            "recommendation": self._generate_recommendation(signal, levels, sentiment)
        }
    
    def _generate_recommendation(self, signal: TradingSignal, levels: Dict, sentiment: Dict) -> str:
        """Generate trading recommendation"""
        if signal.signal == "NEUTRAL":
            return "Wait for better setup - No strong signals currently"
        
        rec_parts = [f"Signal: {signal.signal}"]
        
        if signal.risk_reward:
            rec_parts.append(f"Risk/Reward: {signal.risk_reward:.2f}:1")
        
        if signal.confidence >= 0.7:
            rec_parts.append("HIGH CONFIDENCE")
        elif signal.confidence >= 0.5:
            rec_parts.append("MODERATE CONFIDENCE")
        else:
            rec_parts.append("LOW CONFIDENCE - Use smaller position")
        
        if sentiment['sentiment'] != "NEUTRAL":
            rec_parts.append(f"Market bias: {sentiment['sentiment']}")
        
        return " | ".join(rec_parts)


# Example usage
if __name__ == "__main__":
    strategy = LiquidationStrategy()
    
    # Get trading signal
    signal = strategy.analyze_clusters("BTCUSDT")
    print(f"\n📊 Trading Signal for BTCUSDT:")
    print(f"  Signal: {signal.signal}")
    print(f"  Entry: ${signal.entry_price:.2f}")
    print(f"  Stop Loss: ${signal.stop_loss:.2f}" if signal.stop_loss else "  Stop Loss: N/A")
    print(f"  Take Profit: ${signal.take_profit:.2f}" if signal.take_profit else "  Take Profit: N/A")
    print(f"  Confidence: {signal.confidence:.2%}")
    print(f"  Risk/Reward: {signal.risk_reward:.2f}:1" if signal.risk_reward else "  Risk/Reward: N/A")
    print(f"  Reason: {signal.reason}")
    
    # Get support/resistance levels
    levels = strategy.get_support_resistance_levels("BTCUSDT")
    print(f"\n📈 Support/Resistance Levels:")
    print(f"  Current Price: ${levels['current_price']:.2f}")
    print(f"  Support Levels:")
    for sup in levels['support']:
        print(f"    ${sup['price']:.2f} (strength: {sup['strength']:.2f}, OI: ${sup['oi']:,.0f})")
    print(f"  Resistance Levels:")
    for res in levels['resistance']:
        print(f"    ${res['price']:.2f} (strength: {res['strength']:.2f}, OI: ${res['oi']:,.0f})")
    
    # Get market sentiment
    sentiment = strategy.get_market_sentiment("BTCUSDT")
    print(f"\n💭 Market Sentiment:")
    print(f"  Sentiment: {sentiment.get('sentiment', 'UNKNOWN')}")
    print(f"  Long/Short Ratio: {sentiment.get('long_short_ratio', 0):.2f}")
    print(f"  Interpretation: {sentiment.get('interpretation', 'N/A')}")
    
    # Generate complete trading plan
    plan = strategy.generate_trading_plan("BTCUSDT")
    print(f"\n🎯 Complete Trading Plan:")
    print(f"  {plan['recommendation']}")
