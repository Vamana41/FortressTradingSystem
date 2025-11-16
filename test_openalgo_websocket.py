#!/usr/bin/env python3
"""
Test script to connect to OpenAlgo native WebSocket
"""

import asyncio
import websockets
import json

async def test_websocket():
    """Test connection to OpenAlgo WebSocket"""
    
    uri = "ws://127.0.0.1:8765"
    
    try:
        print(f"Connecting to OpenAlgo WebSocket at {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to OpenAlgo WebSocket!")
            
            # Send a test message
            test_message = json.dumps({"type": "test", "message": "Hello from symbol injector"})
            await websocket.send(test_message)
            print(f"Sent: {test_message}")
            
            # Try to receive a response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Received: {response}")
            except asyncio.TimeoutError:
                print("No response received (timeout after 5 seconds)")
                
            print("WebSocket connection test completed successfully!")
            
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())