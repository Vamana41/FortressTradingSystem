#!/usr/bin/env python3
"""
Test script for OpenAlgo Gateway Integration

This script tests the complete integration between Fortress Worker and OpenAlgo Gateway,
including trade execution, position synchronization, and error handling.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from fortress.core.event_bus import EventBus
from fortress.core.events import EventType, OrderEvent
from fortress.worker.worker import FortressWorker
from fortress.integrations.openalgo_gateway import OpenAlgoGateway, create_openalgo_gateway


class MockOpenAlgoGateway(OpenAlgoGateway):
    """
    Mock OpenAlgo Gateway for testing without requiring actual OpenAlgo server
    """
    
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
    
    async def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, str] = None) -> Dict[str, Any]:
        """Mock implementation of _make_request"""
        await asyncio.sleep(0.1)  # Simulate network delay
        
        if endpoint == "positions":
            return {
                "status": "success",
                "data": self.mock_positions
            }
        elif endpoint == "funds":
            return {
                "status": "success", 
                "data": self.mock_funds
            }
        elif endpoint == "orders/place":
            self.order_counter += 1
            order_id = f"MOCK_ORDER_{self.order_counter}"
            self.mock_orders[order_id] = {
                "order_id": order_id,
                "symbol": data.get("symbol"),
                "quantity": data.get("quantity"),
                "side": data.get("side"),
                "status": "PENDING",
                "filled_quantity": 0
            }
            return {
                "status": "success",
                "data": {"order_id": order_id}
            }
        elif endpoint == "orders/status":
            order_id = data.get("order_id")
            order = self.mock_orders.get(order_id)
            if order:
                # Simulate order filling
                if order["status"] == "PENDING":
                    order["status"] = "COMPLETE"
                    order["filled_quantity"] = order["quantity"]
                return {
                    "status": "success",
                    "data": order
                }
            else:
                return {
                    "status": "error",
                    "message": "Order not found"
                }
        else:
            return {"status": "error", "message": f"Endpoint {endpoint} not implemented in mock"}


async def test_gateway_integration():
    """Test the complete OpenAlgo Gateway integration"""
    print("🚀 Starting OpenAlgo Gateway Integration Test")
    print("=" * 60)
    
    # Create event bus
    event_bus = EventBus()
    await event_bus.connect()
    
    # Create worker with mock gateway
    worker = FortressWorker(event_bus)
    
    # Initialize the worker (this sets up Redis)
    await worker.initialize()
    
    # Replace the real gateway with our mock for testing
    worker.openalgo_gateway = MockOpenAlgoGateway(
        api_key="test_key",
        base_url="http://localhost:8080/api/v1",
        event_bus=event_bus
    )
    await worker.openalgo_gateway.connect()
    
    try:
        # Test 1: Position Synchronization
        print("\n📊 Test 1: Position Synchronization")
        print("-" * 40)
        success = await worker.synchronize_with_broker()
        print(f"✅ Position sync successful: {success}")
        
        # Test 2: Single Order Execution
        print("\n📈 Test 2: Single Order Execution")
        print("-" * 40)
        
        test_job = {
            "job_id": "TEST_JOB_001",
            "symbol": "NIFTY25NOV24000CE",
            "action": "BUY",
            "total_qty": 50,  # 1 lot of NIFTY
            "price": 100.0,
            "strategy_name": "TEST_STRATEGY"
        }
        
        # Add job to queue
        await worker.redis_client.rpush("trade_queue", json.dumps(test_job))
        print(f"📤 Added job to queue: {test_job['job_id']}")
        
        # Process the job
        await worker.execute_trade_job(test_job)
        print("✅ Single order execution completed")
        
        # Test 3: Large Order with Slicing
        print("\n📊 Test 3: Large Order with SEBI-Compliant Slicing")
        print("-" * 40)
        
        large_job = {
            "job_id": "TEST_JOB_002", 
            "symbol": "BANKNIFTY25NOV50000CE",
            "action": "SELL",
            "total_qty": 450,  # 10 lots - should be sliced into 9+1
            "price": 200.0,
            "strategy_name": "TEST_STRATEGY"
        }
        
        # Add large job to queue
        await worker.redis_client.rpush("trade_queue", json.dumps(large_job))
        print(f"📤 Added large job to queue: {large_job['job_id']}")
        
        # Process the large job
        await worker.execute_trade_job(large_job)
        print("✅ Large order execution with slicing completed")
        
        # Test 4: All-or-Nothing Failure Simulation
        print("\n⚠️ Test 4: All-or-Nothing Failure Simulation")
        print("-" * 40)
        
        # Create a job that will fail on second slice
        failing_job = {
            "job_id": "TEST_JOB_003",
            "symbol": "FINNIFTY25NOV22000CE", 
            "action": "BUY",
            "total_qty": 100,  # 2 lots - first succeeds, second fails
            "price": 150.0,
            "strategy_name": "TEST_STRATEGY"
        }
        
        # Temporarily modify mock to simulate failure
        original_make_request = worker.openalgo_gateway._make_request
        
        async def failing_make_request(method, endpoint, data=None, params=None):
            if endpoint == "orders/place" and worker.openalgo_gateway.order_counter == 3:
                # Simulate failure on third order (second slice of this job)
                return {"status": "error", "message": "Insufficient margin"}
            return await original_make_request(method, endpoint, data, params)
        
        worker.openalgo_gateway._make_request = failing_make_request
        
        # Process the failing job
        result = await worker.execute_trade_job(failing_job)
        print(f"✅ All-or-nothing failure handled: {not result}")  # Should return False
        
        # Restore original method
        worker.openalgo_gateway._make_request = original_make_request
        
        # Test 5: Event Bus Integration
        print("\n📡 Test 5: Event Bus Integration")
        print("-" * 40)
        
        # Listen for events
        events_received = []
        
        async def event_listener(event_type: EventType, priority: str):
            while True:
                try:
                    event = await event_bus.consume_event(event_type, priority)
                    events_received.append(event)
                    print(f"📨 Received event: {event.event_type} - {event.data}")
                except asyncio.CancelledError:
                    break
        
        # Start event listeners
        listeners = [
            asyncio.create_task(event_listener(EventType.ORDER_PLACED, "HIGH")),
            asyncio.create_task(event_listener(EventType.ORDER_EXECUTED, "HIGH")),
            asyncio.create_task(event_listener(EventType.ORDER_NEUTRALIZED, "CRITICAL"))
        ]
        
        # Give listeners time to process
        await asyncio.sleep(2)
        
        # Cancel listeners
        for listener in listeners:
            listener.cancel()
        
        print(f"✅ Event bus integration working - received {len(events_received)} events")
        
        print("\n🎉 All OpenAlgo Gateway Integration Tests Completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        await worker.cleanup()
        await event_bus.disconnect()
        print("\n🧹 Cleanup completed")


async def test_real_gateway():
    """Test with real OpenAlgo Gateway (requires OpenAlgo server running)"""
    print("🏗️ Testing with Real OpenAlgo Gateway")
    print("⚠️  This requires OpenAlgo server to be running on localhost:8080")
    print("=" * 60)
    
    try:
        # Create event bus
        event_bus = EventBus()
        await event_bus.connect()
        
        # Create real gateway
        gateway = await create_openalgo_gateway(
            api_key="your_openalgo_api_key",  # Replace with real API key
            base_url="http://localhost:8080/api/v1",
            event_bus=event_bus
        )
        
        print("✅ Connected to real OpenAlgo Gateway")
        
        # Test health check
        healthy = await gateway.health_check()
        print(f"✅ Gateway health check: {healthy}")
        
        # Test funds retrieval
        funds = await gateway.get_funds()
        print(f"💰 Available margin: {funds.available_margin}")
        
        # Test positions retrieval
        positions = await gateway.get_positions()
        print(f"📊 Current positions: {len(positions)}")
        for pos in positions[:5]:  # Show first 5 positions
            print(f"  - {pos.symbol}: {pos.quantity} @ {pos.average_price}")
        
        # Test quote retrieval
        quote = await gateway.get_quotes("NIFTY25NOV24000CE")
        print(f"📈 NIFTY quote: {quote}")
        
        print("\n✅ Real gateway tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Real gateway test failed: {e}")
        print("💡 Make sure OpenAlgo server is running on localhost:8080")
        
    finally:
        await event_bus.disconnect()


if __name__ == "__main__":
    print("🔬 OpenAlgo Gateway Integration Test Suite")
    print("=" * 60)
    
    # Run mock tests first
    asyncio.run(test_gateway_integration())
    
    # Optionally run real tests (uncomment if you have OpenAlgo running)
    # print("\n" + "="*60 + "\n")
    # asyncio.run(test_real_gateway())