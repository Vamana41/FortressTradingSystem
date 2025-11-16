"""Main application entry point for Fortress Trading System."""

from __future__ import annotations

import asyncio
import signal
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

import structlog

from fortress.core.event_bus import EventBus, event_bus_manager, start_event_consumers
from fortress.core.logging import configure_structlog, get_logger
from fortress.brain.brain import FortressBrain
from fortress.integrations.amibroker import AmiBrokerIntegration
from fortress.integrations.openalgo_gateway import OpenAlgoGateway
from fortress.worker.worker import FortressWorker
from fortress.worker import WorkerManager
from fortress.dashboard.startup import initialize_dashboard_connection
from fortress.utils.api_key_manager import SecureAPIKeyManager
from fortress.utils.openalgo_api_manager import FortressOpenAlgoIntegration


logger = get_logger(__name__)


class FortressTradingSystem:
    """Main Fortress Trading System application."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the trading system."""
        self.config_path = config_path
        self.brain: Optional[FortressBrain] = None
        self.amibroker_integration: Optional[AmiBrokerIntegration] = None
        self.event_bus: Optional[EventBus] = None
        self.worker_manager: Optional[WorkerManager] = None
        self.openalgo_gateway: Optional[OpenAlgoGateway] = None
        self.openalgo_integration: Optional[FortressOpenAlgoIntegration] = None
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Configure logging
        configure_structlog(log_level="INFO", json_format=False)

        logger.info("Fortress Trading System initialized")

    async def start(self) -> None:
        """Start the trading system."""
        try:
            logger.info("Starting Fortress Trading System")

            # Initialize event bus
            self.event_bus = event_bus_manager.get_event_bus(
                name="fortress",
                redis_url="redis://localhost:6379",
                key_prefix="fortress",
            )
            await self.event_bus.connect()

            # Initialize OpenAlgo Gateway with automatic API key management
            await self._initialize_openalgo_gateway()

            logger.info("OpenAlgo Gateway connected successfully")

            # Initialize brain with OpenAlgo gateway
            self.brain = FortressBrain(brain_id="main")
            await self.brain.initialize(self.event_bus, self.openalgo_gateway)
            await self.brain.start()

            # Connect dashboard to brain
            await initialize_dashboard_connection(self.brain)
            logger.info("Dashboard connected to brain successfully")

            # Initialize Worker Manager with OpenAlgo gateway
            self.worker_manager = WorkerManager(
                event_bus=self.event_bus
            )
            await self.worker_manager.start_worker()
            logger.info("Worker Manager started successfully")

            # Initialize AmiBroker integration
            self.amibroker_integration = AmiBrokerIntegration(
                watch_directory=Path("./signals/amibroker"),
                file_extension=".csv",
            )
            await self.amibroker_integration.start()

            # Start event consumers
            await start_event_consumers("fortress")

            # Register sample strategies
            await self._register_sample_strategies()

            self._running = True
            logger.info("Fortress Trading System started successfully")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error("Failed to start trading system", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the trading system."""
        logger.info("Stopping Fortress Trading System")

        self._running = False

        # Stop components in reverse order
        if self.worker_manager:
            await self.worker_manager.stop()
            logger.info("Worker Manager stopped")

        if self.amibroker_integration:
            await self.amibroker_integration.stop()
            logger.info("AmiBroker integration stopped")

        if self.brain:
            await self.brain.stop()
            logger.info("Brain stopped")

        if self.openalgo_gateway:
            await self.openalgo_gateway.disconnect()
            logger.info("OpenAlgo Gateway disconnected")

        if self.event_bus:
            await self.event_bus.disconnect()
            logger.info("Event bus disconnected")

        # Signal shutdown complete
        self._shutdown_event.set()

    async def _initialize_openalgo_gateway(self) -> None:
        """Initialize OpenAlgo Gateway with automatic API key management."""
        logger.info("Initializing OpenAlgo Gateway with automatic API key management")

        # First try to get API key from secure storage or environment
        api_key_manager = SecureAPIKeyManager()
        api_key = api_key_manager.get_api_key("openalgo")

        if not api_key:
            # Fallback to environment variable if not found in secure storage
            api_key = os.getenv("OPENALGO_API_KEY", "your_openalgo_api_key")
            if api_key and api_key != "your_openalgo_api_key":
                # Store it securely for future use
                api_key_manager.store_api_key("openalgo", api_key)
                logger.info("OpenAlgo API key stored securely for future use")

        # Initialize OpenAlgo Gateway
        self.openalgo_gateway = OpenAlgoGateway(
            api_key=api_key,
            base_url=os.getenv("OPENALGO_BASE_URL", "http://localhost:5000/api/v1"),
            event_bus=self.event_bus
        )
        await self.openalgo_gateway.connect()

        # Setup automatic API key management
        self.openalgo_integration = FortressOpenAlgoIntegration(self.brain)

        # Check if we should try automatic key retrieval
        openalgo_username = os.getenv("OPENALGO_USERNAME")
        openalgo_password = os.getenv("OPENALGO_PASSWORD")

        if openalgo_username and openalgo_password:
            logger.info("Found OpenAlgo credentials, setting up automatic API key management...")
            try:
                # Try to get API key automatically
                new_api_key = await self.openalgo_integration.initialize(
                    openalgo_username, openalgo_password
                )
                if new_api_key and new_api_key != api_key:
                    # Update gateway with new API key
                    self.openalgo_gateway.api_key = new_api_key
                    logger.info(f"Updated OpenAlgo Gateway with automatically retrieved API key")
            except Exception as e:
                logger.warning(f"Automatic API key retrieval failed: {e}")
                logger.info("Continuing with existing API key or manual configuration")
        else:
            logger.info("No OpenAlgo credentials found in environment. Manual API key configuration required.")
            logger.info("To enable automatic API key management, set OPENALGO_USERNAME and OPENALGO_PASSWORD environment variables.")
            logger.info("Or use the get_openalgo_api_key.py script to retrieve and store the API key.")

        logger.info("Fortress Trading System stopped")

    async def _register_sample_strategies(self) -> None:
        """Register sample strategies for testing."""
        # Register sample strategies
        strategies = [
            {
                "strategy_name": "MA_Crossover",
                "timeframe": "15min",
                "symbol": "NIFTY24NOVFUT",
                "parameters": {
                    "fast_ma": 20,
                    "slow_ma": 50,
                    "ma_type": "EMA",
                },
            },
            {
                "strategy_name": "RSI_Strategy",
                "timeframe": "5min",
                "symbol": "BANKNIFTY24NOVFUT",
                "parameters": {
                    "rsi_period": 14,
                    "overbought": 70,
                    "oversold": 30,
                },
            },
            {
                "strategy_name": "MACD_Strategy",
                "timeframe": "1h",
                "symbol": "FINNIFTY24NOVFUT",
                "parameters": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                },
            },
        ]

        for strategy_config in strategies:
            await self.brain.register_strategy(**strategy_config)
            await self.brain.activate_strategy(
                strategy_config["strategy_name"],
                strategy_config["timeframe"],
                strategy_config["symbol"],
            )

            logger.info(
                "Sample strategy registered and activated",
                strategy_name=strategy_config["strategy_name"],
                timeframe=strategy_config["timeframe"],
                symbol=strategy_config["symbol"],
            )

    def is_running(self) -> bool:
        """Check if the system is running."""
        return self._running

    async def get_status(self) -> Dict[str, Any]:
        """Get system status."""
        status = {
            "running": self._running,
            "brain_connected": self.brain is not None,
            "amibroker_connected": self.amibroker_integration is not None,
            "event_bus_connected": self.event_bus is not None,
            "worker_connected": self.worker_manager is not None,
        }

        if self.worker_manager:
            status["worker_status"] = await self.worker_manager.get_worker_status()

        if self.brain:
            status["brain_state"] = self.brain.get_state().model_dump()

        if self.event_bus:
            try:
                status["queue_stats"] = await self.event_bus.get_queue_stats()
            except Exception as e:
                logger.warning("Failed to get queue stats", error=str(e))

        return status


async def main() -> None:
    """Main application entry point."""
    # Create trading system
    trading_system = FortressTradingSystem()

    # Set up signal handlers
    def signal_handler(sig: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info("Received shutdown signal", signal=sig)
        asyncio.create_task(trading_system.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start the system
        await trading_system.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await trading_system.stop()

    except Exception as e:
        logger.error("Application error", error=str(e))
        await trading_system.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Configure event loop for Windows
    if sys.platform == "win32":
        import winloop
        winloop.install()
    else:
        import uvloop
        uvloop.install()

    # Run the application
    asyncio.run(main())
