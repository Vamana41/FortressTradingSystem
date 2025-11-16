#!/usr/bin/env python3
"""
Test script to discover OpenAlgo WebSocket protocol
"""

import asyncio
import websockets
import json

async def test_protocol():
    """Test different WebSocket message formats"""
    
    uri = "ws://127.0.0.1:8765"
    
    test_messages = [
        {"action": "subscribe", "symbols": ["SBIN", "RELIANCE"]},
        {"action": "add_symbols", "symbols": ["SBIN", "RELIANCE"]},
        {"action": "inject", "symbols": ["SBIN", "RELIANCE"]},
        {"type": "subscribe", "data": {"symbols": ["SBIN", "RELIANCE"]}},
        {"command": "add", "symbols": ["SBIN", "RELIANCE"]},
        {"method": "subscribe", "params": {"symbols": ["SBIN", "RELIANCE"]}},
        {"action": "ping"},
        {"type": "ping"},
    ]
    
    try:
        print(f"Connecting to OpenAlgo WebSocket at {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to OpenAlgo WebSocket!")
            print()
            
            for i, message in enumerate(test_messages):
                print(f"Test {i+1}: {message}")
                try:
                    await websocket.send(json.dumps(message))
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    print(f"  Response: {response}")
                except asyncio.TimeoutError:
                    print("  No response (timeout)")
                except Exception as e:
                    print(f"  Error: {e}")
                print()
                
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_protocol())