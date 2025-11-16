#!/usr/bin/env python3
"""
Test OpenAlgo WebSocket authentication and symbol injection
"""

import asyncio
import websockets
import json

async def test_authentication():
    """Test WebSocket authentication with API key"""
    
    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
    
    try:
        print(f"Connecting to OpenAlgo WebSocket at {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to OpenAlgo WebSocket!")
            print()
            
            # Test authentication methods
            auth_methods = [
                {"action": "auth", "apikey": api_key},
                {"action": "authenticate", "apikey": api_key},
                {"type": "auth", "apikey": api_key},
                {"action": "login", "apikey": api_key},
                {"method": "auth", "params": {"apikey": api_key}},
            ]
            
            for i, auth_msg in enumerate(auth_methods):
                print(f"Auth Test {i+1}: {auth_msg}")
                try:
                    await websocket.send(json.dumps(auth_msg))
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    print(f"  Response: {response}")
                    
                    # If authentication successful, try subscribing
                    if "success" in response.lower() or "authenticated" in response.lower():
                        print("  ✅ Authentication successful! Testing subscription...")
                        subscribe_msg = {"action": "subscribe", "symbols": ["SBIN", "RELIANCE"]}
                        await websocket.send(json.dumps(subscribe_msg))
                        sub_response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        print(f"  Subscribe Response: {sub_response}")
                        break
                        
                except asyncio.TimeoutError:
                    print("  No response (timeout)")
                except Exception as e:
                    print(f"  Error: {e}")
                print()
                
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_authentication())