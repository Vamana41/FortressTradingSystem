#!/usr/bin/env python3
"""
Test NSE index symbols with different formats
"""

import asyncio
import websockets
import json

async def test_nse_indices():
    """Test different NSE index symbol formats"""
    
    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
    
    # Test different NSE index formats
    nse_indices = [
        {"exchange": "NSE", "symbol": "NIFTY"},
        {"exchange": "NSE", "symbol": "NIFTY50"},
        {"exchange": "NSE", "symbol": "NIFTY_50"},
        {"exchange": "NSE", "symbol": "BANKNIFTY"},
        {"exchange": "NSE", "symbol": "BANK_NIFTY"},
        {"exchange": "NSE", "symbol": "FINNIFTY"},
        {"exchange": "NSE", "symbol": "MIDCPNIFTY"},
        {"exchange": "NSE", "symbol": "NIFTYNXT50"},
    ]
    
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Authenticate first
            auth_message = {
                "action": "auth",
                "api_key": api_key
            }
            
            await websocket.send(json.dumps(auth_message))
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            print("✅ Authentication successful!")
            
            # Test each index symbol
            working_indices = []
            
            for symbol_info in nse_indices:
                exchange = symbol_info['exchange']
                symbol = symbol_info['symbol']
                
                subscribe_message = {
                    "action": "subscribe",
                    "exchange": exchange,
                    "symbol": symbol
                }
                
                print(f"\nTesting: {exchange}:{symbol}")
                await websocket.send(json.dumps(subscribe_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                
                status = response_data.get("status", "unknown")
                if status == "success":
                    print(f"  ✅ SUCCESS!")
                    working_indices.append(f"{exchange}:{symbol}")
                elif status == "partial":
                    # Check individual subscription status
                    subscriptions = response_data.get("subscriptions", [])
                    for sub in subscriptions:
                        sub_status = sub.get('status', 'unknown')
                        if sub_status == "success":
                            print(f"  ✅ SUCCESS!")
                            working_indices.append(f"{exchange}:{symbol}")
                        else:
                            print(f"  ❌ Failed: {sub.get('message', 'Unknown error')}")
                else:
                    print(f"  ❌ Unknown status: {status}")
            
            print(f"\n🎉 Working NSE indices found: {len(working_indices)}")
            for symbol in working_indices:
                print(f"  - {symbol}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_nse_indices())