#!/usr/bin/env python3
"""
Fresh test of OpenAlgo WebSocket authentication with current API key
"""

import asyncio
import websockets
import json

async def fresh_auth_test():
    """Fresh authentication test"""
    
    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
    
    try:
        print(f"Fresh connection to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Test the exact same authentication as in the injector
            auth_message = {
                "action": "auth",
                "api_key": api_key
            }
            
            print(f"Sending auth: {auth_message}")
            await websocket.send(json.dumps(auth_message))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            print(f"Response: {response}")
            
            response_data = json.loads(response)
            if response_data.get("status") == "success":
                print("✅ Authentication successful!")
                
                # Now test subscription
                subscribe_msg = {
                    "action": "subscribe",
                    "symbols": ["NSE:SBIN", "NSE:RELIANCE"]
                }
                print(f"Sending subscribe: {subscribe_msg}")
                await websocket.send(json.dumps(subscribe_msg))
                
                sub_response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                print(f"Subscribe response: {sub_response}")
                
            else:
                print(f"❌ Authentication failed: {response_data}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(fresh_auth_test())