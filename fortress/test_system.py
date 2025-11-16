#!/usr/bin/env python3
"""Test script for Fortress Trading System."""

import asyncio
import csv
import uuid
from datetime import datetime
from pathlib import Path

from fortress.core.events import EventType, create_signal_event
from fortress.core.event_bus import EventBus, event_bus_manager, publish_event
from fortress.core.logging import configure_structlog, get_logger
from fortress.brain.brain import FortressBrain
from fortress.integrations.amibroker import AmiBrokerIntegration, AmiBrokerSignal


logger = get_logger(__name__)


async def test_event_bus() -> None:
    """Test the event bus functionality."""
    logger.info("Testing event bus...")

    # Get event bus
    event_bus = event_bus_manager.get_event_bus("test")
    await event_bus.connect()

    # Test event publishing
    test_event = create_signal_event(
        event_id=str(uuid.uuid4()),
        source="test",
        symbol="NIFTY24NOVFUT",
        signal_type="BUY",
        quantity=50,
        timeframe="15min",
        strategy_name="MA_Crossover",
        price=25000.0,
    )

    success = await publish_event(test_event, "test")
    logger.info(f"Event publishing test: {'SUCCESS' if success else 'FAILED'}")

    # Get queue stats
    stats = await event_bus.get_queue_stats()
    logger.info(f"Queue stats: {stats}")

    await event_bus.disconnect()


async def test_brain() -> None:
    """Test the brain functionality."""
    logger.info("Testing brain...")

    # Create brain
    brain = FortressBrain("test")

    # Register test strategy
    await brain.register_strategy(
        strategy_name="MA_Crossover",
        timeframe="15min",
        symbol="NIFTY24NOVFUT",
        parameters={"fast_ma": 20, "slow_ma": 50},
    )

    # Activate strategy
    success = await brain.activate_strategy("MA_Crossover", "15min", "NIFTY24NOVFUT")
    logger.info(f"Strategy activation test: {'SUCCESS' if success else 'FAILED'}")

    # Get brain state
    state = brain.get_state()
    logger.info(f"Brain state: {state.model_dump()}")


async def test_amibroker_integration() -> None:
    """Test AmiBroker integration."""
    logger.info("Testing AmiBroker integration...")

    # Create test directories
    test_dir = Path("./test_signals")
    test_dir.mkdir(exist_ok=True)

    # Create integration
    integration = AmiBrokerIntegration(
        watch_directory=test_dir,
        file_extension=".csv",
    )

    # Create sample signals
    sample_signals = [
        AmiBrokerSignal(
            symbol="NIFTY24NOVFUT",
            signal_type="BUY",
            quantity=50,
            price=25000.0,
            timeframe="15min",
            strategy_name="MA_Crossover",
        ),
        AmiBrokerSignal(
            symbol="BANKNIFTY24NOVFUT",
            signal_type="SELL",
            quantity=25,
            price=52000.0,
            timeframe="5min",
            strategy_name="RSI_Strategy",
        ),
    ]

    # Create sample file
    sample_file = test_dir / "test_signals.csv"
    integration.create_sample_signal_file(sample_file, sample_signals)

    logger.info(f"Sample signal file created: {sample_file}")

    # Test signal parsing
    signals = await integration._read_signal_file(sample_file)
    logger.info(f"Parsed {len(signals)} signals from file")

    # Clean up
    import shutil
    shutil.rmtree(test_dir)


async def test_full_system() -> None:
    """Test the full system integration."""
    logger.info("Testing full system integration...")

    # Create test directories
    signal_dir = Path("./signals/amibroker")
    signal_dir.mkdir(parents=True, exist_ok=True)

    # Create event bus
    event_bus = event_bus_manager.get_event_bus("fortress")
    await event_bus.connect()

    # Create brain
    brain = FortressBrain("main")
    await brain.initialize(event_bus)
    await brain.start()

    # Create AmiBroker integration
    amibroker = AmiBrokerIntegration(
        watch_directory=signal_dir,
        file_extension=".csv",
    )
    await amibroker.start()

    # Create test signal file
    test_signals = [
        AmiBrokerSignal(
            symbol="NIFTY24NOVFUT",
            signal_type="BUY",
            quantity=50,
            price=25000.0,
            timeframe="15min",
            strategy_name="MA_Crossover",
        ),
    ]

    test_file = signal_dir / "test_integration.csv"
    amibroker.create_sample_signal_file(test_file, test_signals)

    # Wait a bit for processing
    await asyncio.sleep(2)

    # Check brain state
    state = brain.get_state()
    logger.info(f"Brain processed signals: {state.processed_signals}")

    # Get queue stats
    stats = await event_bus.get_queue_stats()
    logger.info(f"Final queue stats: {stats}")

    # Clean up
    await brain.stop()
    await amibroker.stop()
    await event_bus.disconnect()

    logger.info("Full system test completed")


async def main() -> None:
    """Run all tests."""
    configure_structlog(log_level="INFO", json_format=False)

    logger.info("Starting Fortress Trading System tests...")

    try:
        # Run individual tests
        await test_event_bus()
        await test_brain()
        await test_amibroker_integration()
        await test_full_system()

        logger.info("All tests completed successfully!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
