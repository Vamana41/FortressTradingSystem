#!/usr/bin/env python3
"""
Test different subscription formats for OpenAlgo WebSocket
"""

import asyncio
import websockets
import json

async def test_subscription_formats():
    """Test different subscription message formats"""
    
    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
    
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
            print(f"Auth response: {auth_response}")
            
            # Test different subscription formats
            subscription_formats = [
                {"action": "subscribe", "symbols": ["SBIN", "RELIANCE"]},
                {"action": "subscribe", "symbols": ["NSE:SBIN", "NSE:RELIANCE"]},
                {"action": "subscribe", "data": {"symbols": ["SBIN", "RELIANCE"]}},
                {"type": "subscribe", "symbols": ["SBIN", "RELIANCE"]},
                {"command": "subscribe", "symbols": ["SBIN", "RELIANCE"]},
                {"action": "sub", "symbols": ["SBIN", "RELIANCE"]},
                {"action": "add", "symbols": ["SBIN", "RELIANCE"]},
                {"action": "watch", "symbols": ["SBIN", "RELIANCE"]},
            ]
            
            for i, sub_msg in enumerate(subscription_formats):
                print(f"\nSubscription Test {i+1}: {sub_msg}")
                try:
                    await websocket.send(json.dumps(sub_msg))
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"  Response: {response}")
                    
                    # Check if successful
                    response_data = json.loads(response)
                    if response_data.get("status") == "success":
                        print("  ✅ SUCCESS!")
                        break
                    elif "error" in response_data.get("status", "").lower():
                        print(f"  ❌ Error: {response_data.get('message', 'Unknown error')}")
                    else:
                        print(f"  ⚠️  Unknown response: {response_data}")
                        
                except asyncio.TimeoutError:
                    print("  ⏰ Timeout - no response")
                except Exception as e:
                    print(f"  💥 Exception: {e}")
                    
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_subscription_formats())