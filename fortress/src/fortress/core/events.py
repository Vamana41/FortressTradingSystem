"""Event system for Fortress Trading System."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types for the trading system."""
    
    # Trading events
    SIGNAL_RECEIVED = "signal.received"
    ORDER_PLACED = "order.placed"
    ORDER_FILLED = "order.filled"
    ORDER_REJECTED = "order.rejected"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_EXECUTED = "order.executed"
    ORDER_NEUTRALIZED = "order.neutralized"
    POSITION_UPDATED = "position.updated"
    POSITION_SYNC = "position.sync"
    FUNDS_UPDATED = "funds.updated"
    FUNDS_UPDATE = "funds.update"
    
    # Risk management events
    RISK_CHECK_PASSED = "risk.check_passed"
    RISK_CHECK_FAILED = "risk.check_failed"
    MARGIN_LOCKED = "margin.locked"
    MARGIN_RELEASED = "margin.released"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    ERROR_OCCURRED = "error.occurred"
    EXECUTION_FAILED = "execution.failed"
    
    # AmiBroker integration events
    AMIBROKER_SIGNAL = "amibroker.signal"
    AMIBROKER_FILE_DETECTED = "amibroker.file_detected"
    
    # Scanner events
    SCANNER_JOB_CREATED = "scanner.job_created"
    SCANNER_JOB_STARTED = "scanner.job_started"
    SCANNER_PROGRESS = "scanner.progress"
    SCANNER_SIGNAL = "scanner.signal"
    SCANNER_JOB_COMPLETED = "scanner.job_completed"
    SCANNER_JOB_ERROR = "scanner.job_error"
    SCANNER_JOB_CANCELLED = "scanner.job_cancelled"
    MARKET_DATA_UPDATE = "market_data.update"
    SYMBOL_DATA_UPDATE = "symbol_data.update"
    SYMBOL_DATA_REQUEST = "symbol_data.request"
    SYMBOL_DATA_RESPONSE = "symbol_data.response"


class EventPriority(str, Enum):
    """Event priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Event(BaseModel):
    """Base event class for all system events."""
    
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of event")
    priority: EventPriority = Field(default=EventPriority.NORMAL, description="Event priority")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    source: str = Field(..., description="Event source component")
    target: Optional[str] = Field(None, description="Target component for event")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string for Redis storage."""
        return self.model_dump_json()
    
    @classmethod
    def from_json(cls, json_str: str) -> Event:
        """Create event from JSON string."""
        return cls.model_validate_json(json_str)


class SignalEvent(Event):
    """Trading signal event from AmiBroker or other sources."""
    
    symbol: str = Field(..., description="Trading symbol")
    signal_type: str = Field(..., description="Signal type (BUY/SELL/SHORT/COVER)")
    quantity: int = Field(..., description="Quantity to trade")
    price: Optional[float] = Field(None, description="Signal price")
    timeframe: str = Field(..., description="Strategy timeframe")
    strategy_name: str = Field(..., description="Strategy name")
    
    def __init__(self, **data):
        """Initialize signal event."""
        # Use provided event_type if given, otherwise default to SIGNAL_RECEIVED
        if 'event_type' not in data:
            data['event_type'] = EventType.SIGNAL_RECEIVED
        super().__init__(**data)


class OrderEvent(Event):
    """Order-related event."""
    
    symbol: str = Field(..., description="Trading symbol")
    order_type: str = Field(..., description="Order type")
    side: str = Field(..., description="Order side (BUY/SELL)")
    quantity: int = Field(..., description="Order quantity")
    price: Optional[float] = Field(None, description="Order price")
    order_id: Optional[str] = Field(None, description="Broker order ID")
    status: str = Field(..., description="Order status")
    
    def __init__(self, event_type: EventType, **data):
        """Initialize order event."""
        super().__init__(event_type=event_type, **data)


class PositionEvent(Event):
    """Position update event."""
    
    symbol: str = Field(..., description="Trading symbol")
    net_quantity: int = Field(..., description="Net position quantity")
    average_price: float = Field(..., description="Average position price")
    realized_pnl: float = Field(default=0.0, description="Realized P&L")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized P&L")
    
    def __init__(self, **data):
        """Initialize position event."""
        super().__init__(event_type=EventType.POSITION_UPDATED, **data)


class RiskEvent(Event):
    """Risk management event."""
    
    symbol: str = Field(..., description="Trading symbol")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional risk data")
    
    def __init__(self, **data):
        """Initialize risk event."""
        super().__init__(event_type=EventType.RISK_CHECK_PASSED, **data)


class MarginEvent(Event):
    """Margin management event."""
    
    symbol: str = Field(..., description="Trading symbol")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional margin data")
    
    def __init__(self, **data):
        """Initialize margin event."""
        super().__init__(event_type=EventType.MARGIN_LOCKED, **data)


class ErrorEvent(Event):
    """System error event."""
    
    error_type: str = Field(..., description="Error type")
    error_message: str = Field(..., description="Error message")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    def __init__(self, **data):
        """Initialize error event."""
        super().__init__(event_type=EventType.ERROR_OCCURRED, **data)


# Event factory functions
def create_signal_event(
    event_id: str,
    source: str,
    symbol: str,
    signal_type: str,
    quantity: int,
    timeframe: str,
    strategy_name: str,
    price: Optional[float] = None,
    priority: EventPriority = EventPriority.HIGH,
    **kwargs
) -> SignalEvent:
    """Create a signal event."""
    return SignalEvent(
        event_id=event_id,
        source=source,
        priority=priority,
        symbol=symbol,
        signal_type=signal_type,
        quantity=quantity,
        price=price,
        timeframe=timeframe,
        strategy_name=strategy_name,
        **kwargs
    )


def create_order_event(
    event_id: str,
    source: str,
    event_type: EventType,
    symbol: str,
    order_type: str,
    side: str,
    quantity: int,
    status: str,
    price: Optional[float] = None,
    order_id: Optional[str] = None,
    **kwargs
) -> OrderEvent:
    """Create an order event."""
    return OrderEvent(
        event_id=event_id,
        source=source,
        event_type=event_type,
        symbol=symbol,
        order_type=order_type,
        side=side,
        quantity=quantity,
        price=price,
        order_id=order_id,
        status=status,
        **kwargs
    )


def create_error_event(
    event_id: str,
    source: str,
    error_type: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None,
    priority: EventPriority = EventPriority.CRITICAL,
    **kwargs
) -> ErrorEvent:
    """Create an error event."""
    return ErrorEvent(
        event_id=event_id,
        source=source,
        priority=priority,
        error_type=error_type,
        error_message=error_message,
        error_details=error_details,
        **kwargs
    )