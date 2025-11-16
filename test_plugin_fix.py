#!/usr/bin/env python3
"""
Test script to verify OpenAlgo Relay Server and Plugin Fix
"""

import asyncio
import websockets
import json
import time
import sys

def test_relay_connection():
    """Test connection to relay server"""
    print("Testing relay server connection...")

    async def test_connection():
        try:
            async with websockets.connect("ws://localhost:8766") as websocket:
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                response = await websocket.recv()
                data = json.loads(response)

                if data.get("type") == "pong":
                    print("✓ Relay server connection successful")
                    return True
                else:
                    print(f"✗ Unexpected response: {data}")
                    return False

        except Exception as e:
            print(f"✗ Relay server connection failed: {e}")
            return False

    return asyncio.run(test_connection())

def test_quote_subscription():
    """Test quote subscription"""
    print("Testing quote subscription...")

    async def test_subscription():
        try:
            async with websockets.connect("ws://localhost:8766") as websocket:
                # Subscribe to a symbol
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "symbol": "RELIANCE-NSE"
                }))

                # Wait for response
                response = await websocket.recv()
                data = json.loads(response)

                if data.get("type") == "quote":
                    print(f"✓ Quote received: {data}")
                    return True
                else:
                    print(f"✗ Quote subscription failed: {data}")
                    return False

        except Exception as e:
            print(f"✗ Quote subscription failed: {e}")
            return False

    return asyncio.run(test_subscription())

def main():
    print("OpenAlgo Plugin Fix Test Suite")
    print("=" * 40)

    tests = [
        ("Relay Connection", test_relay_connection),
        ("Quote Subscription", test_quote_subscription),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        if test_func():
            passed += 1
        time.sleep(1)

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests passed! The fix should work correctly.")
    else:
        print("✗ Some tests failed. Check the relay server and configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
