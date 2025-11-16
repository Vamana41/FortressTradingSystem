#!/usr/bin/env python3
"""
Test and analyze subscription responses more carefully
"""

import asyncio
import websockets
import json

async def analyze_responses():
    """Analyze subscription responses in detail"""

    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"

    # Test symbols
    test_symbols = [
        {"exchange": "NSE", "symbol": "SBIN"},  # Known working
        {"exchange": "NSE", "symbol": "NIFTY"},  # Index test
        {"exchange": "MCX", "symbol": "CRUDEOIL"},  # MCX test
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
            auth_data = json.loads(auth_response)
            print(f"Auth response: {json.dumps(auth_data, indent=2)}")

            # Test each symbol
            for symbol_info in test_symbols:
                exchange = symbol_info['exchange']
                symbol = symbol_info['symbol']

                subscribe_message = {
                    "action": "subscribe",
                    "exchange": exchange,
                    "symbol": symbol
                }

                print(f"\n{'='*50}")
                print(f"Testing: {exchange}:{symbol}")
                print(f"Message: {json.dumps(subscribe_message)}")

                await websocket.send(json.dumps(subscribe_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)

                print(f"Response: {json.dumps(response_data, indent=2)}")

                # Analyze the response
                status = response_data.get("status", "unknown")
                if status == "success":
                    print("✅ SUCCESS - Symbol subscribed!")
                    subscriptions = response_data.get("subscriptions", [])
                    for sub in subscriptions:
                        print(f"  - {sub.get('exchange')}:{sub.get('symbol')} -> {sub.get('status')}")
                elif status == "partial":
                    print("⚠️  PARTIAL - Some subscriptions failed")
                    subscriptions = response_data.get("subscriptions", [])
                    for sub in subscriptions:
                        sub_status = sub.get('status', 'unknown')
                        symbol_str = f"{sub.get('exchange')}:{sub.get('symbol')}"
                        if sub_status == "success":
                            print(f"  ✅ {symbol_str} -> SUCCESS")
                        else:
                            print(f"  ❌ {symbol_str} -> {sub_status}: {sub.get('message', 'Unknown error')}")
                elif status == "error":
                    print(f"❌ ERROR - {response_data.get('message', 'Unknown error')}")
                else:
                    print(f"❓ UNKNOWN STATUS: {status}")

    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_responses())
