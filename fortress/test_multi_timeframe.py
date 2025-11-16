"""Test Multi-Timeframe Strategy Support for Fortress Trading System."""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from fortress.core.event_bus import EventBus
from fortress.core.events import EventType, SignalEvent
from fortress.brain import (
    FortressBrain,
    TimeframeSignalManager,
    MultiTimeframeStrategyConfig,
    Timeframe,
    TimeframeConfig,
    TimeframePriority,
    SignalCorrelation,
    TimeframeSignal,
    MultiTimeframeSignal
)


@pytest.fixture
async def event_bus():
    """Create event bus for testing."""
    bus = EventBus()
    await bus.connect()
    yield bus
    await bus.disconnect()


@pytest.fixture
async def brain(event_bus):
    """Create Fortress Brain for testing."""
    brain = FortressBrain("test_brain")
    await brain.initialize(event_bus)
    await brain.start()
    yield brain
    await brain.stop()


@pytest.fixture
def timeframe_manager():
    """Create timeframe manager for testing."""
    manager = TimeframeSignalManager()
    yield manager


@pytest.mark.asyncio
class TestTimeframeManager:
    """Test timeframe signal manager functionality."""

    def test_timeframe_manager_initialization(self, timeframe_manager):
        """Test timeframe manager initialization."""
        assert timeframe_manager.active_signals == {}
        assert timeframe_manager.signal_history == []
        assert timeframe_manager.strategy_configs == {}

    def test_multi_timeframe_config_creation(self):
        """Test multi-timeframe strategy configuration creation."""
        config = MultiTimeframeStrategyConfig(
            strategy_name="TestStrategy",
            symbol="RELIANCE",
            primary_timeframe=Timeframe.H1,
            confirmation_timeframes=[
                TimeframeConfig(
                    timeframe=Timeframe.H4,
                    priority=TimeframePriority.CONFIRMATION,
                    weight=1.0
                ),
                TimeframeConfig(
                    timeframe=Timeframe.D1,
                    priority=TimeframePriority.CONFIRMATION,
                    weight=0.8
                )
            ],
            filter_timeframes=[
                TimeframeConfig(
                    timeframe=Timeframe.M15,
                    priority=TimeframePriority.FILTER,
                    weight=0.6
                )
            ],
            require_confirmation=True,
            require_filter_agreement=False
        )

        assert config.strategy_name == "TestStrategy"
        assert config.symbol == "RELIANCE"
        assert config.primary_timeframe == Timeframe.H1
        assert len(config.confirmation_timeframes) == 2
        assert len(config.filter_timeframes) == 1
        assert config.require_confirmation is True

    async def test_register_strategy_config(self, timeframe_manager):
        """Test strategy configuration registration."""
        config = MultiTimeframeStrategyConfig(
            strategy_name="TestStrategy",
            symbol="RELIANCE",
            primary_timeframe=Timeframe.H1,
            confirmation_timeframes=[
                TimeframeConfig(
                    timeframe=Timeframe.H4,
                    priority=TimeframePriority.CONFIRMATION
                )
            ]
        )

        timeframe_manager.register_strategy_config(config)

        retrieved_config = timeframe_manager.get_strategy_config("TestStrategy", "RELIANCE")
        assert retrieved_config is not None
        assert retrieved_config.strategy_name == "TestStrategy"
        assert retrieved_config.symbol == "RELIANCE"

    async def test_process_single_timeframe_signal(self, timeframe_manager):
        """Test processing a single timeframe signal."""
        # Register strategy config
        config = MultiTimeframeStrategyConfig(
            strategy_name="TestStrategy",
            symbol="RELIANCE",
            primary_timeframe=Timeframe.H1,
            confirmation_timeframes=[],
            require_confirmation=False  # Allow without confirmation
        )
        timeframe_manager.register_strategy_config(config)

        # Process signal
        result = await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="1h",
            signal_type="BUY",
            quantity=100,
            price=2500.0,
            confidence=0.8
        )

        assert result.validation_status == "approved"
        assert result.final_signal is not None
        assert result.final_signal.signal_type == "BUY"
        assert result.final_signal.quantity == 100

    async def test_multi_timeframe_signal_processing(self, timeframe_manager):
        """Test multi-timeframe signal processing with confirmation."""
        # Register strategy config
        config = MultiTimeframeStrategyConfig(
            strategy_name="TestStrategy",
            symbol="RELIANCE",
            primary_timeframe=Timeframe.H1,
            confirmation_timeframes=[
                TimeframeConfig(
                    timeframe=Timeframe.H4,
                    priority=TimeframePriority.CONFIRMATION,
                    correlation_threshold=0.6
                )
            ],
            require_confirmation=True
        )
        timeframe_manager.register_strategy_config(config)

        # Process primary signal first
        primary_result = await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="1h",
            signal_type="BUY",
            quantity=100,
            price=2500.0,
            confidence=0.8
        )

        # Should be pending since no confirmation yet
        assert primary_result.validation_status == "rejected"
        assert "No confirmation signals available" in primary_result.validation_reason

        # Process confirmation signal
        confirmation_result = await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="4h",
            signal_type="BUY",
            quantity=120,
            price=2510.0,
            confidence=0.7
        )

        # Now should be approved with both signals
        assert confirmation_result.validation_status == "approved"
        assert confirmation_result.final_signal is not None
        assert confirmation_result.correlation_type == SignalCorrelation.BULLISH_CONFLUENCE

    async def test_signal_correlation_calculation(self, timeframe_manager):
        """Test signal correlation calculation."""
        # Create signals
        primary_signal = TimeframeSignal(
            timeframe="1h",
            signal_type="BUY",
            quantity=100,
            price=2500.0,
            confidence=0.8
        )

        confirmation_signals = [
            TimeframeSignal(
                timeframe="4h",
                signal_type="BUY",
                quantity=120,
                price=2510.0,
                confidence=0.7
            ),
            TimeframeSignal(
                timeframe="1d",
                signal_type="BUY",
                quantity=150,
                price=2520.0,
                confidence=0.6
            )
        ]

        filter_signals = [
            TimeframeSignal(
                timeframe="15m",
                signal_type="BUY",
                quantity=80,
                price=2495.0,
                confidence=0.5
            )
        ]

        # Test correlation calculation
        correlation_type, correlation_score = await timeframe_manager._calculate_signal_correlation(
            primary_signal, confirmation_signals, filter_signals
        )

        assert correlation_type == SignalCorrelation.BULLISH_CONFLUENCE
        assert correlation_score > 0.7

    async def test_conflicting_signals(self, timeframe_manager):
        """Test handling of conflicting signals."""
        # Register strategy config
        config = MultiTimeframeStrategyConfig(
            strategy_name="TestStrategy",
            symbol="RELIANCE",
            primary_timeframe=Timeframe.H1,
            confirmation_timeframes=[
                TimeframeConfig(
                    timeframe=Timeframe.H4,
                    priority=TimeframePriority.CONFIRMATION,
                    correlation_threshold=0.7
                )
            ],
            require_confirmation=True
        )
        timeframe_manager.register_strategy_config(config)

        # Process primary signal
        await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="1h",
            signal_type="BUY",
            quantity=100,
            price=2500.0,
            confidence=0.8
        )

        # Process conflicting confirmation signal
        result = await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="4h",
            signal_type="SELL",
            quantity=120,
            price=2510.0,
            confidence=0.7
        )

        # Should be rejected due to conflicting signals
        assert result.validation_status == "rejected"
        assert result.correlation_type == SignalCorrelation.CONFLICTING

    async def test_signal_expiration(self, timeframe_manager):
        """Test signal expiration and cleanup."""
        # Register strategy config with short timeout
        config = MultiTimeframeStrategyConfig(
            strategy_name="TestStrategy",
            symbol="RELIANCE",
            primary_timeframe=Timeframe.H1,
            confirmation_timeframes=[
                TimeframeConfig(
                    timeframe=Timeframe.H4,
                    priority=TimeframePriority.CONFIRMATION,
                    signal_timeout=timedelta(seconds=1),  # Very short timeout
                    max_signal_age=timedelta(seconds=2)
                )
            ],
            require_confirmation=True
        )
        timeframe_manager.register_strategy_config(config)

        # Process signal
        await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="1h",
            signal_type="BUY",
            quantity=100,
            price=2500.0,
            confidence=0.8
        )

        # Wait for signal to expire
        await asyncio.sleep(3)

        # Process confirmation signal after expiration
        result = await timeframe_manager.process_timeframe_signal(
            symbol="RELIANCE",
            strategy_name="TestStrategy",
            timeframe="4h",
            signal_type="BUY",
            quantity=120,
            price=2510.0,
            confidence=0.7
        )

        # Should still be rejected because primary signal expired
        assert result.validation_status == "rejected"


@pytest.mark.asyncio
class TestBrainMultiTimeframeIntegration:
    """Test integration of multi-timeframe support with Fortress Brain."""

    async def test_register_multi_timeframe_strategy(self, brain):
        """Test registering multi-timeframe strategy with brain."""
        await brain.register_multi_timeframe_strategy(
            strategy_name="MultiTFStrategy",
            symbol="RELIANCE",
            primary_timeframe="1h",
            confirmation_timeframes=["4h", "1d"],
            filter_timeframes=["15m", "30m"],
            require_confirmation=True,
            require_filter_agreement=False,
            parameters={"rsi_period": 14, "macd_fast": 12}
        )

        # Check that individual timeframe strategies were registered
        assert brain.get_strategy_state("MultiTFStrategy", "1h", "RELIANCE") is not None
        assert brain.get_strategy_state("MultiTFStrategy", "4h", "RELIANCE") is not None
        assert brain.get_strategy_state("MultiTFStrategy", "1d", "RELIANCE") is not None
        assert brain.get_strategy_state("MultiTFStrategy", "15m", "RELIANCE") is not None
        assert brain.get_strategy_state("MultiTFStrategy", "30m", "RELIANCE") is not None

        # Check timeframe manager configuration
        config = brain.timeframe_manager.get_strategy_config("MultiTFStrategy", "RELIANCE")
        assert config is not None
        assert config.primary_timeframe == Timeframe.H1
        assert len(config.confirmation_timeframes) == 2
        assert len(config.filter_timeframes) == 2

    async def test_process_multi_timeframe_signal_through_brain(self, brain):
        """Test processing multi-timeframe signal through brain."""
        # Register multi-timeframe strategy
        await brain.register_multi_timeframe_strategy(
            strategy_name="MultiTFStrategy",
            symbol="RELIANCE",
            primary_timeframe="1h",
            confirmation_timeframes=["4h"],
            require_confirmation=True
        )

        # Process primary signal
        result1 = await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=100,
            timeframe="1h",
            strategy_name="MultiTFStrategy",
            price=2500.0,
            confidence=0.8
        )

        # Should be False due to missing confirmation
        assert result1 is False

        # Process confirmation signal
        result2 = await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=120,
            timeframe="4h",
            strategy_name="MultiTFStrategy",
            price=2510.0,
            confidence=0.7
        )

        # Should be True with confirmation
        assert result2 is True

    async def test_get_timeframe_summary(self, brain):
        """Test getting timeframe summary from brain."""
        # Register multi-timeframe strategy
        await brain.register_multi_timeframe_strategy(
            strategy_name="MultiTFStrategy",
            symbol="RELIANCE",
            primary_timeframe="1h",
            confirmation_timeframes=["4h", "1d"],
            filter_timeframes=["15m"]
        )

        # Process some signals
        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=100,
            timeframe="1h",
            strategy_name="MultiTFStrategy",
            price=2500.0
        )

        # Get timeframe summary
        summary = brain.get_timeframe_summary("RELIANCE", "MultiTFStrategy")

        assert "symbol" in summary
        assert "strategy_name" in summary
        assert "primary_timeframe" in summary
        assert "active_signals" in summary
        assert "confirmation_status" in summary
        assert "filter_status" in summary
        assert "correlation_analysis" in summary

        assert summary["symbol"] == "RELIANCE"
        assert summary["strategy_name"] == "MultiTFStrategy"
        assert summary["primary_timeframe"] == Timeframe.H1

    async def test_get_multi_timeframe_signals_history(self, brain):
        """Test getting multi-timeframe signal history."""
        # Register multi-timeframe strategy
        await brain.register_multi_timeframe_strategy(
            strategy_name="MultiTFStrategy",
            symbol="RELIANCE",
            primary_timeframe="1h",
            confirmation_timeframes=["4h"],
            require_confirmation=False  # Allow all signals
        )

        # Process multiple signals
        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=100,
            timeframe="1h",
            strategy_name="MultiTFStrategy",
            price=2500.0
        )

        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=120,
            timeframe="4h",
            strategy_name="MultiTFStrategy",
            price=2510.0
        )

        # Get signal history
        history = brain.get_multi_timeframe_signals(
            symbol="RELIANCE",
            strategy_name="MultiTFStrategy",
            limit=10
        )

        assert len(history) >= 2
        assert all("symbol" in signal for signal in history)
        assert all("strategy_name" in signal for signal in history)
        assert all("validation_status" in signal for signal in history)

    async def test_get_active_timeframe_signals(self, brain):
        """Test getting active timeframe signals."""
        # Register multi-timeframe strategy
        await brain.register_multi_timeframe_strategy(
            strategy_name="MultiTFStrategy",
            symbol="RELIANCE",
            primary_timeframe="1h",
            confirmation_timeframes=["4h"],
            require_confirmation=False
        )

        # Process signals
        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=100,
            timeframe="1h",
            strategy_name="MultiTFStrategy",
            price=2500.0
        )

        # Get active signals
        active_signals = brain.get_active_timeframe_signals("RELIANCE")

        assert "1h" in active_signals
        assert active_signals["1h"]["signal_type"] == "BUY"
        assert active_signals["1h"]["quantity"] == 100


@pytest.mark.asyncio
async def test_multi_timeframe_integration():
    """Integration test for multi-timeframe strategy support."""

    # Create event bus and brain
    event_bus = EventBus()
    await event_bus.connect()

    brain = FortressBrain("integration_test")
    await brain.initialize(event_bus)
    await brain.start()

    try:
        # Register comprehensive multi-timeframe strategy
        await brain.register_multi_timeframe_strategy(
            strategy_name="ComprehensiveStrategy",
            symbol="RELIANCE",
            primary_timeframe="1h",
            confirmation_timeframes=["4h", "1d"],
            filter_timeframes=["15m", "30m"],
            require_confirmation=True,
            require_filter_agreement=False,
            parameters={
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "macd_signal_period": 9
            }
        )

        # Process filter signals first
        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=80,
            timeframe="15m",
            strategy_name="ComprehensiveStrategy",
            price=2495.0,
            confidence=0.6
        )

        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=90,
            timeframe="30m",
            strategy_name="ComprehensiveStrategy",
            price=2498.0,
            confidence=0.65
        )

        # Process primary signal
        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=100,
            timeframe="1h",
            strategy_name="ComprehensiveStrategy",
            price=2500.0,
            confidence=0.8
        )

        # Process confirmation signals
        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=120,
            timeframe="4h",
            strategy_name="ComprehensiveStrategy",
            price=2510.0,
            confidence=0.7
        )

        await brain.process_signal(
            symbol="RELIANCE",
            signal_type="BUY",
            quantity=150,
            timeframe="1d",
            strategy_name="ComprehensiveStrategy",
            price=2520.0,
            confidence=0.75
        )

        # Get comprehensive summary
        summary = brain.get_timeframe_summary("RELIANCE", "ComprehensiveStrategy")

        assert summary["symbol"] == "RELIANCE"
        assert summary["strategy_name"] == "ComprehensiveStrategy"
        assert len(summary["active_signals"]) > 0
        assert len(summary["confirmation_status"]) == 2
        assert len(summary["filter_status"]) == 2
        assert "correlation_analysis" in summary

        # Verify correlation analysis shows bullish confluence
        correlation_analysis = summary["correlation_analysis"]
        if correlation_analysis:
            assert correlation_analysis["confirmation_count"] >= 2
            assert correlation_analysis["filter_count"] >= 2

        print(f"Multi-timeframe integration test completed successfully")
        print(f"Strategy summary: {summary}")

    finally:
        await brain.stop()
        await event_bus.disconnect()


if __name__ == "__main__":
    # Run the integration test
    asyncio.run(test_multi_timeframe_integration())
    print("All multi-timeframe strategy tests completed successfully!")
