#!/usr/bin/env python3
"""Test Vantage2 API endpoint"""

import requests
import json
import time

def test_endpoint():
    base_url = "http://localhost:8003"
    
    print("=" * 60)
    print("VANTAGE2 API TEST")
    print("=" * 60)
    print()
    
    # Test root endpoint
    print("1. Testing root endpoint...")
    try:
        r = requests.get(f"{base_url}/", timeout=5)
        print(f"   Status: {r.status_code}")
        print(f"   Response: {json.dumps(r.json(), indent=2)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # Test fundingOI endpoint
    print("2. Testing /vantage2/fundingOI endpoint...")
    try:
        start = time.time()
        r = requests.get(f"{base_url}/vantage2/fundingOI", timeout=30)
        elapsed = time.time() - start
        
        print(f"   Status: {r.status_code}")
        print(f"   Response time: {elapsed:.2f}s")
        
        if r.status_code == 200:
            data = r.json()
            print(f"   ✅ Success: {data.get('ok')}")
            print(f"   ✅ Timestamp: {data.get('t')}")
            print(f"   ✅ Total symbols: {len(data.get('d', []))}")
            
            # Check data quality
            symbols = data.get('d', [])
            with_oi = sum(1 for s in symbols if s.get('oi') is not None)
            with_fr = sum(1 for s in symbols if s.get('fr') is not None)
            
            print(f"   ✅ Symbols with OI: {with_oi}/{len(symbols)}")
            print(f"   ✅ Symbols with FR: {with_fr}/{len(symbols)}")
            
            # Show sample
            if symbols:
                sample = symbols[0]
                print(f"   ✅ Sample: {sample.get('s')} - OI: {sample.get('oi')}, FR: {sample.get('fr')}")
        else:
            print(f"   ❌ Error: {r.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_endpoint()
