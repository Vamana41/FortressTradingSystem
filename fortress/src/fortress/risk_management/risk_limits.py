"""Risk Limits and Exposure Management for FortressTradingSystem.

Implements comprehensive risk limits including:
- Per-symbol and per-instrument limits
- Portfolio-level exposure controls
- Time-based trading limits
- Sector and category exposure limits
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict, deque

from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExposureLimits:
    """Exposure limit configuration."""
    max_lots: int = 100  # Maximum lots per symbol
    max_notional: float = 1000000  # Maximum notional value per symbol
    max_net_quantity: int = 1000  # Maximum net quantity per symbol
    max_long_quantity: int = 1000  # Maximum long quantity
    max_short_quantity: int = 1000  # Maximum short quantity


@dataclass
class RiskLimitsConfig:
    """Risk limits configuration."""
    # Symbol-level limits
    symbol_limits: Dict[str, ExposureLimits] = field(default_factory=dict)
    default_symbol_limits: ExposureLimits = field(default_factory=ExposureLimits)
    
    # Portfolio-level limits
    max_total_exposure: float = 5000000  # Maximum total portfolio exposure
    max_open_positions: int = 50  # Maximum number of open positions
    max_sector_exposure: Dict[str, float] = field(default_factory=dict)  # Sector limits
    
    # Time-based limits
    max_orders_per_minute: int = 10  # Maximum orders per minute
    max_orders_per_hour: int = 100  # Maximum orders per hour
    max_orders_per_day: int = 500  # Maximum orders per day
    
    # Leverage limits
    max_leverage_ratio: float = 2.0  # Maximum leverage (total exposure / equity)
    max_margin_utilization: float = 0.8  # Maximum margin utilization
    
    # Circuit breakers
    daily_loss_limit: float = 50000  # Daily loss limit
    max_drawdown_percentage: float = 0.05  # Maximum drawdown percentage


class RiskLimits:
    """Risk limits manager with real-time tracking and enforcement."""
    
    def __init__(self, config: RiskLimitsConfig):
        self.config = config
        self.order_history = deque(maxlen=1000)  # Track recent orders for rate limiting
        self.daily_orders = 0
        self.last_reset_time = datetime.now()
        
        # Exposure tracking
        self.symbol_exposure: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "lots": 0,
            "notional": 0.0,
            "net_quantity": 0,
            "long_quantity": 0,
            "short_quantity": 0
        })
        
        self.sector_exposure: Dict[str, float] = defaultdict(float)
        self.total_exposure = 0.0
        self.open_positions = 0
        
        # Circuit breaker state
        self.daily_loss = 0.0
        self.max_daily_pnl = 0.0
        self.min_daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = None
        
        logger.info("RiskLimits initialized", config=config)
    
    async def check_order_limits(
        self, symbol: str, order_type: str, quantity: int, price: float
    ) -> tuple[bool, Optional[str]]:
        """Check if order complies with all risk limits."""
        
        # Reset daily counters if needed
        await self._reset_daily_limits_if_needed()
        
        # Check circuit breakers first
        if self.circuit_breaker_active:
            return False, f"Circuit breaker active: {self.circuit_breaker_reason}"
        
        # Check time-based limits
        passed, reason = await self._check_rate_limits()
        if not passed:
            return False, reason
        
        # Check symbol-level limits
        passed, reason = await self._check_symbol_limits(symbol, quantity, price)
        if not passed:
            return False, reason
        
        # Check portfolio-level limits
        passed, reason = await self._check_portfolio_limits(symbol, quantity, price)
        if not passed:
            return False, reason
        
        # Check sector limits
        passed, reason = await self._check_sector_limits(symbol, quantity, price)
        if not passed:
            return False, reason
        
        return True, None
    
    async def _check_rate_limits(self) -> tuple[bool, Optional[str]]:
        """Check order rate limits."""
        now = datetime.now()
        
        # Count orders in the last minute
        recent_orders = [
            order_time for order_time in self.order_history
            if now - order_time < timedelta(minutes=1)
        ]
        
        if len(recent_orders) >= self.config.max_orders_per_minute:
            return False, f"Orders per minute limit exceeded: {len(recent_orders)} >= {self.config.max_orders_per_minute}"
        
        # Count orders in the last hour
        recent_hour_orders = [
            order_time for order_time in self.order_history
            if now - order_time < timedelta(hours=1)
        ]
        
        if len(recent_hour_orders) >= self.config.max_orders_per_hour:
            return False, f"Orders per hour limit exceeded: {len(recent_hour_orders)} >= {self.config.max_orders_per_hour}"
        
        # Check daily limit
        if self.daily_orders >= self.config.max_orders_per_day:
            return False, f"Daily order limit exceeded: {self.daily_orders} >= {self.config.max_orders_per_day}"
        
        return True, None
    
    async def _check_symbol_limits(self, symbol: str, quantity: int, price: float) -> tuple[bool, Optional[str]]:
        """Check symbol-level exposure limits."""
        symbol_limits = self.config.symbol_limits.get(symbol, self.config.default_symbol_limits)
        current_exposure = self.symbol_exposure[symbol]
        
        # Calculate new exposure
        new_lots = current_exposure["lots"] + (quantity / 100)  # Assuming 100 shares per lot, adjust as needed
        new_notional = current_exposure["notional"] + (quantity * price)
        
        # Check lot limit
        if new_lots > symbol_limits.max_lots:
            return False, f"Symbol lot limit exceeded: {new_lots} > {symbol_limits.max_lots}"
        
        # Check notional limit
        if new_notional > symbol_limits.max_notional:
            return False, f"Symbol notional limit exceeded: {new_notional} > {symbol_limits.max_notional}"
        
        # Check net quantity limit (this would need position direction logic)
        projected_net = current_exposure["net_quantity"] + quantity
        if abs(projected_net) > symbol_limits.max_net_quantity:
            return False, f"Symbol net quantity limit exceeded: {abs(projected_net)} > {symbol_limits.max_net_quantity}"
        
        return True, None
    
    async def _check_portfolio_limits(self, symbol: str, quantity: int, price: float) -> tuple[bool, Optional[str]]:
        """Check portfolio-level limits."""
        
        # Check total exposure
        new_total_exposure = self.total_exposure + (quantity * price)
        if new_total_exposure > self.config.max_total_exposure:
            return False, f"Total exposure limit exceeded: {new_total_exposure} > {self.config.max_total_exposure}"
        
        # Check number of open positions (simplified - would need proper position tracking)
        if symbol not in self.symbol_exposure:
            new_open_positions = self.open_positions + 1
            if new_open_positions > self.config.max_open_positions:
                return False, f"Max open positions exceeded: {new_open_positions} > {self.config.max_open_positions}"
        
        return True, None
    
    async def _check_sector_limits(self, symbol: str, quantity: int, price: float) -> tuple[bool, Optional[str]]:
        """Check sector exposure limits."""
        # This would need symbol-to-sector mapping
        # For now, return True (no sector limits enforced)
        return True, None
    
    async def update_exposure(self, symbol: str, quantity: int, price: float, order_type: str) -> None:
        """Update exposure tracking after order execution."""
        
        # Add to order history
        self.order_history.append(datetime.now())
        self.daily_orders += 1
        
        # Update symbol exposure
        exposure = self.symbol_exposure[symbol]
        notional_change = quantity * price
        
        exposure["lots"] += quantity / 100  # Assuming 100 shares per lot
        exposure["notional"] += notional_change
        exposure["net_quantity"] += quantity if order_type == "BUY" else -quantity
        
        if order_type == "BUY":
            exposure["long_quantity"] += quantity
        else:
            exposure["short_quantity"] += quantity
        
        # Update total exposure
        self.total_exposure += notional_change
        
        # Update open positions count
        if exposure["net_quantity"] == 0 and exposure["notional"] == 0:
            self.open_positions = max(0, self.open_positions - 1)
        elif exposure["net_quantity"] != 0 and exposure["notional"] == 0:
            self.open_positions += 1
        
        logger.info(
            "Updated exposure tracking",
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
            total_exposure=self.total_exposure,
            open_positions=self.open_positions
        )
    
    async def update_pnl(self, realized_pnl: float, unrealized_pnl: float) -> None:
        """Update P&L tracking and check circuit breakers."""
        
        self.daily_loss += min(0, realized_pnl)  # Only track losses
        current_pnl = realized_pnl + unrealized_pnl
        
        # Track max/min P&L for drawdown calculation
        self.max_daily_pnl = max(self.max_daily_pnl, current_pnl)
        self.min_daily_pnl = min(self.min_daily_pnl, current_pnl)
        
        # Check daily loss limit
        if abs(self.daily_loss) > self.config.daily_loss_limit:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = f"Daily loss limit exceeded: {abs(self.daily_loss):.2f} > {self.config.daily_loss_limit}"
            logger.critical("Daily loss limit circuit breaker triggered", daily_loss=abs(self.daily_loss), limit=self.config.daily_loss_limit)
        
        # Check drawdown limit
        if self.max_daily_pnl > 0:
            drawdown = (self.max_daily_pnl - current_pnl) / self.max_daily_pnl
            if drawdown > self.config.max_drawdown_percentage:
                self.circuit_breaker_active = True
                self.circuit_breaker_reason = f"Max drawdown exceeded: {drawdown:.2%} > {self.config.max_drawdown_percentage:.2%}"
                logger.critical("Drawdown circuit breaker triggered", drawdown=drawdown, limit=self.config.max_drawdown_percentage)
        
        logger.info(
            "Updated P&L tracking",
            daily_loss=self.daily_loss,
            current_pnl=current_pnl,
            max_pnl=self.max_daily_pnl,
            min_pnl=self.min_daily_pnl,
            circuit_breaker_active=self.circuit_breaker_active
        )
    
    async def _reset_daily_limits_if_needed(self) -> None:
        """Reset daily limits if it's a new day."""
        now = datetime.now()
        if now.date() > self.last_reset_time.date():
            logger.info("Resetting daily limits for new trading day")
            self.daily_orders = 0
            self.daily_loss = 0.0
            self.max_daily_pnl = 0.0
            self.min_daily_pnl = 0.0
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = None
            self.last_reset_time = now
    
    def get_exposure_summary(self) -> Dict[str, Any]:
        """Get current exposure summary."""
        return {
            "total_exposure": self.total_exposure,
            "open_positions": self.open_positions,
            "symbol_exposure": dict(self.symbol_exposure),
            "sector_exposure": dict(self.sector_exposure),
            "daily_orders": self.daily_orders,
            "daily_loss": self.daily_loss,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason
        }
    
    def reset_circuit_breaker(self) -> bool:
        """Manually reset circuit breaker (requires admin intervention)."""
        if self.circuit_breaker_active:
            logger.warning("Circuit breaker manually reset", reason=self.circuit_breaker_reason)
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = None
            return True
        return False