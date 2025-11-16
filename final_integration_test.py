#!/usr/bin/env python3
"""
Final comprehensive integration test for Fortress Trading System
Tests the complete workflow: AmiBroker → OpenAlgo → Fortress
"""

import asyncio
import sys
import os
import requests
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fortress', 'src'))

from fortress.utils.api_key_manager import SecureAPIKeyManager

def test_openalgo_server():
    """Test OpenAlgo server connectivity"""
    print("🔍 Testing OpenAlgo Server...")

    try:
        response = requests.get("http://localhost:5000/", timeout=10)
        if response.status_code == 200:
            print("✅ OpenAlgo server is running")
            return True
        else:
            print(f"❌ OpenAlgo server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ OpenAlgo server connection failed: {e}")
        return False

def test_openalgo_api_endpoints():
    """Test all OpenAlgo API endpoints"""
    print("🔍 Testing OpenAlgo API Endpoints...")

    api_key_manager = SecureAPIKeyManager()
    api_key = api_key_manager.get_api_key("openalgo")

    if not api_key:
        print("❌ No API key found in secure storage")
        return False

    endpoints = [
        "/api/v1/ping",
        "/api/v1/funds",
        "/api/v1/positionbook",
        "/api/v1/orderbook",
        "/api/v1/holdings"
    ]

    success_count = 0

    for endpoint in endpoints:
        try:
            response = requests.post(
                f"http://localhost:5000{endpoint}",
                json={"apikey": api_key},
                timeout=10
            )

            if response.status_code == 200:
                print(f"✅ {endpoint}: OK")
                success_count += 1
            else:
                print(f"❌ {endpoint}: {response.status_code}")

        except Exception as e:
            print(f"❌ {endpoint}: Error - {e}")

    print(f"📊 API Test Results: {success_count}/{len(endpoints)} endpoints working")
    return success_count == len(endpoints)

async def test_fortress_openalgo_integration():
    """Test Fortress to OpenAlgo integration"""
    print("🔍 Testing Fortress → OpenAlgo Integration...")

    try:
        from fortress.main import FortressTradingSystem

        fortress = FortressTradingSystem()

        # Initialize event bus
        from fortress.core.event_bus import event_bus_manager
        fortress.event_bus = event_bus_manager.get_event_bus(
            name="test_integration",
            redis_url="redis://localhost:6379",
            key_prefix="test_integration",
        )
        await fortress.event_bus.connect()

        # Initialize OpenAlgo gateway
        await fortress._initialize_openalgo_gateway()

        # Test connection
        await fortress.openalgo_gateway.connect()

        # Test API calls
        funds = await fortress.openalgo_gateway.get_funds()
        positions = await fortress.openalgo_gateway.get_positions()
        orders = await fortress.openalgo_gateway.get_orderbook()

        await fortress.openalgo_gateway.disconnect()

        print(f"✅ Funds: Available Margin: {funds.available_margin}")
        print(f"✅ Positions: {len(positions)} positions")
        print(f"✅ Orders: {len(orders)} orders")

        return True

    except Exception as e:
        print(f"❌ Fortress integration test failed: {e}")
        return False

def test_amiBroker_plugin_setup():
    """Test AmiBroker plugin setup"""
    print("🔍 Testing AmiBroker Plugin Setup...")

    # Check if plugin files exist
    plugin_files = [
        "C:/Program Files/AmiBroker/Plugins/OpenAlgoPlugin.dll",
        "C:/Program Files (x86)/AmiBroker/Plugins/OpenAlgoPlugin.dll"
    ]

    plugin_found = False
    for plugin_file in plugin_files:
        if os.path.exists(plugin_file):
            print(f"✅ OpenAlgo plugin found: {plugin_file}")
            plugin_found = True
            break

    if not plugin_found:
        print("⚠️  OpenAlgo plugin not found in standard locations")
        print("💡 Please ensure OpenAlgoPlugin.dll is manually placed in AmiBroker Plugins folder")

    # Check if AFL formula exists
    afl_file = "OpenAlgo_ATM_Scanner.afl"
    if os.path.exists(afl_file):
        print(f"✅ AFL formula found: {afl_file}")
        return True
    else:
        print(f"❌ AFL formula not found: {afl_file}")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Final Integration Test for Fortress Trading System")
    print("=" * 60)
    print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    tests = [
        ("OpenAlgo Server", test_openalgo_server),
        ("OpenAlgo API Endpoints", test_openalgo_api_endpoints),
        ("Fortress Integration", lambda: asyncio.run(test_fortress_openalgo_integration())),
        ("AmiBroker Plugin", test_amiBroker_plugin_setup)
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*60)
    print("📊 FINAL TEST SUMMARY")
    print("="*60)

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if result:
            passed += 1

    print(f"\n🎯 Overall Result: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("\n🎉 ALL TESTS PASSED! System is ready for trading.")
        print("\n📋 Next Steps:")
        print("1. Open AmiBroker and load the OpenAlgo_ATM_Scanner.afl formula")
        print("2. Run the ATM scanner to identify trading opportunities")
        print("3. Start the Fortress Trading System: python launch_fortress.py")
        print("4. Monitor the dashboard at http://localhost:8000")
        return 0
    else:
        print(f"\n⚠️  {len(tests) - passed} tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
