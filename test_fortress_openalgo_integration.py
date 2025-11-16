#!/usr/bin/env python3
"""
Test complete Fortress → OpenAlgo integration
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fortress', 'src'))

from fortress.main import FortressTradingSystem
from fortress.utils.api_key_manager import SecureAPIKeyManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_fortress_openalgo_integration():
    """Test the complete Fortress → OpenAlgo integration"""

    print("🚀 Testing Fortress → OpenAlgo Integration")
    print("=" * 50)

    # Get the stored API key
    api_key_manager = SecureAPIKeyManager()
    api_key = api_key_manager.get_api_key("openalgo")

    if not api_key:
        print("❌ No OpenAlgo API key found in secure storage!")
        return False

    print(f"🔐 Using API key: {api_key[:8]}...")

    # Initialize Fortress system
    try:
        fortress = FortressTradingSystem()
        print("✅ Fortress system initialized")

        # Initialize event bus first (required for OpenAlgo gateway)
        from fortress.core.event_bus import event_bus_manager
        fortress.event_bus = event_bus_manager.get_event_bus(
            name="test",
            redis_url="redis://localhost:6379",
            key_prefix="test",
        )
        await fortress.event_bus.connect()
        print("✅ Event bus initialized")

        # Initialize OpenAlgo gateway
        await fortress._initialize_openalgo_gateway()
        print("✅ OpenAlgo gateway initialized")

        # Test OpenAlgo gateway connection
        if fortress.openalgo_gateway:
            print("✅ OpenAlgo gateway found")

            # Test connection
            try:
                await fortress.openalgo_gateway.connect()
                print("✅ OpenAlgo gateway connected")

                # Test API calls through the gateway
                try:
                    # Test funds retrieval
                    funds = await fortress.openalgo_gateway.get_funds()
                    print(f"✅ Funds retrieved: {funds}")

                    # Test positions
                    positions = await fortress.openalgo_gateway.get_positions()
                    print(f"✅ Positions retrieved: {len(positions)} positions")

                    # Test orders (using get_orderbook method)
                    orders = await fortress.openalgo_gateway.get_orderbook()
                    print(f"✅ Orders retrieved: {len(orders)} orders")

                    print("\n🎉 All integration tests passed!")
                    return True

                except Exception as e:
                    print(f"❌ API call failed: {e}")
                    return False

            except Exception as e:
                print(f"❌ Gateway connection failed: {e}")
                return False
        else:
            print("❌ OpenAlgo gateway not found in Fortress system!")
            return False

    except Exception as e:
        print(f"❌ Fortress initialization failed: {e}")
        return False

    finally:
        # Cleanup
        try:
            if hasattr(fortress, 'openalgo_gateway'):
                await fortress.openalgo_gateway.disconnect()
                print("✅ OpenAlgo gateway disconnected")
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_fortress_openalgo_integration())
    sys.exit(0 if success else 1)
