#!/usr/bin/env python3
"""Test the live indicators API endpoint"""

import json
import httpx
import time

def test_api():
    base_url = "http://localhost:8002"
    
    print("="*60)
    print("Testing Live Indicators API")
    print("="*60)
    
    # Test root
    print("\n1. Testing root endpoint...")
    try:
        response = httpx.get(f"{base_url}/", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)[:200]}...")
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    # Test all indicators
    print("\n2. Testing /indicators endpoint (all symbols)...")
    start = time.time()
    try:
        response = httpx.get(f"{base_url}/indicators", timeout=30)
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {response.status_code}")
            print(f"   Success: {data.get('success')}")
            print(f"   Symbols returned: {len(data.get('data', []))}")
            print(f"   API Latency: {data.get('latency_ms', 0):.1f}ms")
            print(f"   Request Time: {elapsed:.1f}ms")
            print(f"   Timestamp: {data.get('timestamp', 'N/A')}")
            
            # Check for entry signals
            signals = [d for d in data.get('data', []) if d.get('entry_signal')]
            print(f"   Entry Signals: {len(signals)}")
            
            if signals:
                print(f"\n   Entry Signals Found:")
                for sig in signals[:5]:
                    print(f"     {sig['symbol']}: {sig['entry_signal']} @ {sig['leverage']}x (strength: {sig['signal_strength']:.2f})")
            
            # Sample data
            if data.get('data'):
                sample = data['data'][0]
                print(f"\n   Sample Symbol ({sample['symbol']}):")
                print(f"     Price: ${sample['price']:.6f}")
                print(f"     Volume: {sample['volume']:,.0f}")
                print(f"     RSI: {sample['indicators'].get('rsi', 0):.2f}")
                print(f"     Momentum: {sample['indicators'].get('momentum', 0):.4f}")
                print(f"     EMA Fast: {sample['indicators'].get('ema_fast', 0):.6f}")
                print(f"     EMA Slow: {sample['indicators'].get('ema_slow', 0):.6f}")
                print(f"     ATR: {sample['indicators'].get('atr', 0):.6f}")
                print(f"     Volume Ratio: {sample['indicators'].get('volume_ratio', 0):.2f}")
        else:
            print(f"   Error: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_api()
