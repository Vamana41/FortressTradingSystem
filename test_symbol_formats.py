#!/usr/bin/env python3
"""
Test correct symbol formats for MCX and NSE indices
"""

import asyncio
import websockets
import json

async def test_symbol_formats():
    """Test different symbol formats"""

    uri = "ws://127.0.0.1:8765"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"

    # Test different symbol formats
    test_symbols = [
        # MCX commodities - different formats
        {"exchange": "MCX", "symbol": "CRUDEOIL"},
        {"exchange": "MCX", "symbol": "CRUDEOIL22FEB25"},
        {"exchange": "MCX", "symbol": "CRUDEOILM"},
        {"exchange": "MCX", "symbol": "CRUDEOILM24FEB25"},
        {"exchange": "MCX", "symbol": "NATURALGAS"},
        {"exchange": "MCX", "symbol": "NATURALGASM"},
        {"exchange": "MCX", "symbol": "GOLD"},
        {"exchange": "MCX", "symbol": "GOLDM"},
        {"exchange": "MCX", "symbol": "GOLDPETAL"},
        {"exchange": "MCX", "symbol": "SILVER"},
        {"exchange": "MCX", "symbol": "SILVERM"},
        {"exchange": "MCX", "symbol": "COPPER"},
        {"exchange": "MCX", "symbol": "COPPERM"},
        {"exchange": "MCX", "symbol": "NICKEL"},
        {"exchange": "MCX", "symbol": "NICKELM"},

        # NSE indices - different formats
        {"exchange": "NSE", "symbol": "NIFTY"},
        {"exchange": "NSE", "symbol": "NIFTY50"},
        {"exchange": "NSE", "symbol": "NIFTY50-INDEX"},
        {"exchange": "NSE", "symbol": "BANKNIFTY"},
        {"exchange": "NSE", "symbol": "NIFTYBANK"},
        {"exchange": "NSE", "symbol": "NIFTYBANK-INDEX"},
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
            print(f"Auth response: {auth_response}")

            # Test each symbol
            working_symbols = []

            for symbol_info in test_symbols:
                exchange = symbol_info['exchange']
                symbol = symbol_info['symbol']

                subscribe_message = {
                    "action": "subscribe",
                    "exchange": exchange,
                    "symbol": symbol
                }

                print(f"\nTesting: {exchange}:{symbol}")
                await websocket.send(json.dumps(subscribe_message))

                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)

                    if response_data.get("status") == "success":
                        print(f"  ✅ SUCCESS!")
                        working_symbols.append(f"{exchange}:{symbol}")
                    else:
                        print(f"  ❌ Failed: {response_data.get('message', 'Unknown error')}")

                except asyncio.TimeoutError:
                    print(f"  ⏰ Timeout")
                except Exception as e:
                    print(f"  💥 Exception: {e}")

            print(f"\n🎉 Working symbols found: {len(working_symbols)}")
            for symbol in working_symbols:
                print(f"  - {symbol}")

    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_symbol_formats())
