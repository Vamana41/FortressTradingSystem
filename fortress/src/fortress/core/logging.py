"""Structured logging configuration for Fortress Trading System."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import LoggerFactory


def configure_structlog(
    log_level: str = "INFO",
    json_format: bool = True,
    include_timestamp: bool = True,
    include_source: bool = True,
) -> None:
    """Configure structured logging for the trading system."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog processors
    processors = []

    if include_timestamp:
        processors.append(structlog.stdlib.add_log_level)
        processors.append(structlog.stdlib.add_logger_name)
        processors.append(structlog.dev.set_exc_info)
        processors.append(structlog.processors.TimeStamper(fmt="iso"))

    if include_source:
        processors.append(add_source_info)

    # Add trading-specific processors
    processors.extend([
        add_trading_context,
        add_performance_metrics,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ])

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def add_source_info(logger: str, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add source code information to log entries."""
    import inspect

    # Get the calling frame (skip this function and structlog internals)
    frame = inspect.currentframe()
    try:
        # Go up the call stack to find user code
        while frame:
            filename = frame.f_code.co_filename
            if "structlog" not in filename and "logging" not in filename:
                event_dict["source_file"] = filename.split("/")[-1]
                event_dict["source_line"] = frame.f_lineno
                event_dict["source_function"] = frame.f_code.co_name
                break
            frame = frame.f_back
    finally:
        del frame  # Avoid reference cycles

    return event_dict


def add_trading_context(logger: str, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add trading-specific context to log entries."""
    # Add trading session context if available
    if hasattr(logging, "trading_context"):
        context = getattr(logging, "trading_context")
        event_dict.update(context)

    return event_dict


def add_performance_metrics(logger: str, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add performance metrics to log entries."""
    # Add memory usage if psutil is available
    try:
        import psutil
        process = psutil.Process()
        event_dict["memory_mb"] = round(process.memory_info().rss / 1024 / 1024, 2)
        event_dict["cpu_percent"] = process.cpu_percent()
    except ImportError:
        pass

    return event_dict


class TradingContext:
    """Context manager for trading-specific logging context."""

    def __init__(self, **context: Any):
        """Initialize trading context."""
        self.context = context
        self._original_context = {}

    def __enter__(self) -> TradingContext:
        """Enter context."""
        # Store original context
        if hasattr(logging, "trading_context"):
            self._original_context = getattr(logging, "trading_context").copy()
        else:
            setattr(logging, "trading_context", {})

        # Update with new context
        getattr(logging, "trading_context").update(self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        # Restore original context
        if self._original_context:
            setattr(logging, "trading_context", self._original_context)
        else:
            if hasattr(logging, "trading_context"):
                delattr(logging, "trading_context")


def log_trading_event(
    logger: structlog.BoundLogger,
    event_type: str,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    timeframe: Optional[str] = None,
    quantity: Optional[int] = None,
    price: Optional[float] = None,
    **kwargs: Any,
) -> None:
    """Log trading events with structured data."""
    log_data = {
        "event_type": event_type,
        "symbol": symbol,
        "strategy": strategy,
        "timeframe": timeframe,
        "quantity": quantity,
        "price": price,
    }
    log_data.update(kwargs)

    # Remove None values
    log_data = {k: v for k, v in log_data.items() if v is not None}

    logger.info("Trading event", **log_data)


def log_order_event(
    logger: structlog.BoundLogger,
    order_id: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    status: str,
    price: Optional[float] = None,
    filled_quantity: Optional[int] = None,
    average_price: Optional[float] = None,
    **kwargs: Any,
) -> None:
    """Log order events with structured data."""
    log_data = {
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "status": status,
        "price": price,
        "filled_quantity": filled_quantity,
        "average_price": average_price,
    }
    log_data.update(kwargs)

    # Remove None values
    log_data = {k: v for k, v in log_data.items() if v is not None}

    logger.info("Order event", **log_data)


def log_risk_event(
    logger: structlog.BoundLogger,
    risk_type: str,
    symbol: Optional[str] = None,
    risk_amount: Optional[float] = None,
    available_margin: Optional[float] = None,
    required_margin: Optional[float] = None,
    **kwargs: Any,
) -> None:
    """Log risk management events with structured data."""
    log_data = {
        "risk_type": risk_type,
        "symbol": symbol,
        "risk_amount": risk_amount,
        "available_margin": available_margin,
        "required_margin": required_margin,
    }
    log_data.update(kwargs)

    # Remove None values
    log_data = {k: v for k, v in log_data.items() if v is not None}

    logger.info("Risk event", **log_data)


def log_performance_metrics(
    logger: structlog.BoundLogger,
    operation: str,
    duration_ms: float,
    success: bool = True,
    **kwargs: Any,
) -> None:
    """Log performance metrics with structured data."""
    log_data = {
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }
    log_data.update(kwargs)

    if success:
        logger.info("Performance metric", **log_data)
    else:
        logger.error("Performance metric (failed)", **log_data)


# Convenience functions for getting loggers
def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger."""
    return structlog.get_logger(name)


def get_trading_logger(component: str) -> structlog.BoundLogger:
    """Get a trading component logger."""
    return structlog.get_logger(f"fortress.trading.{component}")


def get_brain_logger() -> structlog.BoundLogger:
    """Get the Brain component logger."""
    return get_trading_logger("brain")


def get_worker_logger() -> structlog.BoundLogger:
    """Get the Worker component logger."""
    return get_trading_logger("worker")


def get_gateway_logger() -> structlog.BoundLogger:
    """Get the Gateway component logger."""
    return get_trading_logger("gateway")


def get_risk_logger() -> structlog.BoundLogger:
    """Get the Risk Management component logger."""
    return get_trading_logger("risk")


# Initialize logging on module import
configure_structlog()
