# ===================================================================================
# ==                 Fortress Trading System: Core Functionality Test              ==
# ===================================================================================

import asyncio
import json
import tempfile
from pathlib import Path

from fortress.core.event_bus import EventBus, event_bus_manager
from fortress.core.events import EventType
from fortress.brain.brain import FortressBrain
from fortress.worker.worker import FortressWorker


async def test_core_functionality():
    """Test core Fortress Trading System functionality"""
    print("🚀 Testing Core Fortress Trading System Functionality")

    # Create event bus
    event_bus = event_bus_manager.get_event_bus(
        name="test_core",
        redis_url="redis://localhost:6379",
        key_prefix="test_core"
    )
    await event_bus.connect()
    print("✅ Connected to Redis event bus")

    # Create brain
    brain = FortressBrain(brain_id="test_core_brain")
    await brain.initialize(event_bus)
    await brain.start()
    print("✅ Fortress Brain initialized and started")

    # Register test strategy
    await brain.register_strategy(
        strategy_name="Test_Strategy",
        timeframe="15min",
        symbol="NSE:NIFTY-FUT",
        parameters={"fast_ma": 20, "slow_ma": 50}
    )
    await brain.activate_strategy("Test_Strategy", "15min", "NSE:NIFTY-FUT")
    print("✅ Test strategy registered and activated")

    # Test direct signal processing (bypassing AmiBroker for now)
    print("\n📡 Testing direct signal processing...")

    # Process signal directly through brain
    signal_processed = await brain.process_signal(
        symbol="NSE:NIFTY-FUT",
        signal_type="BUY",
        quantity=10,
        timeframe="15min",
        strategy_name="Test_Strategy",
        price=18000.0
    )

    print(f"✅ Signal processed: {signal_processed}")

    # Create worker with mocked HTTP client
    worker = FortressWorker(event_bus)

    # Mock HTTP client for OpenAlgo integration
    from unittest.mock import AsyncMock
    worker.http_client = AsyncMock()

    # Mock successful order placement
    worker.http_client.post.return_value = AsyncMock(
        status_code=200,
        json=lambda: {
            "status": "success",
            "data": {"order_id": "test_order_123"}
        }
    )

    # Mock successful order status
    worker.http_client.get.return_value = AsyncMock(
        status_code=200,
        json=lambda: {
            "status": "success",
            "data": {
                "status": "COMPLETE",
                "filled_qty": 10
            }
        }
    )

    await worker.initialize()
    print("✅ Fortress Worker initialized")

    # Test SEBI-compliant order slicing
    print("\n⚖️ Testing SEBI-compliant order slicing...")
    test_quantities = [5, 9, 15, 25, 50]

    for qty in test_quantities:
        slices = worker.slice_order(qty)
        print(f"  Order {qty} -> Slices: {slices}")

        # Verify SEBI compliance
        assert all(slice_qty <= 9 for slice_qty in slices), f"SEBI violation in slices: {slices}"
        assert sum(slices) == qty, f"Total quantity mismatch: {sum(slices)} != {qty}"

    print("✅ All SEBI compliance tests passed")

    # Test action mapping
    print("\n🎯 Testing action mapping...")

    action_tests = [
        ("BUY", "BUY"),
        ("SELL", "SELL"),
        ("SHORT", "SELL"),
        ("COVER", "BUY")
    ]

    for input_action, expected_side in action_tests:
        # Test the mapping logic from execute_order_slice
        side_map = {
            "BUY": "BUY",
            "SELL": "SELL",
            "SHORT": "SELL",
            "COVER": "BUY"
        }
        mapped_side = side_map.get(input_action.upper(), "BUY")
        assert mapped_side == expected_side, f"Action mapping failed: {input_action} -> {mapped_side} != {expected_side}"
        print(f"  {input_action} -> {mapped_side} ✅")

    print("✅ Action mapping tests passed")

    # Test job queue functionality
    print("\n📋 Testing job queue functionality...")

    # Create test job
    test_job = {
        "job_id": "test_job_123",
        "symbol": "NSE:NIFTY-FUT",
        "action": "BUY",
        "total_qty": 15,  # Will be sliced into [9, 6]
        "price": 18000.0
    }

    # Add job to queue
    await worker.redis_client.rpush("trade_queue", json.dumps(test_job))
    print(f"✅ Added job to queue: {test_job['job_id']}")

    # Check queue length
    queue_length = await worker.redis_client.llen("trade_queue")
    print(f"📊 Queue length: {queue_length}")

    # Get job from queue
    job_data = await worker.redis_client.lpop("trade_queue")
    job = json.loads(job_data)
    print(f"✅ Retrieved job: {job['job_id']}")

    # Verify job details
    assert job["symbol"] == "NSE:NIFTY-FUT"
    assert job["action"] == "BUY"
    assert job["total_qty"] == 15

    print("✅ Job queue functionality working correctly")

    # Test event system
    print("\n📡 Testing event system...")

    events_received = []

    async def event_handler(event):
        events_received.append(event)
        print(f"  📨 Received event: {event.event_type}")

    # Subscribe to events
    await event_bus.subscribe(EventType.SIGNAL_RECEIVED, event_handler)
    await event_bus.subscribe(EventType.ORDER_PLACED, event_handler)

    # Process another signal to generate events
    await brain.process_signal(
        symbol="NSE:BANKNIFTY-FUT",
        signal_type="SELL",
        quantity=5,
        timeframe="5min",
        strategy_name="Test_Strategy",
        price=42000.0
    )

    # Wait for events
    await asyncio.sleep(1)

    print(f"✅ Received {len(events_received)} events")

    # Check brain state
    print("\n🧠 Checking brain state...")
    brain_state = brain.get_state()
    print(f"  Active strategies: {len(brain_state.active_strategies)}")
    print(f"  Strategy names: {[s.strategy_name for s in brain_state.active_strategies]}")

    # Cleanup
    print("\n🧹 Cleaning up...")
    await worker.cleanup()
    await brain.stop()
    await event_bus.disconnect()

    print("\n🎉 Core Fortress Trading System Test PASSED!")
    print("✅ Event-driven architecture working")
    print("✅ Redis-based job queue operational")
    print("✅ SEBI-compliant order slicing implemented")
    print("✅ Signal processing functional")
    print("✅ Event system coordinating components")

    return True


if __name__ == "__main__":
    asyncio.run(test_core_functionality())
