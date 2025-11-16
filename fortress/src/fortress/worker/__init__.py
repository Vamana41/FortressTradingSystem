# ===================================================================================
# ==                 Fortress Trading System: Worker Integration                  ==
# ===================================================================================
#
# Integration module for the Fortress Worker within the main trading system
# Handles worker lifecycle management and coordination with other components
# ===================================================================================

import asyncio
from typing import Optional

from fortress.core.event_bus import EventBus
from fortress.core.logging import get_logger
from fortress.worker.worker import FortressWorker


class WorkerManager:
    """
    Manages the Fortress Worker lifecycle and integration with the trading system

    Responsibilities:
    - Worker initialization and cleanup
    - Event coordination between worker and other components
    - Health monitoring and restart logic
    - Error handling and recovery
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.logger = get_logger("fortress.worker_manager")
        self.worker: Optional[FortressWorker] = None
        self.worker_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def initialize(self) -> bool:
        """Initialize the worker manager and worker component"""
        try:
            self.logger.info("Initializing Worker Manager")

            # Create and initialize the worker
            self.worker = FortressWorker(self.event_bus)

            if not await self.worker.initialize():
                self.logger.error("Failed to initialize Fortress Worker")
                return False

            self.logger.info("Worker Manager initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize Worker Manager", error=str(e))
            return False

    async def start_worker(self) -> bool:
        """Start the worker in the background"""
        if not self.worker:
            self.logger.error("Worker not initialized")
            return False

        try:
            self.logger.info("Starting Fortress Worker")
            self.is_running = True

            # Start worker loop in background task
            self.worker_task = asyncio.create_task(self.worker.start_worker_loop())

            self.logger.info("Fortress Worker started successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to start worker", error=str(e))
            self.is_running = False
            return False

    async def stop_worker(self) -> bool:
        """Stop the worker gracefully"""
        if not self.worker_task or not self.is_running:
            self.logger.info("Worker not running")
            return True

        try:
            self.logger.info("Stopping Fortress Worker")
            self.is_running = False

            # Cancel the worker task
            if self.worker_task:
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling task

            # Cleanup worker resources
            if self.worker:
                await self.worker.cleanup()

            self.logger.info("Fortress Worker stopped successfully")
            return True

        except Exception as e:
            self.logger.error("Error stopping worker", error=str(e))
            return False

    async def get_worker_status(self) -> dict:
        """Get current worker status and health information"""
        return {
            "is_running": self.is_running,
            "worker_initialized": self.worker is not None,
            "task_running": self.worker_task is not None and not self.worker_task.done(),
            "task_cancelled": self.worker_task is not None and self.worker_task.cancelled(),
            "task_exception": str(self.worker_task.exception()) if self.worker_task and self.worker_task.done() and self.worker_task.exception() else None
        }

    async def restart_worker(self) -> bool:
        """Restart the worker if it's not functioning properly"""
        self.logger.info("Restarting Fortress Worker")

        # Stop current worker
        await self.stop_worker()

        # Re-initialize if needed
        if not await self.initialize():
            self.logger.error("Failed to re-initialize worker during restart")
            return False

        # Start worker again
        return await self.start_worker()

    async def cleanup(self) -> None:
        """Cleanup worker manager resources"""
        self.logger.info("Cleaning up Worker Manager")
        await self.stop_worker()
        self.logger.info("Worker Manager cleanup completed")


# Integration with main application
async def create_and_start_worker(event_bus: EventBus) -> Optional[WorkerManager]:
    """
    Create and start the worker manager as part of the main application

    Args:
        event_bus: Event bus instance for event coordination

    Returns:
        WorkerManager instance if successful, None otherwise
    """
    logger = get_logger("fortress.worker_integration")

    try:
        logger.info("Creating Worker Manager")

        # Create worker manager
        worker_manager = WorkerManager(event_bus)

        # Initialize worker
        if not await worker_manager.initialize():
            logger.error("Failed to initialize worker manager")
            return None

        # Start worker
        if not await worker_manager.start_worker():
            logger.error("Failed to start worker")
            await worker_manager.cleanup()
            return None

        logger.info("Worker Manager created and started successfully")
        return worker_manager

    except Exception as e:
        logger.error("Failed to create and start worker", error=str(e))
        return None
