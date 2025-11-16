#!/usr/bin/env python3
"""
Test different data structures for OpenAlgo WebSocket subscription
"""

import asyncio
import websockets
import json

async def test_data_structures():
    """Test different data structures for subscription"""

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

            # Test different data structures
            subscription_formats = [
                # Test 3 variations from previous test
                {"action": "subscribe", "data": {"symbols": ["SBIN"]}},
                {"action": "subscribe", "data": {"symbols": ["NSE:SBIN"]}},
                {"action": "subscribe", "data": {"symbol": "SBIN"}},
                {"action": "subscribe", "data": {"symbol": "NSE:SBIN"}},

                # Try direct symbol field
                {"action": "subscribe", "symbol": "SBIN"},
                {"action": "subscribe", "symbol": "NSE:SBIN"},

                # Try array format
                {"action": "subscribe", "symbols": "SBIN"},
                {"action": "subscribe", "symbols": ["SBIN"]},

                # Try with exchange
                {"action": "subscribe", "exchange": "NSE", "symbol": "SBIN"},
                {"action": "subscribe", "exchange": "NSE", "symbols": ["SBIN"]},
            ]

            for i, sub_msg in enumerate(subscription_formats):
                print(f"\nTest {i+1}: {sub_msg}")
                try:
                    await websocket.send(json.dumps(sub_msg))
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"  Response: {response}")

                    # Check if successful
                    response_data = json.loads(response)
                    if response_data.get("status") == "success":
                        print("  ✅ SUCCESS!")
                        # Test with multiple symbols
                        multi_symbols = {"action": "subscribe", "symbols": ["SBIN", "RELIANCE", "TCS"]}
                        print(f"  Testing multi-symbols: {multi_symbols}")
                        await websocket.send(json.dumps(multi_symbols))
                        multi_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        print(f"  Multi-response: {multi_response}")
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
    asyncio.run(test_data_structures())
