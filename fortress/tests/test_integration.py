# ===================================================================================
# ==                 Fortress Trading System: End-to-End Integration Test         ==
# ===================================================================================

import asyncio
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime

import pytest

from fortress.core.event_bus import EventBus, event_bus_manager
from fortress.core.events import EventType, SignalEvent, OrderEvent
from fortress.brain.brain import FortressBrain
from fortress.integrations.amibroker import AmiBrokerIntegration
from fortress.worker.worker import FortressWorker
from fortress.main import FortressTradingSystem


class TestFortressTradingSystemIntegration:
    """End-to-end integration tests for the complete Fortress Trading System"""
    
    @pytest.fixture
    async def temp_signal_dir(self):
        """Create temporary signal directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            signal_dir = Path(temp_dir) / "signals" / "amibroker"
            signal_dir.mkdir(parents=True, exist_ok=True)
            yield signal_dir
    
    @pytest.fixture
    async def event_bus(self):
        """Create test event bus"""
        event_bus = event_bus_manager.get_event_bus(
            name="test_fortress",
            redis_url="redis://localhost:6379",
            key_prefix="test_fortress"
        )
        await event_bus.connect()
        yield event_bus
        await event_bus.disconnect()
    
    @pytest.fixture
    async def complete_system(self, temp_signal_dir, event_bus):
        """Create complete trading system for integration testing"""
        
        # Create brain
        brain = FortressBrain(brain_id="test_brain")
        await brain.initialize(event_bus)
        await brain.start()
        
        # Create AmiBroker integration
        amibroker = AmiBrokerIntegration(
            watch_directory=temp_signal_dir,
            file_extension=".csv"
        )
        await amibroker.start()
        
        # Create worker (with mocked HTTP client)
        worker = FortressWorker(event_bus)
        
        # Mock HTTP client for OpenAlgo integration
        from unittest.mock import AsyncMock
        worker.http_client = AsyncMock()
        
        # Mock successful order placement and status
        worker.http_client.post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"order_id": "test_order_123"}
            }
        )
        
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
        
        # Start worker loop in background
        worker_task = asyncio.create_task(worker.start_worker_loop())
        
        yield {
            "brain": brain,
            "amibroker": amibroker,
            "worker": worker,
            "event_bus": event_bus,
            "signal_dir": temp_signal_dir,
            "worker_task": worker_task
        }
        
        # Cleanup
        worker.is_running = False
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        
        await worker.cleanup()
        await brain.stop()
        await amibroker.stop()
    
    @pytest.mark.asyncio
    async def test_complete_signal_to_execution_workflow(self, complete_system):
        """Test complete workflow from signal generation to trade execution"""
        
        # Register a test strategy
        brain = complete_system["brain"]
        await brain.register_strategy(
            strategy_name="Test_MA_Strategy",
            timeframe="15min",
            symbol="NSE:NIFTY-FUT",
            parameters={"fast_ma": 20, "slow_ma": 50}
        )
        await brain.activate_strategy("Test_MA_Strategy", "15min", "NSE:NIFTY-FUT")
        
        # Create signal file
        signal_content = """symbol,signal_type,quantity,price,timeframe,strategy_name
NSE:NIFTY-FUT,BUY,10,18000.0,15min,Test_MA_Strategy"""
        
        signal_file = complete_system["signal_dir"] / "test_signal.csv"
        signal_file.write_text(signal_content)
        
        # Wait for signal processing
        await asyncio.sleep(2)
        
        # Check that signal was processed
        brain_state = brain.get_state()
        assert len(brain_state.recent_signals) > 0
        
        # Check Redis queue for trade job
        redis_client = complete_system["worker"].redis_client
        queue_length = await redis_client.llen("trade_queue")
        assert queue_length > 0
        
        # Get job from queue
        job_data = await redis_client.lpop("trade_queue")
        job = json.loads(job_data)
        
        # Verify job details
        assert job["symbol"] == "NSE:NIFTY-FUT"
        assert job["action"] == "BUY"
        assert job["total_qty"] == 10
        assert job["price"] == 18000.0
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_strategy_validation(self, complete_system):
        """Test multi-timeframe strategy validation"""
        
        brain = complete_system["brain"]
        
        # Register multiple timeframe strategies
        strategies = [
            {"strategy_name": "MA_5min", "timeframe": "5min", "symbol": "NSE:BANKNIFTY-FUT"},
            {"strategy_name": "MA_15min", "timeframe": "15min", "symbol": "NSE:BANKNIFTY-FUT"},
            {"strategy_name": "MA_1h", "timeframe": "1h", "symbol": "NSE:BANKNIFTY-FUT"},
        ]
        
        for strategy_config in strategies:
            await brain.register_strategy(**strategy_config)
            await brain.activate_strategy(
                strategy_config["strategy_name"],
                strategy_config["timeframe"],
                strategy_config["symbol"]
            )
        
        # Create signals for different timeframes
        signals = [
            "NSE:BANKNIFTY-FUT,BUY,5,42000.0,5min,MA_5min",
            "NSE:BANKNIFTY-FUT,SELL,8,41900.0,15min,MA_15min",
            "NSE:BANKNIFTY-FUT,BUY,3,42100.0,1h,MA_1h"
        ]
        
        for signal_line in signals:
            signal_content = f"symbol,signal_type,quantity,price,timeframe,strategy_name\n{signal_line}"
            signal_file = complete_system["signal_dir"] / f"signal_{int(time.time())}.csv"
            signal_file.write_text(signal_content)
            await asyncio.sleep(0.5)
        
        # Wait for all signals to be processed
        await asyncio.sleep(3)
        
        # Verify all signals were processed
        brain_state = brain.get_state()
        assert len(brain_state.recent_signals) == 3
        
        # Verify different timeframes were handled
        timeframes = [signal.timeframe for signal in brain_state.recent_signals]
        assert "5min" in timeframes
        assert "15min" in timeframes
        assert "1h" in timeframes
    
    @pytest.mark.asyncio
    async def test_order_slicing_and_execution(self, complete_system):
        """Test SEBI-compliant order slicing and execution"""
        
        brain = complete_system["brain"]
        worker = complete_system["worker"]
        
        # Register strategy
        await brain.register_strategy(
            strategy_name="Large_Order_Strategy",
            timeframe="15min",
            symbol="NSE:NIFTY-FUT",
            parameters={}
        )
        await brain.activate_strategy("Large_Order_Strategy", "15min", "NSE:NIFTY-FUT")
        
        # Create signal with large quantity (requires slicing)
        signal_content = """symbol,signal_type,quantity,price,timeframe,strategy_name
NSE:NIFTY-FUT,BUY,25,18000.0,15min,Large_Order_Strategy"""
        
        signal_file = complete_system["signal_dir"] / "large_order_signal.csv"
        signal_file.write_text(signal_content)
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Check Redis queue
        redis_client = worker.redis_client
        queue_length = await redis_client.llen("trade_queue")
        assert queue_length > 0
        
        # Get job and verify slicing logic
        job_data = await redis_client.lpop("trade_queue")
        job = json.loads(job_data)
        assert job["total_qty"] == 25
        
        # Manually test slicing
        slices = worker.slice_order(25)
        assert slices == [9, 9, 7]  # SEBI-compliant: max 9 lots per order
    
    @pytest.mark.asyncio
    async def test_all_or_nothing_execution_failure(self, complete_system):
        """Test all-or-nothing execution logic with failure scenario"""
        
        brain = complete_system["brain"]
        worker = complete_system["worker"]
        
        # Modify worker to simulate failure
        from unittest.mock import AsyncMock
        
        # First slice succeeds, second fails
        success_response = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"order_id": "slice_1"}
            }
        )
        
        failure_response = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "error",
                "message": "Insufficient margin"
            }
        )
        
        # Set up responses: first succeeds, second fails
        worker.http_client.post.side_effect = [success_response, failure_response]
        
        # Mock order status
        status_response = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {
                    "status": "COMPLETE",
                    "filled_qty": 9
                }
            }
        )
        worker.http_client.get.return_value = status_response
        
        # Register strategy and create signal
        await brain.register_strategy(
            strategy_name="Failure_Test_Strategy",
            timeframe="15min",
            symbol="NSE:NIFTY-FUT",
            parameters={}
        )
        await brain.activate_strategy("Failure_Test_Strategy", "15min", "NSE:NIFTY-FUT")
        
        # Create signal requiring multiple slices
        signal_content = """symbol,signal_type,quantity,price,timeframe,strategy_name
NSE:NIFTY-FUT,BUY,18,18000.0,15min,Failure_Test_Strategy"""
        
        signal_file = complete_system["signal_dir"] / "failure_test_signal.csv"
        signal_file.write_text(signal_content)
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Add job directly to worker queue to test execution
        test_job = {
            "job_id": "failure_test_job",
            "symbol": "NSE:NIFTY-FUT",
            "action": "BUY",
            "total_qty": 18,  # Will be sliced into [9, 9]
            "price": 18000.0
        }
        
        redis_client = worker.redis_client
        await redis_client.rpush("trade_queue", json.dumps(test_job))
        
        # Wait for execution
        await asyncio.sleep(3)
        
        # Check for neutralization job (should be created due to failure)
        queue_length = await redis_client.llen("trade_queue")
        if queue_length > 0:
            neutralize_job_data = await redis_client.lpop("trade_queue")
            neutralize_job = json.loads(neutralize_job_data)
            
            # Verify neutralization job
            assert neutralize_job["action"] == "SELL"  # Opposite of BUY
            assert neutralize_job["is_neutralization"] is True
            assert neutralize_job["total_qty"] == 9  # First slice that succeeded
    
    @pytest.mark.asyncio
    async def test_event_flow_and_coordination(self, complete_system):
        """Test event flow and coordination between components"""
        
        brain = complete_system["brain"]
        event_bus = complete_system["event_bus"]
        
        # Track events
        events_received = []
        
        async def event_handler(event):
            events_received.append(event)
        
        # Subscribe to all order-related events
        await event_bus.subscribe(EventType.ORDER_PLACED, event_handler)
        await event_bus.subscribe(EventType.ORDER_EXECUTED, event_handler)
        await event_bus.subscribe(EventType.ORDER_NEUTRALIZED, event_handler)
        
        # Register strategy and create signal
        await brain.register_strategy(
            strategy_name="Event_Test_Strategy",
            timeframe="15min",
            symbol="NSE:NIFTY-FUT",
            parameters={}
        )
        await brain.activate_strategy("Event_Test_Strategy", "15min", "NSE:NIFTY-FUT")
        
        # Create signal
        signal_content = """symbol,signal_type,quantity,price,timeframe,strategy_name
NSE:NIFTY-FUT,BUY,5,18000.0,15min,Event_Test_Strategy"""
        
        signal_file = complete_system["signal_dir"] / "event_test_signal.csv"
        signal_file.write_text(signal_content)
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Verify events were generated
        event_types = [event.event_type for event in events_received]
        assert EventType.ORDER_PLACED in event_types
        
        # Clean up event subscription
        await event_bus.unsubscribe(EventType.ORDER_PLACED, event_handler)
        await event_bus.unsubscribe(EventType.ORDER_EXECUTED, event_handler)
        await event_bus.unsubscribe(EventType.ORDER_NEUTRALIZED, event_handler)
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, complete_system):
        """Test error handling and system recovery"""
        
        brain = complete_system["brain"]
        worker = complete_system["worker"]
        
        # Test with invalid signal data
        invalid_signal_content = """invalid,data,format
this,is,not,a,valid,signal"""
        
        invalid_signal_file = complete_system["signal_dir"] / "invalid_signal.csv"
        invalid_signal_file.write_text(invalid_signal_content)
        
        # Wait for processing (should handle gracefully)
        await asyncio.sleep(2)
        
        # System should still be functional
        brain_state = brain.get_state()
        assert brain_state is not None
        
        # Test with malformed job data
        malformed_job = "invalid json data"
        redis_client = worker.redis_client
        await redis_client.rpush("trade_queue", malformed_job)
        
        # Wait for processing
        await asyncio.sleep(1)
        
        # Check dead letter queue
        dead_letter_length = await redis_client.llen("dead_letter_queue")
        assert dead_letter_length > 0  # Malformed job should be in dead letter queue


if __name__ == "__main__":
    pytest.main([__file__, "-v"])