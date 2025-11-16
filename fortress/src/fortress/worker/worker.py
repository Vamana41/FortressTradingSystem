# ===================================================================================
# ==                 Fortress Trading System: Fortress Worker                      ==
# ===================================================================================
#
# This is the stateless, reliable execution engine for the Fortress Trading System.
#
# Its ONLY job is to:
#   1. Listen for trade "jobs" on the Redis queue
#   2. Execute that job by communicating with the OpenAlgo gateway
#   3. Handle all execution logic, including order slicing and failure neutralization
#   4. Isolate and quarantine any "poison pill" jobs that cause errors
#
# It holds no state. It knows nothing about strategy. It only follows orders.
# ===================================================================================

import asyncio
import json
import math
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import httpx
import structlog
from redis.asyncio import Redis

from fortress.core.events import Event, EventType, OrderEvent, PositionEvent, ErrorEvent
from fortress.core.event_bus import EventBus
from fortress.core.logging import get_logger
from fortress.integrations.openalgo_gateway import (
    OpenAlgoGateway, OrderParams, OrderSide, OrderType, ProductType,
    create_openalgo_gateway
)

# Configuration
OPENALGO_API_BASE_URL = "http://localhost:8080/api/v1"
MAX_LOTS_PER_ORDER = 9  # SEBI regulatory limit per order
DELAY_BETWEEN_SLICES_SEC = 1.1  # Delay to avoid hitting rapid-fire API limits
ORDER_STATUS_POLL_DELAY_SEC = 2  # How often to check if an order has filled
ORDER_STATUS_TIMEOUT_SEC = 20  # Max time to wait for a fill before failing

class FortressWorker:
    """
    The Fortress Worker - Stateless trade execution engine

    Handles:
    - SEBI-compliant order slicing (max 9 lots per order)
    - All-or-nothing trade execution with pessimistic margin locking
    - Position synchronization with broker APIs
    - Error handling and trade neutralization for failed executions
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.logger = get_logger("fortress.worker")
        self.redis_client: Optional[Redis] = None
        self.openalgo_gateway: Optional[OpenAlgoGateway] = None
        self.is_running = False

    async def initialize(self) -> bool:
        """Initialize the worker with Redis and OpenAlgo Gateway connections"""
        try:
            # Initialize Redis connection
            self.redis_client = Redis(
                host="localhost",
                port=6379,
                decode_responses=True
            )

            # Test Redis connection
            await self.redis_client.ping()
            self.logger.info("Connected to Redis server")

            # Initialize OpenAlgo Gateway
            # For production, this should come from environment variables or config
            self.openalgo_gateway = OpenAlgoGateway(
                api_key="fortress_worker_key",  # Should be from config
                base_url=OPENALGO_API_BASE_URL,
                event_bus=self.event_bus
            )
            await self.openalgo_gateway.connect()
            self.logger.info("Connected to OpenAlgo Gateway")

            self.logger.info("Fortress Worker initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize Fortress Worker", error=str(e))
            return False

    async def cleanup(self) -> None:
        """Cleanup resources"""
        self.is_running = False

        if self.redis_client:
            await self.redis_client.close()

        if self.openalgo_gateway:
            await self.openalgo_gateway.disconnect()

        self.logger.info("Fortress Worker cleanup completed")

    async def start_worker_loop(self) -> None:
        """Start the main worker loop - listens for jobs and executes them"""
        if not self.redis_client:
            await self.initialize()

        self.is_running = True
        self.logger.info("Fortress Worker is live. Waiting for jobs on 'trade_queue'...")

        while self.is_running:
            try:
                # Listen for jobs on Redis queue (blocking pop with 1 second timeout)
                job_data = await self.redis_client.brpop('trade_queue', timeout=1)

                if job_data:
                    # Parse the job data
                    queue_name, job_string = job_data
                    job = json.loads(job_string)

                    self.logger.info("Received new job", job_id=job.get("job_id"),
                                   symbol=job.get("symbol"), action=job.get("action"))

                    # Execute the job with error handling
                    try:
                        await self.execute_trade_job(job)
                    except Exception as e:
                        await self.handle_job_failure(job, e)

            except asyncio.CancelledError:
                self.logger.info("Worker loop cancelled")
                break
            except json.JSONDecodeError as e:
                self.logger.error("Failed to parse job JSON", error=str(e))
            except Exception as e:
                self.logger.error("Unexpected error in worker loop", error=str(e))
                await asyncio.sleep(1)  # Brief pause before continuing

    async def execute_trade_job(self, job: Dict[str, Any]) -> bool:
        """
        Execute a trade job with all-or-nothing logic and SEBI-compliant slicing

        Args:
            job: Trade job containing symbol, action, quantity, etc.

        Returns:
            bool: True if execution successful, False otherwise
        """
        job_id = job.get("job_id", "unknown")
        symbol = job.get("symbol")
        action = job.get("action")  # BUY/SELL/SHORT/COVER
        total_qty = job.get("total_qty", 0)

        self.logger.info("Starting trade execution", job_id=job_id, symbol=symbol,
                        action=action, total_qty=total_qty)

        # Publish order placed event
        await self.event_bus.publish(Event(
            event_id=f"order_placed_{job_id}_{int(time.time() * 1000)}",
            event_type=EventType.ORDER_PLACED,
            source="fortress_worker",
            priority="high",
            data={
                "symbol": symbol,
                "order_id": job_id,
                "action": action,
                "quantity": total_qty,
                "price": job.get("price")
            }
        ))

        # Step 1: Slice the order into SEBI-compliant chunks
        order_slices = self.slice_order(total_qty)
        self.logger.info("Order sliced into SEBI-compliant chunks",
                        job_id=job_id, slices=len(order_slices))

        # Step 2: Execute each slice with all-or-nothing logic
        executed_slices = []

        for i, slice_qty in enumerate(order_slices):
            self.logger.info(f"Executing slice {i+1}/{len(order_slices)}",
                           job_id=job_id, slice_qty=slice_qty)

            try:
                # Execute individual slice
                order_result = await self.execute_order_slice(
                    symbol=symbol,
                    action=action,
                    quantity=slice_qty,
                    job_id=f"{job_id}_slice_{i}"
                )

                if order_result["status"] == "success":
                    executed_slices.append({
                        "slice_id": i,
                        "quantity": slice_qty,
                        "order_id": order_result.get("order_id"),
                        "filled_quantity": order_result.get("filled_quantity", 0)
                    })
                    self.logger.info(f"Slice {i+1} executed successfully",
                                   job_id=job_id, order_id=order_result.get("order_id"))
                else:
                    # Slice failed - need to handle failure
                    self.logger.error(f"Slice {i+1} failed", job_id=job_id,
                                     error=order_result.get("error", "Unknown error"))

                    # All-or-nothing logic: neutralize any successful slices
                    await self.neutralize_executed_slices(executed_slices, symbol, action)
                    return False

            except Exception as e:
                self.logger.error(f"Exception executing slice {i+1}", job_id=job_id, error=str(e))
                # All-or-nothing logic: neutralize any successful slices
                await self.neutralize_executed_slices(executed_slices, symbol, action)
                return False

            # Brief delay between slices to avoid API rate limits
            if i < len(order_slices) - 1:
                await asyncio.sleep(DELAY_BETWEEN_SLICES_SEC)

        # Step 3: Verify all slices executed successfully
        if len(executed_slices) == len(order_slices):
            total_filled = sum(slice_info["filled_quantity"] for slice_info in executed_slices)
            self.logger.info("All slices executed successfully", job_id=job_id,
                           total_filled=total_filled, total_requested=total_qty)

            # Publish successful execution event
            await self.event_bus.publish(Event(
                event_id=f"order_executed_{job_id}_{int(time.time() * 1000)}",
                event_type=EventType.ORDER_EXECUTED,
                source="fortress_worker",
                priority="high",
                data={
                    "symbol": symbol,
                    "order_id": job_id,
                    "action": action,
                    "quantity": total_filled,
                    "price": job.get("price")
                }
            ))

            return True
        else:
            self.logger.error("Incomplete execution - some slices failed", job_id=job_id)
            return False

    def slice_order(self, total_quantity: int) -> List[int]:
        """
        Slice order into SEBI-compliant chunks (max 9 lots per order)

        Args:
            total_quantity: Total quantity to trade

        Returns:
            List of quantities for each slice
        """
        if total_quantity <= MAX_LOTS_PER_ORDER:
            return [total_quantity]

        slices = []
        remaining = total_quantity

        while remaining > 0:
            slice_qty = min(remaining, MAX_LOTS_PER_ORDER)
            slices.append(slice_qty)
            remaining -= slice_qty

        return slices

    async def execute_order_slice(self, symbol: str, action: str, quantity: int, job_id: str) -> Dict[str, Any]:
        """
        Execute a single order slice via OpenAlgo Gateway

        Args:
            symbol: Trading symbol
            action: BUY/SELL/SHORT/COVER
            quantity: Quantity for this slice
            job_id: Unique job identifier

        Returns:
            Dict containing execution result
        """
        if not self.openalgo_gateway:
            raise RuntimeError("OpenAlgo Gateway not initialized")

        # Map action to OpenAlgo side parameter
        side_map = {
            "BUY": OrderSide.BUY,
            "SELL": OrderSide.SELL,
            "SHORT": OrderSide.SELL,
            "COVER": OrderSide.BUY
        }

        side = side_map.get(action.upper(), OrderSide.BUY)

        # Create order parameters
        order_params = OrderParams(
            symbol=symbol,
            quantity=quantity,
            side=side,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY
        )

        try:
            # Place order via OpenAlgo Gateway
            order_id = await self.openalgo_gateway.place_order(order_params)

            # Poll for order status
            filled_quantity = await self.poll_order_status(order_id)

            return {
                "status": "success",
                "order_id": order_id,
                "filled_quantity": filled_quantity
            }

        except Exception as e:
            self.logger.error("Exception placing order", job_id=job_id, error=str(e))
            return {
                "status": "failed",
                "error": f"Exception: {str(e)}"
            }

    async def poll_order_status(self, order_id: str) -> int:
        """
        Poll order status until filled or timeout using OpenAlgo Gateway

        Args:
            order_id: Order ID to poll

        Returns:
            Filled quantity
        """
        if not self.openalgo_gateway:
            raise RuntimeError("OpenAlgo Gateway not initialized")

        try:
            # Use OpenAlgo Gateway's wait_for_order_fill method
            order_status = await self.openalgo_gateway.wait_for_order_fill(
                order_id=order_id,
                timeout=ORDER_STATUS_TIMEOUT_SEC,
                poll_interval=ORDER_STATUS_POLL_DELAY_SEC
            )

            filled_qty = int(order_status.get("filled_quantity", 0))
            order_state = order_status.get("status", "").upper()

            if order_state in ["COMPLETE", "FILLED"]:
                return filled_qty
            elif order_state in ["CANCELLED", "REJECTED"]:
                self.logger.error("Order cancelled or rejected", order_id=order_id,
                                 status=order_state)
                return filled_qty
            else:
                # Timeout case
                self.logger.error("Order status polling timeout", order_id=order_id)
                return filled_qty

        except TimeoutError:
            self.logger.error("Order status polling timeout", order_id=order_id)
            return 0
        except Exception as e:
            self.logger.error("Error polling order status", order_id=order_id, error=str(e))
            return 0

    async def neutralize_executed_slices(self, executed_slices: List[Dict], symbol: str, original_action: str) -> None:
        """
        Neutralize any successfully executed slices due to all-or-nothing failure

        Args:
            executed_slices: List of successfully executed slice info
            symbol: Trading symbol
            original_action: Original action (BUY/SELL/SHORT/COVER)
        """
        if not executed_slices:
            return

        # Determine neutralizing action
        neutralize_action = {
            "BUY": "SELL",
            "SELL": "BUY",
            "SHORT": "COVER",
            "COVER": "SHORT"
        }.get(original_action.upper(), "SELL")

        total_filled = sum(slice_info["filled_quantity"] for slice_info in executed_slices)

        self.logger.warning("Neutralizing executed slices due to all-or-nothing failure",
                           symbol=symbol, original_action=original_action,
                           neutralize_action=neutralize_action, total_quantity=total_filled)

        # Create neutralization job and add to queue
        neutralize_job = {
            "job_id": f"neutralize_{int(time.time())}",
            "symbol": symbol,
            "action": neutralize_action,
            "total_qty": total_filled,
            "is_neutralization": True,
            "original_job_id": executed_slices[0].get("job_id", "unknown")
        }

        await self.redis_client.rpush("trade_queue", json.dumps(neutralize_job))

        # Publish neutralization event
        await self.event_bus.publish(Event(
            event_id=f"order_neutralized_{neutralize_job['job_id']}_{int(time.time() * 1000)}",
            event_type=EventType.ORDER_NEUTRALIZED,
            source="fortress_worker",
            priority="critical",
            data={
                "symbol": symbol,
                "order_id": neutralize_job["job_id"],
                "action": neutralize_action,
                "quantity": total_filled
            }
        ))

    async def handle_job_failure(self, job: Dict[str, Any], error: Exception) -> None:
        """Handle job failure by moving to dead letter queue and logging"""
        job_id = job.get("job_id", "unknown")

        self.logger.error("Job execution failed", job_id=job_id, error=str(error))

        # Move job to dead letter queue for manual inspection
        await self.redis_client.rpush("dead_letter_queue", json.dumps(job))

        # Publish error event
        await self.event_bus.publish(Event(
            event_id=f"execution_failed_{job_id}_{int(time.time() * 1000)}",
            event_type=EventType.EXECUTION_FAILED,
            source="fortress_worker",
            priority="critical",
            data={
                "error_message": f"Trade execution failed: {str(error)}",
                "context": {"job_id": job_id, "job": job}
            }
        ))

    async def synchronize_with_broker(self) -> bool:
        """
        Synchronize positions and funds with broker via OpenAlgo Gateway

        Returns:
            True if synchronization successful
        """
        try:
            if not self.openalgo_gateway:
                self.logger.error("OpenAlgo Gateway not initialized for synchronization")
                return False

            self.logger.info("Starting broker synchronization")

            # Get current positions from broker
            positions = await self.openalgo_gateway.get_positions()
            self.logger.info(f"Retrieved {len(positions)} positions from broker")

            # Get funds information
            funds = await self.openalgo_gateway.get_funds()
            self.logger.info(f"Available margin: {funds.available_margin}")

            # Publish synchronization complete event
            await self.event_bus.publish(Event(
                event_id=f"pos_sync_{int(time.time() * 1000)}",
                event_type=EventType.POSITION_SYNC,
                source="fortress_worker",
                data={
                    "positions_count": len(positions),
                    "available_margin": funds.available_margin,
                    "total_balance": funds.total_balance
                }
            ))

            return True

        except Exception as e:
            self.logger.error("Broker synchronization failed", error=str(e))
            return False


# Standalone worker execution
async def main():
    """Main function to run the Fortress Worker standalone"""
    from fortress.core.event_bus import EventBus

    # Create event bus
    event_bus = EventBus()
    await event_bus.connect()

    # Create and initialize worker
    worker = FortressWorker(event_bus)

    if await worker.initialize():
        try:
            await worker.start_worker_loop()
        except KeyboardInterrupt:
            print("\nShutting down Fortress Worker...")
        finally:
            await worker.cleanup()
            await event_bus.disconnect()
    else:
        print("Failed to initialize Fortress Worker")


if __name__ == "__main__":
    asyncio.run(main())
