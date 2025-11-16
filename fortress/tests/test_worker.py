# ===================================================================================
# ==                 Fortress Worker Integration Tests                            ==
# ===================================================================================

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from fortress.core.event_bus import EventBus
from fortress.core.events import EventType, OrderEvent, ErrorEvent
from fortress.worker.worker import FortressWorker


class TestFortressWorker:
    """Test suite for Fortress Worker component"""

    @pytest.fixture
    async def event_bus(self):
        """Create test event bus"""
        event_bus = EventBus()
        await event_bus.connect()
        yield event_bus
        await event_bus.disconnect()

    @pytest.fixture
    async def worker(self, event_bus):
        """Create test worker instance"""
        worker = FortressWorker(event_bus)

        # Mock Redis and HTTP clients
        worker.redis_client = AsyncMock()
        worker.http_client = AsyncMock()

        yield worker

        # Cleanup
        await worker.cleanup()

    @pytest.mark.asyncio
    async def test_worker_initialization(self, event_bus):
        """Test worker initialization"""
        worker = FortressWorker(event_bus)

        # Mock the clients
        with patch('redis.asyncio.Redis') as mock_redis, \
             patch('httpx.AsyncClient') as mock_http:

            mock_redis_instance = AsyncMock()
            mock_redis_instance.ping.return_value = True
            mock_redis.return_value = mock_redis_instance

            mock_http_instance = AsyncMock()
            mock_http.return_value = mock_http_instance

            # Test initialization
            result = await worker.initialize()

            assert result is True
            assert worker.redis_client is not None
            assert worker.http_client is not None

    @pytest.mark.asyncio
    async def test_order_slicing_sebi_compliance(self, worker):
        """Test SEBI-compliant order slicing (max 9 lots per order)"""
        # Test small order (no slicing needed)
        slices = worker.slice_order(5)
        assert slices == [5]

        # Test exact 9 lots
        slices = worker.slice_order(9)
        assert slices == [9]

        # Test larger order requiring multiple slices
        slices = worker.slice_order(25)
        assert slices == [9, 9, 7]

        # Test very large order
        slices = worker.slice_order(50)
        assert slices == [9, 9, 9, 9, 9, 5]

        # Verify all slices comply with SEBI limit
        for slice_qty in slices:
            assert slice_qty <= 9

        # Verify total quantity is preserved
        assert sum(slices) == 25

    @pytest.mark.asyncio
    async def test_successful_trade_execution(self, worker):
        """Test successful trade execution with all-or-nothing logic"""
        # Mock successful order placement
        worker.http_client.post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"order_id": "test_order_123"}
            }
        )

        # Mock successful order status polling
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

        # Test job
        job = {
            "job_id": "test_job_123",
            "symbol": "NSE:RELIANCE-EQ",
            "action": "BUY",
            "total_qty": 10,
            "price": 2500.0
        }

        # Execute trade
        result = await worker.execute_trade_job(job)

        assert result is True

        # Verify order was placed
        worker.http_client.post.assert_called_once()
        call_args = worker.http_client.post.call_args
        assert call_args[0][0] == "/orders/place"
        assert call_args[1]["json"]["symbol"] == "NSE:RELIANCE-EQ"
        assert call_args[1]["json"]["qty"] == 10

    @pytest.mark.asyncio
    async def test_failed_slice_neutralization(self, worker):
        """Test all-or-nothing logic when a slice fails"""
        # Mock first slice successful
        success_response = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"order_id": "slice_1"}
            }
        )

        # Mock second slice failed
        failure_response = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "error",
                "message": "Insufficient margin"
            }
        )

        # Mock order status polling
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

        # Set up responses: first call succeeds, second fails
        worker.http_client.post.side_effect = [success_response, failure_response]
        worker.http_client.get.return_value = status_response

        # Test job requiring multiple slices
        job = {
            "job_id": "test_job_fail",
            "symbol": "NSE:NIFTY-FUT",
            "action": "BUY",
            "total_qty": 15,  # Will be sliced into [9, 6]
            "price": 18000.0
        }

        # Execute trade (should fail due to second slice)
        result = await worker.execute_trade_job(job)

        assert result is False

        # Verify neutralization job was created
        worker.redis_client.rpush.assert_called_once()
        neutralize_call = worker.redis_client.rpush.call_args
        assert neutralize_call[0][0] == "trade_queue"

        # Parse neutralization job
        neutralize_job = json.loads(neutralize_call[0][1])
        assert neutralize_job["action"] == "SELL"  # Opposite of BUY
        assert neutralize_job["total_qty"] == 9  # First slice that succeeded
        assert neutralize_job["is_neutralization"] is True

    @pytest.mark.asyncio
    async def test_job_failure_handling(self, worker):
        """Test job failure handling and dead letter queue"""
        # Mock exception during execution
        worker.http_client.post.side_effect = Exception("Network error")

        # Test job
        job = {
            "job_id": "failing_job",
            "symbol": "NSE:TCS-EQ",
            "action": "SELL",
            "total_qty": 5,
            "price": 3200.0
        }

        # Execute trade (should fail)
        result = await worker.execute_trade_job(job)

        assert result is False

        # Verify job was moved to dead letter queue
        worker.redis_client.rpush.assert_called_once()
        dead_letter_call = worker.redis_client.rpush.call_args
        assert dead_letter_call[0][0] == "dead_letter_queue"
        assert json.loads(dead_letter_call[0][1]) == job

    @pytest.mark.asyncio
    async def test_order_status_polling_timeout(self, worker):
        """Test order status polling with timeout"""
        # Mock order placement success
        worker.http_client.post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"order_id": "timeout_order"}
            }
        )

        # Mock order status polling that never completes
        pending_response = AsyncMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {
                    "status": "PENDING",
                    "filled_qty": 0
                }
            }
        )
        worker.http_client.get.return_value = pending_response

        # Test order status polling (should timeout)
        filled_qty = await worker.poll_order_status("timeout_order")

        assert filled_qty == 0  # Should return 0 due to timeout

    @pytest.mark.asyncio
    async def test_worker_loop_job_processing(self, worker):
        """Test worker loop job processing"""
        # Mock successful job execution
        with patch.object(worker, 'execute_trade_job', return_value=True) as mock_execute:
            # Mock Redis job data
            job_data = ("trade_queue", json.dumps({
                "job_id": "loop_test_job",
                "symbol": "NSE:INFY-EQ",
                "action": "BUY",
                "total_qty": 20
            }))

            worker.redis_client.brpop.return_value = job_data

            # Run worker loop for one iteration
            worker.is_running = True

            # Create task for worker loop
            loop_task = asyncio.create_task(worker.start_worker_loop())

            # Let it process one job
            await asyncio.sleep(0.1)

            # Stop the loop
            worker.is_running = False
            loop_task.cancel()

            try:
                await loop_task
            except asyncio.CancelledError:
                pass

            # Verify job was executed
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_job_handling(self, worker):
        """Test handling of invalid job data"""
        # Mock invalid JSON
        job_data = ("trade_queue", "invalid json data")
        worker.redis_client.brpop.return_value = job_data

        # Should not crash, should move to dead letter queue
        try:
            await worker.start_worker_loop()
        except:
            pass  # Expected to handle gracefully

        # Verify invalid job was moved to dead letter queue
        worker.redis_client.rpush.assert_called_once()
        dead_letter_call = worker.redis_client.rpush.call_args
        assert dead_letter_call[0][0] == "dead_letter_queue"
        assert dead_letter_call[0][1] == "invalid json data"

    @pytest.mark.asyncio
    async def test_action_mapping(self, worker):
        """Test action mapping for different order types"""
        # Test BUY action
        result = await worker.execute_order_slice("NSE:RELIANCE-EQ", "BUY", 10, "test_buy")
        call_args = worker.http_client.post.call_args
        assert call_args[1]["json"]["side"] == "BUY"

        # Test SELL action
        result = await worker.execute_order_slice("NSE:RELIANCE-EQ", "SELL", 10, "test_sell")
        call_args = worker.http_client.post.call_args
        assert call_args[1]["json"]["side"] == "SELL"

        # Test SHORT action (maps to SELL)
        result = await worker.execute_order_slice("NSE:RELIANCE-EQ", "SHORT", 10, "test_short")
        call_args = worker.http_client.post.call_args
        assert call_args[1]["json"]["side"] == "SELL"

        # Test COVER action (maps to BUY)
        result = await worker.execute_order_slice("NSE:RELIANCE-EQ", "COVER", 10, "test_cover")
        call_args = worker.http_client.post.call_args
        assert call_args[1]["json"]["side"] == "BUY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
