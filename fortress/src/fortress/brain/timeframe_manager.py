"""Multi-Timeframe Strategy Support for Fortress Trading System.

Implements comprehensive multi-timeframe strategy management including:
- Timeframe-specific strategy parameters
- Cross-timeframe signal validation
- Timeframe hierarchy and priority
- Signal correlation and confirmation
- Multi-timeframe risk management
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

import structlog
from pydantic import BaseModel, Field

from ..core.events import Event, EventType, SignalEvent, create_signal_event, create_error_event
from ..core.event_bus import publish_event
from ..core.logging import get_brain_logger, TradingContext

logger = get_brain_logger()


class Timeframe(str, Enum):
    """Standard trading timeframes."""

    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H8 = "8h"
    H12 = "12h"
    D1 = "1d"
    D3 = "3d"
    W1 = "1w"
    MN1 = "1M"


class TimeframePriority(str, Enum):
    """Timeframe priority levels for signal validation."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONFIRMATION = "confirmation"
    FILTER = "filter"


class SignalCorrelation(str, Enum):
    """Signal correlation types across timeframes."""

    BULLISH_CONFLUENCE = "bullish_confluence"
    BEARISH_CONFLUENCE = "bearish_confluence"
    BULLISH_DIVERGENCE = "bullish_divergence"
    BEARISH_DIVERGENCE = "bearish_divergence"
    NEUTRAL = "neutral"
    CONFLICTING = "conflicting"


@dataclass
class TimeframeConfig:
    """Configuration for a specific timeframe within a strategy."""

    timeframe: Timeframe
    priority: TimeframePriority
    weight: float = 1.0
    signal_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    max_signal_age: timedelta = field(default_factory=lambda: timedelta(minutes=60))
    correlation_threshold: float = 0.7
    min_confirmation_timeframes: int = 1
    max_confirmation_timeframes: int = 3

    # Strategy-specific parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Risk parameters
    risk_multiplier: float = 1.0
    position_size_factor: float = 1.0
    stop_loss_multiplier: float = 1.0
    take_profit_multiplier: float = 1.0


@dataclass
class MultiTimeframeStrategyConfig:
    """Configuration for multi-timeframe strategy."""

    strategy_name: str
    symbol: str
    primary_timeframe: Timeframe
    confirmation_timeframes: List[TimeframeConfig] = field(default_factory=list)
    filter_timeframes: List[TimeframeConfig] = field(default_factory=list)

    # Validation rules
    require_confirmation: bool = True
    require_filter_agreement: bool = False
    max_timeframe_divergence: timedelta = field(default_factory=lambda: timedelta(hours=4))
    correlation_weight: float = 0.5

    # Risk management
    risk_scaling_enabled: bool = True
    risk_scaling_factor: float = 0.1
    max_risk_multiplier: float = 2.0
    min_risk_multiplier: float = 0.5


class TimeframeSignal(BaseModel):
    """Signal data for a specific timeframe."""

    timeframe: str
    signal_type: str
    quantity: int
    price: Optional[float] = None
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class MultiTimeframeSignal(BaseModel):
    """Multi-timeframe signal with correlation analysis."""

    symbol: str
    strategy_name: str
    primary_signal: TimeframeSignal
    confirmation_signals: List[TimeframeSignal] = Field(default_factory=list)
    filter_signals: List[TimeframeSignal] = Field(default_factory=list)
    correlation_type: SignalCorrelation = SignalCorrelation.NEUTRAL
    correlation_score: float = 0.0
    final_signal: Optional[TimeframeSignal] = None
    validation_status: str = "pending"
    validation_reason: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class TimeframeSignalManager:
    """Manages timeframe-specific signals and their validation."""

    def __init__(self):
        self.active_signals: Dict[str, Dict[str, TimeframeSignal]] = {}  # symbol -> timeframe -> signal
        self.signal_history: List[MultiTimeframeSignal] = []
        self.strategy_configs: Dict[str, MultiTimeframeStrategyConfig] = {}
        self._signal_cleanup_task: Optional[asyncio.Task] = None

        logger.info("TimeframeSignalManager initialized")

    async def start(self) -> None:
        """Start the signal manager with cleanup task."""
        self._signal_cleanup_task = asyncio.create_task(self._cleanup_expired_signals())
        logger.info("TimeframeSignalManager started")

    async def stop(self) -> None:
        """Stop the signal manager."""
        if self._signal_cleanup_task:
            self._signal_cleanup_task.cancel()
            try:
                await self._signal_cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("TimeframeSignalManager stopped")

    def register_strategy_config(self, config: MultiTimeframeStrategyConfig) -> None:
        """Register multi-timeframe strategy configuration."""
        key = f"{config.strategy_name}:{config.symbol}"
        self.strategy_configs[key] = config

        # Initialize signal storage for this strategy
        if config.symbol not in self.active_signals:
            self.active_signals[config.symbol] = {}

        logger.info(
            "Multi-timeframe strategy registered",
            strategy_name=config.strategy_name,
            symbol=config.symbol,
            primary_timeframe=config.primary_timeframe,
            confirmation_timeframes=[tf.timeframe for tf in config.confirmation_timeframes],
            filter_timeframes=[tf.timeframe for tf in config.filter_timeframes]
        )

    async def process_timeframe_signal(
        self,
        symbol: str,
        strategy_name: str,
        timeframe: str,
        signal_type: str,
        quantity: int,
        price: Optional[float] = None,
        confidence: float = 1.0,
        parameters: Optional[Dict[str, Any]] = None
    ) -> MultiTimeframeSignal:
        """Process a signal from a specific timeframe."""

        with TradingContext(
            symbol=symbol,
            signal_type=signal_type,
            strategy=strategy_name,
            timeframe=timeframe,
        ):
            logger.info(
                "Processing timeframe signal",
                symbol=symbol,
                strategy_name=strategy_name,
                timeframe=timeframe,
                signal_type=signal_type,
                quantity=quantity,
                price=price,
                confidence=confidence
            )

            # Get strategy configuration
            config_key = f"{strategy_name}:{symbol}"
            config = self.strategy_configs.get(config_key)

            if not config:
                logger.error("Strategy configuration not found", config_key=config_key)
                raise ValueError(f"Strategy configuration not found: {config_key}")

            # Create timeframe signal
            timeframe_signal = TimeframeSignal(
                timeframe=timeframe,
                signal_type=signal_type,
                quantity=quantity,
                price=price,
                confidence=confidence,
                parameters=parameters or {}
            )

            # Store signal
            if symbol not in self.active_signals:
                self.active_signals[symbol] = {}
            self.active_signals[symbol][timeframe] = timeframe_signal

            # Build multi-timeframe signal
            multi_signal = await self._build_multi_timeframe_signal(symbol, strategy_name, timeframe_signal)

            # Validate signal
            validation_result = await self._validate_multi_timeframe_signal(multi_signal, config)
            multi_signal.validation_status = validation_result["status"]
            multi_signal.validation_reason = validation_result["reason"]

            if validation_result["status"] == "approved":
                # Calculate final signal
                final_signal = await self._calculate_final_signal(multi_signal, config)
                multi_signal.final_signal = final_signal

                logger.info(
                    "Multi-timeframe signal approved",
                    symbol=symbol,
                    strategy_name=strategy_name,
                    correlation_type=multi_signal.correlation_type,
                    correlation_score=multi_signal.correlation_score,
                    final_quantity=final_signal.quantity if final_signal else None
                )
            else:
                logger.warning(
                    "Multi-timeframe signal rejected",
                    symbol=symbol,
                    strategy_name=strategy_name,
                    reason=validation_result["reason"]
                )

            # Store in history
            self.signal_history.append(multi_signal)

            # Keep history manageable
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]

            return multi_signal

    async def _build_multi_timeframe_signal(
        self,
        symbol: str,
        strategy_name: str,
        primary_signal: TimeframeSignal
    ) -> MultiTimeframeSignal:
        """Build multi-timeframe signal with existing signals."""

        config_key = f"{strategy_name}:{symbol}"
        config = self.strategy_configs[config_key]

        # Get confirmation signals
        confirmation_signals = []
        for tf_config in config.confirmation_timeframes:
            if tf_config.timeframe.value in self.active_signals.get(symbol, {}):
                signal = self.active_signals[symbol][tf_config.timeframe.value]
                # Check if signal is recent enough
                if datetime.utcnow() - signal.timestamp <= tf_config.signal_timeout:
                    confirmation_signals.append(signal)

        # Get filter signals
        filter_signals = []
        for tf_config in config.filter_timeframes:
            if tf_config.timeframe.value in self.active_signals.get(symbol, {}):
                signal = self.active_signals[symbol][tf_config.timeframe.value]
                # Check if signal is recent enough
                if datetime.utcnow() - signal.timestamp <= tf_config.signal_timeout:
                    filter_signals.append(signal)

        # Calculate correlation
        correlation_type, correlation_score = await self._calculate_signal_correlation(
            primary_signal, confirmation_signals, filter_signals
        )

        return MultiTimeframeSignal(
            symbol=symbol,
            strategy_name=strategy_name,
            primary_signal=primary_signal,
            confirmation_signals=confirmation_signals,
            filter_signals=filter_signals,
            correlation_type=correlation_type,
            correlation_score=correlation_score
        )

    async def _calculate_signal_correlation(
        self,
        primary_signal: TimeframeSignal,
        confirmation_signals: List[TimeframeSignal],
        filter_signals: List[TimeframeSignal]
    ) -> Tuple[SignalCorrelation, float]:
        """Calculate correlation between signals across timeframes."""

        if not confirmation_signals and not filter_signals:
            return SignalCorrelation.NEUTRAL, 0.0

        # Analyze signal directions
        primary_direction = 1 if primary_signal.signal_type in ["BUY", "COVER"] else -1

        confirmation_score = 0.0
        filter_score = 0.0

        # Score confirmation signals
        if confirmation_signals:
            confirmations = 0
            for signal in confirmation_signals:
                signal_direction = 1 if signal.signal_type in ["BUY", "COVER"] else -1
                if signal_direction == primary_direction:
                    confirmations += signal.confidence
                else:
                    confirmations -= signal.confidence

            confirmation_score = confirmations / len(confirmation_signals)

        # Score filter signals
        if filter_signals:
            filters = 0
            for signal in filter_signals:
                signal_direction = 1 if signal.signal_type in ["BUY", "COVER"] else -1
                if signal_direction == primary_direction:
                    filters += signal.confidence
                else:
                    filters -= signal.confidence

            filter_score = filters / len(filter_signals)

        # Calculate overall correlation
        total_signals = len(confirmation_signals) + len(filter_signals)
        if total_signals == 0:
            return SignalCorrelation.NEUTRAL, 0.0

        weighted_score = (confirmation_score * 0.7 + filter_score * 0.3)
        correlation_score = weighted_score

        # Determine correlation type
        if correlation_score > 0.7:
            correlation_type = SignalCorrelation.BULLISH_CONFLUENCE if primary_direction > 0 else SignalCorrelation.BEARISH_CONFLUENCE
        elif correlation_score < -0.7:
            correlation_type = SignalCorrelation.BEARISH_DIVERGENCE if primary_direction > 0 else SignalCorrelation.BULLISH_DIVERGENCE
        elif abs(correlation_score) < 0.3:
            correlation_type = SignalCorrelation.NEUTRAL
        else:
            correlation_type = SignalCorrelation.CONFLICTING

        return correlation_type, correlation_score

    async def _validate_multi_timeframe_signal(
        self,
        multi_signal: MultiTimeframeSignal,
        config: MultiTimeframeStrategyConfig
    ) -> Dict[str, str]:
        """Validate multi-timeframe signal against configuration."""

        # Check if confirmation is required
        if config.require_confirmation and not multi_signal.confirmation_signals:
            return {"status": "rejected", "reason": "No confirmation signals available"}

        # Check minimum confirmation requirements
        if config.require_confirmation:
            min_confirmations = min(tf.min_confirmation_timeframes for tf in config.confirmation_timeframes)
            if len(multi_signal.confirmation_signals) < min_confirmations:
                return {"status": "rejected", "reason": f"Insufficient confirmation signals (required: {min_confirmations})"}

        # Check filter agreement if required
        if config.require_filter_agreement and multi_signal.filter_signals:
            filter_agreement = await self._check_filter_agreement(multi_signal, config)
            if not filter_agreement:
                return {"status": "rejected", "reason": "Filter signals do not agree"}

        # Check correlation threshold
        if abs(multi_signal.correlation_score) < config.correlation_weight:
            return {"status": "rejected", "reason": f"Correlation score too low (required: {config.correlation_weight}, actual: {abs(multi_signal.correlation_score)})"}

        # Check for conflicting signals
        if multi_signal.correlation_type == SignalCorrelation.CONFLICTING:
            return {"status": "rejected", "reason": "Conflicting signals across timeframes"}

        return {"status": "approved", "reason": "All validation checks passed"}

    async def _check_filter_agreement(
        self,
        multi_signal: MultiTimeframeSignal,
        config: MultiTimeframeStrategyConfig
    ) -> bool:
        """Check if filter signals agree with primary signal."""

        if not multi_signal.filter_signals:
            return True  # No filters to check

        primary_direction = 1 if multi_signal.primary_signal.signal_type in ["BUY", "COVER"] else -1

        # Check if majority of filters agree
        agreeing_filters = 0
        total_filters = len(multi_signal.filter_signals)

        for signal in multi_signal.filter_signals:
            signal_direction = 1 if signal.signal_type in ["BUY", "COVER"] else -1
            if signal_direction == primary_direction:
                agreeing_filters += 1

        # Require at least 60% agreement
        return (agreeing_filters / total_filters) >= 0.6

    async def _calculate_final_signal(
        self,
        multi_signal: MultiTimeframeSignal,
        config: MultiTimeframeStrategyConfig
    ) -> TimeframeSignal:
        """Calculate final signal based on multi-timeframe analysis."""

        primary_signal = multi_signal.primary_signal

        # Start with primary signal
        final_quantity = primary_signal.quantity
        final_confidence = primary_signal.confidence

        # Apply confirmation adjustments
        if multi_signal.confirmation_signals:
            confirmation_factor = self._calculate_confirmation_factor(
                multi_signal.confirmation_signals, config
            )
            final_confidence *= confirmation_factor

            # Adjust quantity based on confirmation
            avg_confirmation_quantity = sum(sig.quantity for sig in multi_signal.confirmation_signals) / len(multi_signal.confirmation_signals)
            final_quantity = int((primary_signal.quantity + avg_confirmation_quantity) / 2 * confirmation_factor)

        # Apply filter adjustments
        if multi_signal.filter_signals:
            filter_factor = self._calculate_filter_factor(multi_signal.filter_signals, config)
            final_confidence *= filter_factor
            final_quantity = int(final_quantity * filter_factor)

        # Apply risk scaling if enabled
        if config.risk_scaling_enabled:
            risk_factor = await self._calculate_risk_factor(multi_signal, config)
            final_quantity = int(final_quantity * risk_factor)

        # Ensure minimum quantity
        final_quantity = max(1, final_quantity)

        return TimeframeSignal(
            timeframe=primary_signal.timeframe,
            signal_type=primary_signal.signal_type,
            quantity=final_quantity,
            price=primary_signal.price,
            confidence=min(final_confidence, 1.0),  # Cap confidence at 1.0
            parameters=primary_signal.parameters
        )

    def _calculate_confirmation_factor(
        self,
        confirmation_signals: List[TimeframeSignal],
        config: MultiTimeframeStrategyConfig
    ) -> float:
        """Calculate confirmation factor based on signal agreement."""

        if not confirmation_signals:
            return 1.0

        total_confidence = sum(sig.confidence for sig in confirmation_signals)
        avg_confidence = total_confidence / len(confirmation_signals)

        # Scale based on number of confirmations
        confirmation_boost = 1.0 + (len(confirmation_signals) * 0.1)

        return min(avg_confidence * confirmation_boost, 1.5)  # Cap at 1.5x

    def _calculate_filter_factor(
        self,
        filter_signals: List[TimeframeSignal],
        config: MultiTimeframeStrategyConfig
    ) -> float:
        """Calculate filter factor based on filter agreement."""

        if not filter_signals:
            return 1.0

        total_confidence = sum(sig.confidence for sig in filter_signals)
        avg_confidence = total_confidence / len(filter_signals)

        # Require strong filter agreement for boost
        if avg_confidence > 0.8:
            return 1.2
        elif avg_confidence > 0.6:
            return 1.0
        else:
            return 0.8  # Reduce confidence if filters don't strongly agree

    async def _calculate_risk_factor(
        self,
        multi_signal: MultiTimeframeSignal,
        config: MultiTimeframeStrategyConfig
    ) -> float:
        """Calculate risk factor based on signal correlation and confidence."""

        base_factor = 1.0

        # Adjust based on correlation type
        if multi_signal.correlation_type in [SignalCorrelation.BULLISH_CONFLUENCE, SignalCorrelation.BEARISH_CONFLUENCE]:
            base_factor += config.risk_scaling_factor
        elif multi_signal.correlation_type in [SignalCorrelation.BULLISH_DIVERGENCE, SignalCorrelation.BEARISH_DIVERGENCE]:
            base_factor -= config.risk_scaling_factor

        # Adjust based on confidence
        if multi_signal.final_signal:
            confidence_factor = multi_signal.final_signal.confidence
            base_factor *= confidence_factor

        # Apply limits
        return max(config.min_risk_multiplier, min(config.max_risk_multiplier, base_factor))

    async def _cleanup_expired_signals(self) -> None:
        """Background task to clean up expired signals."""

        while True:
            try:
                await asyncio.sleep(60)  # Clean up every minute

                current_time = datetime.utcnow()
                expired_count = 0

                # Clean up expired signals by symbol
                for symbol, timeframe_signals in list(self.active_signals.items()):
                    for timeframe, signal in list(timeframe_signals.items()):
                        # Check if signal has expired based on strategy config
                        config_key = f"{signal.parameters.get('strategy_name', 'default')}:{symbol}"
                        config = self.strategy_configs.get(config_key)

                        if config:
                            max_age = None
                            for tf_config in config.confirmation_timeframes + config.filter_timeframes:
                                if tf_config.timeframe.value == timeframe:
                                    max_age = tf_config.max_signal_age
                                    break

                            if max_age and (current_time - signal.timestamp) > max_age:
                                del self.active_signals[symbol][timeframe]
                                expired_count += 1
                        else:
                            # Default cleanup: 2 hours
                            if (current_time - signal.timestamp) > timedelta(hours=2):
                                del self.active_signals[symbol][timeframe]
                                expired_count += 1

                    # Remove empty symbol entries
                    if not self.active_signals[symbol]:
                        del self.active_signals[symbol]

                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired signals")

            except Exception as e:
                logger.error(f"Error in signal cleanup task: {e}")

    def get_active_signals(self, symbol: str) -> Dict[str, TimeframeSignal]:
        """Get all active signals for a symbol."""
        return self.active_signals.get(symbol, {}).copy()

    def get_signal_history(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 100
    ) -> List[MultiTimeframeSignal]:
        """Get signal history with optional filtering."""

        filtered_history = self.signal_history

        if symbol:
            filtered_history = [sig for sig in filtered_history if sig.symbol == symbol]

        if strategy_name:
            filtered_history = [sig for sig in filtered_history if sig.strategy_name == strategy_name]

        return filtered_history[-limit:]

    def get_strategy_config(self, strategy_name: str, symbol: str) -> Optional[MultiTimeframeStrategyConfig]:
        """Get multi-timeframe strategy configuration."""
        key = f"{strategy_name}:{symbol}"
        return self.strategy_configs.get(key)

    def get_timeframe_summary(self, symbol: str, strategy_name: str) -> Dict[str, Any]:
        """Get summary of current timeframe signals."""

        config_key = f"{strategy_name}:{symbol}"
        config = self.strategy_configs.get(config_key)

        if not config:
            return {}

        active_signals = self.get_active_signals(symbol)

        summary = {
            "symbol": symbol,
            "strategy_name": strategy_name,
            "primary_timeframe": config.primary_timeframe,
            "active_signals": {},
            "confirmation_status": {},
            "filter_status": {},
            "correlation_analysis": {}
        }

        # Primary timeframe status
        primary_signal = active_signals.get(config.primary_timeframe.value)
        summary["active_signals"][config.primary_timeframe.value] = primary_signal.dict() if primary_signal else None

        # Confirmation timeframes status
        for tf_config in config.confirmation_timeframes:
            signal = active_signals.get(tf_config.timeframe.value)
            summary["confirmation_status"][tf_config.timeframe.value] = {
                "has_signal": signal is not None,
                "signal_age": (datetime.utcnow() - signal.timestamp).total_seconds() / 60 if signal else None,
                "within_timeout": (datetime.utcnow() - signal.timestamp) <= tf_config.signal_timeout if signal else False
            }

        # Filter timeframes status
        for tf_config in config.filter_timeframes:
            signal = active_signals.get(tf_config.timeframe.value)
            summary["filter_status"][tf_config.timeframe.value] = {
                "has_signal": signal is not None,
                "signal_age": (datetime.utcnow() - signal.timestamp).total_seconds() / 60 if signal else None,
                "within_timeout": (datetime.utcnow() - signal.timestamp) <= tf_config.signal_timeout if signal else False
            }

        # Current correlation analysis if primary signal exists
        if primary_signal:
            multi_signal = MultiTimeframeSignal(
                symbol=symbol,
                strategy_name=strategy_name,
                primary_signal=primary_signal,
                confirmation_signals=[sig for tf, sig in active_signals.items()
                                    if any(tf_config.timeframe.value == tf for tf_config in config.confirmation_timeframes)],
                filter_signals=[sig for tf, sig in active_signals.items()
                              if any(tf_config.timeframe.value == tf for tf_config in config.filter_timeframes)]
            )

            # Recalculate correlation (synchronous version)
            correlation_type, correlation_score = self._calculate_signal_correlation_sync(
                primary_signal, multi_signal.confirmation_signals, multi_signal.filter_signals
            )

            summary["correlation_analysis"] = {
                "correlation_type": correlation_type,
                "correlation_score": correlation_score,
                "confirmation_count": len(multi_signal.confirmation_signals),
                "filter_count": len(multi_signal.filter_signals)
            }

        return summary

    def _calculate_signal_correlation_sync(
        self,
        primary_signal: TimeframeSignal,
        confirmation_signals: List[TimeframeSignal],
        filter_signals: List[TimeframeSignal]
    ) -> Tuple[SignalCorrelation, float]:
        """Synchronous version of signal correlation calculation."""

        if not confirmation_signals and not filter_signals:
            return SignalCorrelation.NEUTRAL, 0.0

        # Analyze signal directions
        primary_direction = 1 if primary_signal.signal_type in ["BUY", "COVER"] else -1

        confirmation_score = 0.0
        filter_score = 0.0

        # Score confirmation signals
        if confirmation_signals:
            confirmations = 0
            for signal in confirmation_signals:
                signal_direction = 1 if signal.signal_type in ["BUY", "COVER"] else -1
                if signal_direction == primary_direction:
                    confirmations += signal.confidence
                else:
                    confirmations -= signal.confidence

            confirmation_score = confirmations / len(confirmation_signals)

        # Score filter signals
        if filter_signals:
            filters = 0
            for signal in filter_signals:
                signal_direction = 1 if signal.signal_type in ["BUY", "COVER"] else -1
                if signal_direction == primary_direction:
                    filters += signal.confidence
                else:
                    filters -= signal.confidence

            filter_score = filters / len(filter_signals)

        # Calculate overall correlation
        total_signals = len(confirmation_signals) + len(filter_signals)
        if total_signals == 0:
            return SignalCorrelation.NEUTRAL, 0.0

        weighted_score = (confirmation_score * 0.7 + filter_score * 0.3)
        correlation_score = weighted_score

        # Determine correlation type
        if correlation_score > 0.7:
            correlation_type = SignalCorrelation.BULLISH_CONFLUENCE if primary_direction > 0 else SignalCorrelation.BEARISH_CONFLUENCE
        elif correlation_score < -0.7:
            correlation_type = SignalCorrelation.BEARISH_DIVERGENCE if primary_direction > 0 else SignalCorrelation.BULLISH_DIVERGENCE
        elif abs(correlation_score) < 0.3:
            correlation_type = SignalCorrelation.NEUTRAL
        else:
            correlation_type = SignalCorrelation.CONFLICTING

        return correlation_type, correlation_score
