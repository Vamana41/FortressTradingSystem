"""Fortress Brain - Core Strategy & State Management Component."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import structlog
from pydantic import BaseModel, Field

from ..core.events import (
    Event,
    EventType,
    SignalEvent,
    create_signal_event,
    create_error_event,
)
from ..core.event_bus import EventBus, publish_event, subscribe_to_event
from ..core.logging import get_brain_logger, TradingContext
from ..risk_management import RiskManager, RiskManagementConfig
from .timeframe_manager import TimeframeSignalManager, MultiTimeframeStrategyConfig, Timeframe, TimeframeConfig, TimeframePriority


logger = get_brain_logger()


class StrategyState(BaseModel):
    """Strategy state management."""

    strategy_name: str
    timeframe: str
    symbol: str
    is_active: bool = True
    last_signal_time: Optional[datetime] = None
    signal_count: int = 0
    parameters: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class PositionState(BaseModel):
    """Position state management."""

    symbol: str
    net_quantity: int = 0
    average_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    last_update_time: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class RiskState(BaseModel):
    """Risk management state."""

    total_funds: float = 0.0
    available_margin: float = 0.0
    used_margin: float = 0.0
    total_exposure: float = 0.0
    max_allowed_exposure: float = 0.0
    risk_percentage: float = 0.0
    last_update_time: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class BrainState(BaseModel):
    """Overall brain state."""

    brain_id: str
    startup_time: datetime = Field(default_factory=datetime.utcnow)
    is_healthy: bool = True
    strategies: Dict[str, StrategyState] = Field(default_factory=dict)
    positions: Dict[str, PositionState] = Field(default_factory=dict)
    risk_state: RiskState = Field(default_factory=RiskState)
    active_signals: List[str] = Field(default_factory=list)
    processed_signals: int = 0

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class FortressBrain:
    """Fortress Brain - Core Strategy & State Management."""

    def __init__(self, brain_id: str = "default"):
        """Initialize Fortress Brain."""
        self.brain_id = brain_id
        self.state = BrainState(brain_id=brain_id)
        self.event_bus: Optional[EventBus] = None
        self.risk_manager: Optional[RiskManager] = None
        self.timeframe_manager: Optional[TimeframeSignalManager] = None
        self._running = False
        self._signal_handlers: Dict[str, Any] = {}
        self._strategy_validators: Dict[str, Any] = {}

        logger.info("Fortress Brain initialized", brain_id=brain_id)

    async def initialize(self, event_bus: EventBus, openalgo_gateway=None) -> None:
        """Initialize brain with event bus and optional OpenAlgo gateway."""
        self.event_bus = event_bus

        # Initialize risk manager
        risk_config = RiskManagementConfig()
        self.risk_manager = RiskManager(event_bus, risk_config, openalgo_gateway)

        # Initialize timeframe manager
        self.timeframe_manager = TimeframeSignalManager()
        await self.timeframe_manager.start()

        # Subscribe to events
        await subscribe_to_event(EventType.SIGNAL_RECEIVED, self._handle_signal)
        await subscribe_to_event(EventType.POSITION_UPDATED, self._handle_position_update)
        await subscribe_to_event(EventType.FUNDS_UPDATED, self._handle_funds_update)

        logger.info("Fortress Brain connected to event bus", brain_id=self.brain_id)

    async def start(self) -> None:
        """Start the brain."""
        self._running = True
        logger.info("Fortress Brain started", brain_id=self.brain_id)

        # Publish startup event
        startup_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.SYSTEM_STARTUP,
            source=f"brain.{self.brain_id}",
            data={"brain_id": self.brain_id},
        )
        await publish_event(startup_event)

    async def stop(self) -> None:
        """Stop the brain."""
        self._running = False

        # Stop timeframe manager
        if self.timeframe_manager:
            await self.timeframe_manager.stop()

        logger.info("Fortress Brain stopped", brain_id=self.brain_id)

        # Publish shutdown event
        shutdown_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.SYSTEM_SHUTDOWN,
            source=f"brain.{self.brain_id}",
            data={"brain_id": self.brain_id},
        )
        await publish_event(shutdown_event)

    async def register_strategy(
        self,
        strategy_name: str,
        timeframe: str,
        symbol: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a new strategy."""
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"

        strategy_state = StrategyState(
            strategy_name=strategy_name,
            timeframe=timeframe,
            symbol=symbol,
            parameters=parameters or {},
        )

        self.state.strategies[strategy_key] = strategy_state

        logger.info(
            "Strategy registered",
            strategy_name=strategy_name,
            timeframe=timeframe,
            symbol=symbol,
            parameters=parameters,
        )

    async def register_multi_timeframe_strategy(
        self,
        strategy_name: str,
        symbol: str,
        primary_timeframe: str,
        confirmation_timeframes: List[str],
        filter_timeframes: Optional[List[str]] = None,
        require_confirmation: bool = True,
        require_filter_agreement: bool = False,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a multi-timeframe strategy with comprehensive configuration."""

        # Create timeframe configurations
        confirmation_configs = []
        for tf in confirmation_timeframes:
            confirmation_configs.append(TimeframeConfig(
                timeframe=Timeframe(tf),
                priority=TimeframePriority.CONFIRMATION,
                weight=1.0,
                signal_timeout=timedelta(minutes=30),
                max_signal_age=timedelta(minutes=60),
                correlation_threshold=0.7,
                min_confirmation_timeframes=1,
                max_confirmation_timeframes=3,
                parameters=parameters or {}
            ))

        filter_configs = []
        if filter_timeframes:
            for tf in filter_timeframes:
                filter_configs.append(TimeframeConfig(
                    timeframe=Timeframe(tf),
                    priority=TimeframePriority.FILTER,
                    weight=0.8,
                    signal_timeout=timedelta(minutes=45),
                    max_signal_age=timedelta(minutes=90),
                    correlation_threshold=0.6,
                    min_confirmation_timeframes=0,
                    max_confirmation_timeframes=2,
                    parameters=parameters or {}
                ))

        # Create multi-timeframe strategy configuration
        config = MultiTimeframeStrategyConfig(
            strategy_name=strategy_name,
            symbol=symbol,
            primary_timeframe=Timeframe(primary_timeframe),
            confirmation_timeframes=confirmation_configs,
            filter_timeframes=filter_configs,
            require_confirmation=require_confirmation,
            require_filter_agreement=require_filter_agreement,
            max_timeframe_divergence=timedelta(hours=4),
            correlation_weight=0.5,
            risk_scaling_enabled=True,
            risk_scaling_factor=0.1,
            max_risk_multiplier=2.0,
            min_risk_multiplier=0.5
        )

        # Register with timeframe manager
        if self.timeframe_manager:
            self.timeframe_manager.register_strategy_config(config)

        # Register individual timeframe strategies for backward compatibility
        await self.register_strategy(strategy_name, primary_timeframe, symbol, parameters)
        for tf in confirmation_timeframes:
            await self.register_strategy(strategy_name, tf, symbol, parameters)
        if filter_timeframes:
            for tf in filter_timeframes:
                await self.register_strategy(strategy_name, tf, symbol, parameters)

        logger.info(
            "Multi-timeframe strategy registered",
            strategy_name=strategy_name,
            symbol=symbol,
            primary_timeframe=primary_timeframe,
            confirmation_timeframes=confirmation_timeframes,
            filter_timeframes=filter_timeframes or [],
            require_confirmation=require_confirmation,
            require_filter_agreement=require_filter_agreement
        )

    async def activate_strategy(self, strategy_name: str, timeframe: str, symbol: str) -> bool:
        """Activate a strategy."""
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"

        if strategy_key not in self.state.strategies:
            logger.error("Strategy not found", strategy_key=strategy_key)
            return False

        self.state.strategies[strategy_key].is_active = True
        logger.info("Strategy activated", strategy_key=strategy_key)
        return True

    async def deactivate_strategy(self, strategy_name: str, timeframe: str, symbol: str) -> bool:
        """Deactivate a strategy."""
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"

        if strategy_key not in self.state.strategies:
            logger.error("Strategy not found", strategy_key=strategy_key)
            return False

        self.state.strategies[strategy_key].is_active = False
        logger.info("Strategy deactivated", strategy_key=strategy_key)
        return True

    async def process_signal(
        self,
        symbol: str,
        signal_type: str,
        quantity: int,
        timeframe: str,
        strategy_name: str,
        price: Optional[float] = None,
        confidence: float = 1.0,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Process a trading signal with comprehensive multi-timeframe analysis and risk management."""
        with TradingContext(
            symbol=symbol,
            signal_type=signal_type,
            strategy=strategy_name,
            timeframe=timeframe,
        ):
            logger.info(
                "Processing signal",
                symbol=symbol,
                signal_type=signal_type,
                quantity=quantity,
                timeframe=timeframe,
                strategy_name=strategy_name,
                price=price,
                confidence=confidence,
            )

            # Validate strategy
            strategy_key = f"{strategy_name}:{timeframe}:{symbol}"
            if strategy_key not in self.state.strategies:
                logger.error("Unknown strategy", strategy_key=strategy_key)
                return False

            strategy_state = self.state.strategies[strategy_key]
            if not strategy_state.is_active:
                logger.warning("Strategy is inactive", strategy_key=strategy_key)
                return False

            # Check if this is a multi-timeframe strategy
            if self.timeframe_manager:
                config = self.timeframe_manager.get_strategy_config(strategy_name, symbol)
                if config:
                    # Process as multi-timeframe signal
                    return await self._process_multi_timeframe_signal(
                        symbol, signal_type, quantity, timeframe, strategy_name,
                        price, confidence, parameters
                    )

            # Process as single timeframe signal (backward compatibility)
            return await self._process_single_timeframe_signal(
                symbol, signal_type, quantity, timeframe, strategy_name,
                price, parameters
            )

    async def _process_multi_timeframe_signal(
        self,
        symbol: str,
        signal_type: str,
        quantity: int,
        timeframe: str,
        strategy_name: str,
        price: Optional[float] = None,
        confidence: float = 1.0,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Process a signal using multi-timeframe analysis."""

        if not self.timeframe_manager:
            logger.error("Timeframe manager not available")
            return False

        # Process timeframe signal through multi-timeframe manager
        try:
            multi_signal = await self.timeframe_manager.process_timeframe_signal(
                symbol=symbol,
                strategy_name=strategy_name,
                timeframe=timeframe,
                signal_type=signal_type,
                quantity=quantity,
                price=price,
                confidence=confidence,
                parameters=parameters
            )

            # Check if signal was approved
            if multi_signal.validation_status != "approved":
                logger.warning(
                    "Multi-timeframe signal rejected",
                    symbol=symbol,
                    strategy_name=strategy_name,
                    timeframe=timeframe,
                    reason=multi_signal.validation_reason
                )
                return False

            # Use the final calculated signal
            if not multi_signal.final_signal:
                logger.error("No final signal calculated")
                return False

            final_signal = multi_signal.final_signal

            # Validate signal
            if not await self._validate_signal(
                symbol, final_signal.signal_type, final_signal.quantity,
                timeframe, strategy_name, final_signal.price
            ):
                logger.error("Signal validation failed")
                return False

            # Calculate position size with risk management
            if self.risk_manager and final_signal.price:
                sizing_result = await self.risk_manager.calculate_position_size(
                    symbol=symbol,
                    signal_type=final_signal.signal_type,
                    suggested_quantity=final_signal.quantity,
                    price=final_signal.price,
                    strategy_name=strategy_name,
                    timeframe=timeframe
                )

                if not sizing_result.success:
                    logger.error("Position sizing failed", error=sizing_result.error_message)
                    return False

                # Use calculated quantity
                final_quantity = sizing_result.final_quantity
                estimated_cost = sizing_result.estimated_cost

                logger.info(
                    "Position sizing successful",
                    original_quantity=final_signal.quantity,
                    final_quantity=final_quantity,
                    estimated_cost=estimated_cost,
                    sizing_method=sizing_result.sizing_method
                )
            else:
                # Fallback to final signal quantity
                final_quantity = final_signal.quantity
                estimated_cost = final_signal.quantity * (final_signal.price or 0)

            # Approve trade with risk management
            if self.risk_manager:
                approved, approval_reason = await self.risk_manager.approve_trade(
                    symbol=symbol,
                    signal_type=final_signal.signal_type,
                    quantity=final_quantity,
                    price=final_signal.price or 0,
                    strategy_name=strategy_name,
                    timeframe=timeframe,
                    estimated_cost=estimated_cost
                )

                if not approved:
                    logger.error("Trade approval failed", reason=approval_reason)
                    return False

            # Create signal event with final quantity and multi-timeframe data
            signal_event = create_signal_event(
                event_id=str(uuid.uuid4()),
                source=f"brain.{self.brain_id}",
                symbol=symbol,
                signal_type=final_signal.signal_type,
                quantity=final_quantity,
                price=final_signal.price,
                timeframe=timeframe,
                strategy_name=strategy_name,
                data={
                    "original_quantity": quantity,
                    "estimated_cost": estimated_cost,
                    "sizing_method": sizing_result.sizing_method if self.risk_manager and final_signal.price else "original",
                    "risk_percentage": sizing_result.risk_percentage if self.risk_manager and final_signal.price else 0,
                    "multi_timeframe_analysis": {
                        "correlation_type": multi_signal.correlation_type,
                        "correlation_score": multi_signal.correlation_score,
                        "confirmation_signals": len(multi_signal.confirmation_signals),
                        "filter_signals": len(multi_signal.filter_signals),
                        "final_confidence": final_signal.confidence
                    }
                }
            )

            # Update strategy state
            strategy_state = self.state.strategies[strategy_key]
            strategy_state.last_signal_time = datetime.utcnow()
            strategy_state.signal_count += 1

            # Add to active signals
            self.state.active_signals.append(signal_event.event_id)

            # Publish signal event
            success = await publish_event(signal_event)

            if success:
                self.state.processed_signals += 1
                logger.info(
                    "Multi-timeframe signal processed successfully",
                    signal_id=signal_event.event_id,
                    strategy_key=strategy_key,
                    correlation_type=multi_signal.correlation_type,
                    final_quantity=final_quantity,
                    final_confidence=final_signal.confidence
                )
            else:
                logger.error("Failed to publish signal event")

            return success

        except Exception as e:
            logger.error("Error processing multi-timeframe signal", error=str(e))
            return False

    async def _process_single_timeframe_signal(
        self,
        symbol: str,
        signal_type: str,
        quantity: int,
        timeframe: str,
        strategy_name: str,
        price: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Process a single timeframe signal (backward compatibility)."""

        # Validate signal
        if not await self._validate_signal(
            symbol, signal_type, quantity, timeframe, strategy_name, price
        ):
            logger.error("Signal validation failed")
            return False

        # Calculate position size with risk management
        if self.risk_manager and price:
            sizing_result = await self.risk_manager.calculate_position_size(
                symbol=symbol,
                signal_type=signal_type,
                suggested_quantity=quantity,
                price=price,
                strategy_name=strategy_name,
                timeframe=timeframe
            )

            if not sizing_result.success:
                logger.error("Position sizing failed", error=sizing_result.error_message)
                return False

            # Use calculated quantity instead of original
            final_quantity = sizing_result.final_quantity
            estimated_cost = sizing_result.estimated_cost

            logger.info(
                "Position sizing successful",
                original_quantity=quantity,
                final_quantity=final_quantity,
                estimated_cost=estimated_cost,
                sizing_method=sizing_result.sizing_method
            )
        else:
            # Fallback to original quantity if no price or risk manager
            final_quantity = quantity
            estimated_cost = quantity * price if price else 0

        # Approve trade with risk management
        if self.risk_manager:
            approved, approval_reason = await self.risk_manager.approve_trade(
                symbol=symbol,
                signal_type=signal_type,
                quantity=final_quantity,
                price=price or 0,
                strategy_name=strategy_name,
                timeframe=timeframe,
                estimated_cost=estimated_cost
            )

            if not approved:
                logger.error("Trade approval failed", reason=approval_reason)
                return False

        # Create signal event with final quantity
        signal_event = create_signal_event(
            event_id=str(uuid.uuid4()),
            source=f"brain.{self.brain_id}",
            symbol=symbol,
            signal_type=signal_type,
            quantity=final_quantity,  # Use calculated quantity
            price=price,
            timeframe=timeframe,
            strategy_name=strategy_name,
            data={
                "original_quantity": quantity,
                "estimated_cost": estimated_cost,
                "sizing_method": sizing_result.sizing_method if self.risk_manager and price else "original",
                "risk_percentage": sizing_result.risk_percentage if self.risk_manager and price else 0
            }
        )

        # Update strategy state
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"
        strategy_state = self.state.strategies[strategy_key]
        strategy_state.last_signal_time = datetime.utcnow()
        strategy_state.signal_count += 1

        # Add to active signals
        self.state.active_signals.append(signal_event.event_id)

        # Publish signal event
        success = await publish_event(signal_event)

        if success:
            self.state.processed_signals += 1
            logger.info(
                "Signal processed successfully",
                signal_id=signal_event.event_id,
                strategy_key=strategy_key,
            )
        else:
            logger.error("Failed to publish signal event")

        return success

    async def _handle_signal(self, event: Event) -> None:
        """Handle signal received event."""
        if not isinstance(event, SignalEvent):
            logger.error("Invalid signal event type")
            return

        with TradingContext(
            symbol=event.symbol,
            signal_type=event.signal_type,
            strategy=event.strategy_name,
            timeframe=event.timeframe,
        ):
            logger.info(
                "Handling signal event",
                signal_id=event.event_id,
                symbol=event.symbol,
                signal_type=event.signal_type,
                quantity=event.quantity,
                strategy=event.strategy_name,
                timeframe=event.timeframe,
            )

            # Perform risk checks
            if not await self._perform_risk_checks(event):
                logger.error("Risk checks failed for signal", signal_id=event.event_id)

                # Publish risk check failed event
                risk_event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.RISK_CHECK_FAILED,
                    source=f"brain.{self.brain_id}",
                    data={
                        "original_signal_id": event.event_id,
                        "symbol": event.symbol,
                        "signal_type": event.signal_type,
                        "quantity": event.quantity,
                    },
                )
                await publish_event(risk_event)
                return

            # Publish risk check passed event
            risk_event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.RISK_CHECK_PASSED,
                source=f"brain.{self.brain_id}",
                data={
                    "original_signal_id": event.event_id,
                    "symbol": event.symbol,
                    "signal_type": event.signal_type,
                    "quantity": event.quantity,
                },
            )
            await publish_event(risk_event)

            logger.info("Signal processed successfully", signal_id=event.event_id)

    async def _handle_position_update(self, event: Event) -> None:
        """Handle position update event."""
        logger.info(
            "Handling position update",
            event_id=event.event_id,
            symbol=event.data.get("symbol"),
            net_quantity=event.data.get("net_quantity"),
        )

        symbol = event.data.get("symbol")
        if symbol:
            # Update position state
            position_state = PositionState(
                symbol=symbol,
                net_quantity=event.data.get("net_quantity", 0),
                average_price=event.data.get("average_price", 0.0),
                realized_pnl=event.data.get("realized_pnl", 0.0),
                unrealized_pnl=event.data.get("unrealized_pnl", 0.0),
            )
            self.state.positions[symbol] = position_state

            # Update risk manager with new position state
            if self.risk_manager:
                positions_data = {
                    symbol: {
                        "net_quantity": position_state.net_quantity,
                        "average_price": position_state.average_price,
                        "realized_pnl": position_state.realized_pnl,
                        "unrealized_pnl": position_state.unrealized_pnl
                    }
                    for symbol, position_state in self.state.positions.items()
                }

                await self.risk_manager.update_portfolio_state(
                    positions=positions_data,
                    cash_balance=self.state.risk_state.available_margin,
                    total_equity=self.state.risk_state.total_funds,
                    realized_pnl=position_state.realized_pnl,
                    unrealized_pnl=position_state.unrealized_pnl
                )

    async def _handle_funds_update(self, event: Event) -> None:
        """Handle funds update event."""
        logger.info(
            "Handling funds update",
            event_id=event.event_id,
            total_funds=event.data.get("total_funds"),
            available_margin=event.data.get("available_margin"),
        )

        # Update risk state
        self.state.risk_state.total_funds = event.data.get("total_funds", 0.0)
        self.state.risk_state.available_margin = event.data.get("available_margin", 0.0)
        self.state.risk_state.used_margin = event.data.get("used_margin", 0.0)

        # Update risk manager with new funds state
        if self.risk_manager:
            positions_data = {
                symbol: {
                    "net_quantity": position_state.net_quantity,
                    "average_price": position_state.average_price,
                    "realized_pnl": position_state.realized_pnl,
                    "unrealized_pnl": position_state.unrealized_pnl
                }
                for symbol, position_state in self.state.positions.items()
            }

            await self.risk_manager.update_portfolio_state(
                positions=positions_data,
                cash_balance=self.state.risk_state.available_margin,
                total_equity=self.state.risk_state.total_funds
            )

    async def _validate_signal(
        self,
        symbol: str,
        signal_type: str,
        quantity: int,
        timeframe: str,
        strategy_name: str,
        price: Optional[float],
    ) -> bool:
        """Validate trading signal."""
        # Check if we have a validator for this strategy
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"
        validator = self._strategy_validators.get(strategy_key)

        if validator:
            return await validator(
                symbol, signal_type, quantity, timeframe, strategy_name, price
            )

        # Default validation
        if quantity <= 0:
            logger.error("Invalid quantity", quantity=quantity)
            return False

        if signal_type not in ["BUY", "SELL", "SHORT", "COVER"]:
            logger.error("Invalid signal type", signal_type=signal_type)
            return False

        return True

    async def _perform_risk_checks(self, signal_event: SignalEvent) -> bool:
        """Perform comprehensive risk management checks."""
        logger.info(
            "Performing risk checks",
            symbol=signal_event.symbol,
            signal_type=signal_event.signal_type,
            quantity=signal_event.quantity,
        )

        # Use comprehensive risk management system if available
        if self.risk_manager:
            approved, reason = await self.risk_manager.approve_trade(
                symbol=signal_event.symbol,
                signal_type=signal_event.signal_type,
                quantity=signal_event.quantity,
                price=signal_event.price or 0,
                strategy_name=signal_event.strategy_name,
                timeframe=signal_event.timeframe,
                estimated_cost=signal_event.quantity * (signal_event.price or 0)
            )

            if not approved:
                logger.error("Risk check failed", reason=reason)
                return False

            logger.info("Risk check passed with comprehensive risk management")
            return True

        # Fallback to basic checks if risk manager not available
        # Check available margin
        if self.state.risk_state.available_margin <= 0:
            logger.error("No available margin")
            return False

        # Check position limits
        current_position = self.state.positions.get(signal_event.symbol)
        if current_position:
            # Check if signal would exceed position limits
            new_quantity = current_position.net_quantity
            if signal_event.signal_type in ["BUY", "COVER"]:
                new_quantity += signal_event.quantity
            else:  # SELL, SHORT
                new_quantity -= signal_event.quantity

            # Add your position limit logic here
            max_position = 100  # Example limit
            if abs(new_quantity) > max_position:
                logger.error("Position limit exceeded", new_quantity=new_quantity, limit=max_position)
                return False

        logger.info("Basic risk checks passed")
        return True

    def get_state(self) -> BrainState:
        """Get current brain state."""
        return self.state

    def get_strategy_state(self, strategy_name: str, timeframe: str, symbol: str) -> Optional[StrategyState]:
        """Get strategy state."""
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"
        return self.state.strategies.get(strategy_key)

    def get_position_state(self, symbol: str) -> Optional[PositionState]:
        """Get position state."""
        return self.state.positions.get(symbol)

    def get_risk_state(self) -> RiskState:
        """Get risk state."""
        return self.state.risk_state

    def register_signal_handler(self, strategy_name: str, timeframe: str, symbol: str, handler: Any) -> None:
        """Register custom signal handler."""
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"
        self._signal_handlers[strategy_key] = handler
        logger.info("Signal handler registered", strategy_key=strategy_key)

    def register_strategy_validator(self, strategy_name: str, timeframe: str, symbol: str, validator: Any) -> None:
        """Register custom strategy validator."""
        strategy_key = f"{strategy_name}:{timeframe}:{symbol}"
        self._strategy_validators[strategy_key] = validator
        logger.info("Strategy validator registered", strategy_key=strategy_key)

    async def update_portfolio_state(
        self,
        positions: Dict[str, Any],
        cash_balance: float,
        total_equity: float,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0
    ) -> None:
        """Update portfolio state and risk metrics."""

        # Update brain state
        for symbol, position_data in positions.items():
            if symbol not in self.state.positions:
                self.state.positions[symbol] = PositionState(symbol=symbol)

            position_state = self.state.positions[symbol]
            position_state.net_quantity = position_data.get("net_quantity", 0)
            position_state.average_price = position_data.get("average_price", 0)
            position_state.realized_pnl = position_data.get("realized_pnl", 0)
            position_state.unrealized_pnl = position_data.get("unrealized_pnl", 0)
            position_state.last_update_time = datetime.utcnow()

        # Update risk state
        self.state.risk_state.total_funds = total_equity
        self.state.risk_state.available_margin = cash_balance
        self.state.risk_state.used_margin = total_equity - cash_balance
        self.state.risk_state.last_update_time = datetime.utcnow()

        # Update risk manager if available
        if self.risk_manager:
            await self.risk_manager.update_portfolio_state(
                positions=positions,
                cash_balance=cash_balance,
                total_equity=total_equity,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl
            )

        logger.info(
            "Portfolio state updated",
            total_equity=total_equity,
            cash_balance=cash_balance,
            positions_count=len(positions),
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl
        )

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary."""

        if self.risk_manager:
            return self.risk_manager.get_risk_summary()
        else:
            return {
                "portfolio_state": {
                    "total_equity": self.state.risk_state.total_funds,
                    "available_margin": self.state.risk_state.available_margin,
                    "used_margin": self.state.risk_state.used_margin
                },
                "risk_state": self.state.risk_state.dict()
            }

    def get_timeframe_summary(self, symbol: str, strategy_name: str) -> Dict[str, Any]:
        """Get multi-timeframe signal summary for a strategy."""
        if not self.timeframe_manager:
            return {"error": "Timeframe manager not available"}

        return self.timeframe_manager.get_timeframe_summary(symbol, strategy_name)

    def get_multi_timeframe_signals(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get multi-timeframe signal history."""
        if not self.timeframe_manager:
            return []

        signals = self.timeframe_manager.get_signal_history(symbol, strategy_name, limit)
        return [signal.dict() for signal in signals]

    def get_active_timeframe_signals(self, symbol: str) -> Dict[str, Any]:
        """Get all active timeframe signals for a symbol."""
        if not self.timeframe_manager:
            return {}

        signals = self.timeframe_manager.get_active_signals(symbol)
        return {tf: signal.dict() for tf, signal in signals.items()}
