#!/usr/bin/env python3
"""
Test OpenAlgo WebSocket with different API key field names
"""

import asyncio
import websockets
import json

async def test_api_key_fields():
    """Test different API key field names"""

    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"

    try:
        print(f"Connecting to OpenAlgo WebSocket at {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to OpenAlgo WebSocket!")
            print()

            # Test different field names for API key
            auth_methods = [
                {"action": "auth", "key": api_key},
                {"action": "auth", "token": api_key},
                {"action": "auth", "api_key": api_key},
                {"action": "authenticate", "key": api_key},
                {"type": "auth", "key": api_key},
                {"action": "subscribe", "key": api_key, "symbols": ["SBIN"]},
                {"action": "subscribe", "api_key": api_key, "symbols": ["SBIN"]},
            ]

            for i, auth_msg in enumerate(auth_methods):
                print(f"Auth Test {i+1}: {auth_msg}")
                try:
                    await websocket.send(json.dumps(auth_msg))
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    print(f"  Response: {response}")

                    # If authentication successful, try more subscriptions
                    if "success" in response.lower() or "authenticated" in response.lower():
                        print("  ✅ Authentication successful!")
                        break

                except asyncio.TimeoutError:
                    print("  No response (timeout)")
                except Exception as e:
                    print(f"  Error: {e}")
                print()

    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_key_fields())
