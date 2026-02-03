#!/usr/bin/env python3
"""Quick test script for the live indicators API"""

import asyncio
import httpx

async def test_api():
    """Test the API endpoints"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test root
        print("Testing root endpoint...")
        response = await client.get(f"{base_url}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")
        
        # Test symbols
        print("Testing /symbols endpoint...")
        response = await client.get(f"{base_url}/symbols")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Symbols count: {data.get('count', 0)}\n")
        
        # Test single symbol
        print("Testing /indicators/DOGE/USDT:USDT...")
        try:
            response = await client.get(f"{base_url}/indicators/DOGE/USDT:USDT")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Symbol: {data['data']['symbol']}")
                print(f"Price: ${data['data']['price']:.6f}")
                print(f"RSI: {data['data']['indicators'].get('rsi', 'N/A')}")
                print(f"Momentum: {data['data']['indicators'].get('momentum', 'N/A')}")
                print(f"Entry Signal: {data['data']['entry_signal']}")
                print(f"Leverage: {data['data']['leverage']}x")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n" + "="*50)
        print("API test complete!")

if __name__ == "__main__":
    asyncio.run(test_api())
