#!/usr/bin/env python3
"""
Quick test script for OpenAlgo Gateway Integration
"""

import asyncio
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from fortress.core.event_bus import EventBus
from fortress.worker.worker import FortressWorker
from fortress.integrations.openalgo_gateway import OpenAlgoGateway


class MockOpenAlgoGateway(OpenAlgoGateway):
    """Mock OpenAlgo Gateway for testing"""
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:8080/api/v1", event_bus=None):
        super().__init__(api_key, base_url, event_bus)
        self.mock_positions = []
        self.mock_funds = {
            "available_margin": 1000000.0,
            "used_margin": 0.0,
            "total_balance": 1000000.0,
            "cash_balance": 1000000.0
        }
        self.order_counter = 0
        self.mock_orders = {}
    
    async def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """Mock implementation"""
        await asyncio.sleep(0.01)  # Minimal delay
        
        if endpoint == "positions":
            return {"status": "success", "data": self.mock_positions}
        elif endpoint == "funds":
            return {"status": "success", "data": self.mock_funds}
        elif endpoint == "orders/place":
            self.order_counter += 1
            order_id = f"MOCK_ORDER_{self.order_counter}"
            self.mock_orders[order_id] = {
                "order_id": order_id,
                "symbol": data.get("symbol"),
                "quantity": data.get("quantity"),
                "side": data.get("side"),
                "status": "COMPLETE",
                "filled_quantity": data.get("quantity", 0)
            }
            return {"status": "success", "data": {"order_id": order_id}}
        elif endpoint == "orders/status":
            order_id = data.get("order_id")
            order = self.mock_orders.get(order_id, {})
            return {"status": "success", "data": order}
        else:
            return {"status": "error", "message": f"Endpoint {endpoint} not implemented"}


async def quick_test():
    """Quick integration test"""
    print("🚀 Quick OpenAlgo Gateway Integration Test")
    print("=" * 50)
    
    # Create event bus
    event_bus = EventBus()
    await event_bus.connect()
    
    # Create worker
    worker = FortressWorker(event_bus)
    await worker.initialize()
    
    # Replace with mock gateway
    worker.openalgo_gateway = MockOpenAlgoGateway(
        api_key="test_key",
        base_url="http://localhost:8080/api/v1",
        event_bus=event_bus
    )
    await worker.openalgo_gateway.connect()
    
    try:
        # Test 1: Position sync
        print("\n📊 Test 1: Position Synchronization")
        success = await worker.synchronize_with_broker()
        print(f"✅ Position sync: {success}")
        
        # Test 2: Small order execution (no slicing needed)
        print("\n📈 Test 2: Small Order Execution")
        small_job = {
            "job_id": "SMALL_TEST_001",
            "symbol": "NIFTY25NOV24000CE",
            "action": "BUY",
            "total_qty": 25,  # Less than 9 lots
            "price": 100.0,
            "strategy_name": "TEST_STRATEGY"
        }
        
        result = await worker.execute_trade_job(small_job)
        print(f"✅ Small order execution: {result}")
        
        # Test 3: Medium order with slicing
        print("\n📊 Test 3: Medium Order with Slicing")
        medium_job = {
            "job_id": "MEDIUM_TEST_002",
            "symbol": "BANKNIFTY25NOV50000CE",
            "action": "SELL",
            "total_qty": 45,  # 5 lots - should create 5 slices of 9
            "price": 200.0,
            "strategy_name": "TEST_STRATEGY"
        }
        
        result = await worker.execute_trade_job(medium_job)
        print(f"✅ Medium order execution: {result}")
        
        print("\n🎉 All tests completed successfully!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await worker.cleanup()
        await event_bus.disconnect()
        print("\n🧹 Cleanup completed")


if __name__ == "__main__":
    asyncio.run(quick_test())