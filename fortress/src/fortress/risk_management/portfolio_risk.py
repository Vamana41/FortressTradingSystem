"""Portfolio Risk Management for FortressTradingSystem.

Implements portfolio-level risk controls including:
- Daily loss limits and circuit breakers
- Maximum drawdown controls
- Leverage and margin utilization monitoring
- Portfolio correlation and concentration risk
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import asyncio

from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioRiskConfig:
    """Portfolio risk configuration."""
    # Loss limits
    daily_loss_limit: float = 50000.0
    weekly_loss_limit: float = 200000.0
    monthly_loss_limit: float = 500000.0

    # Drawdown controls
    max_intraday_drawdown: float = 0.03  # 3% maximum intraday drawdown
    max_portfolio_drawdown: float = 0.10  # 10% maximum portfolio drawdown

    # Leverage controls
    max_gross_leverage: float = 2.0  # Maximum gross leverage
    max_net_leverage: float = 1.5  # Maximum net leverage
    max_margin_utilization: float = 0.8  # Maximum margin utilization

    # Concentration limits
    max_single_position_weight: float = 0.15  # Maximum 15% in single position
    max_sector_concentration: float = 0.25  # Maximum 25% per sector
    max_correlated_positions: int = 5  # Maximum correlated positions

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    auto_reset_time: timedelta = timedelta(hours=1)  # Auto-reset after 1 hour
    manual_reset_required: bool = True  # Require manual reset for major breaches


class PortfolioRiskManager:
    """Portfolio-level risk manager with comprehensive monitoring and controls."""

    def __init__(self, config: PortfolioRiskConfig):
        self.config = config

        # P&L tracking
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.peak_pnl = 0.0
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0

        # Exposure tracking
        self.total_exposure = 0.0
        self.gross_exposure = 0.0
        self.net_exposure = 0.0
        self.cash_balance = 0.0
        self.portfolio_value = 0.0

        # Position tracking
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.sector_exposure: Dict[str, float] = {}

        # Circuit breaker state
        self.circuit_breakers: Dict[str, bool] = {
            "daily_loss": False,
            "weekly_loss": False,
            "monthly_loss": False,
            "drawdown": False,
            "leverage": False,
            "concentration": False
        }

        self.circuit_breaker_reasons: Dict[str, str] = {}
        self.last_circuit_breaker_time: Optional[datetime] = None
        self.last_reset_time = datetime.now()

        logger.info("PortfolioRiskManager initialized", config=config)

    async def update_portfolio_state(
        self, positions: Dict[str, Dict[str, Any]],
        cash_balance: float,
        total_equity: float
    ) -> None:
        """Update portfolio state and check risk limits."""

        self.positions = positions
        self.cash_balance = cash_balance
        self.portfolio_value = total_equity

        # Calculate exposures
        await self._calculate_exposures()

        # Check all risk limits
        await self._check_all_limits()

        logger.info(
            "Updated portfolio state",
            total_exposure=self.total_exposure,
            gross_exposure=self.gross_exposure,
            net_exposure=self.net_exposure,
            portfolio_value=self.portfolio_value,
            circuit_breakers=self.circuit_breakers
        )

    async def update_pnl(self, realized_pnl: float, unrealized_pnl: float) -> None:
        """Update P&L and check loss limits."""

        total_pnl = realized_pnl + unrealized_pnl

        # Update P&L tracking
        self.daily_pnl += total_pnl
        self.weekly_pnl += total_pnl
        self.monthly_pnl += total_pnl

        # Update peak and drawdown
        if total_pnl > self.peak_pnl:
            self.peak_pnl = total_pnl

        self.current_drawdown = (self.peak_pnl - total_pnl) / self.peak_pnl if self.peak_pnl > 0 else 0
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

        # Check loss limits
        await self._check_loss_limits()

        logger.info(
            "Updated P&L",
            daily_pnl=self.daily_pnl,
            weekly_pnl=self.weekly_pnl,
            monthly_pnl=self.monthly_pnl,
            current_drawdown=self.current_drawdown,
            max_drawdown=self.max_drawdown,
            circuit_breakers=self.circuit_breakers
        )

    async def _calculate_exposures(self) -> None:
        """Calculate portfolio exposures."""

        total_long = 0.0
        total_short = 0.0
        total_notional = 0.0

        # Reset sector exposure
        self.sector_exposure.clear()

        for symbol, position in self.positions.items():
            quantity = position.get("quantity", 0)
            price = position.get("price", 0)
            sector = position.get("sector", "Unknown")
            notional = abs(quantity * price)

            total_notional += notional

            if quantity > 0:
                total_long += notional
            else:
                total_short += notional

            # Update sector exposure
            self.sector_exposure[sector] = self.sector_exposure.get(sector, 0) + notional

        self.total_exposure = total_notional
        self.gross_exposure = total_long + total_short
        self.net_exposure = abs(total_long - total_short)

        # Check concentration limits
        await self._check_concentration_limits()

        # Check leverage limits
        await self._check_leverage_limits()

    async def _check_loss_limits(self) -> None:
        """Check loss limits and trigger circuit breakers."""

        # Daily loss limit
        if abs(self.daily_pnl) > self.config.daily_loss_limit:
            self.circuit_breakers["daily_loss"] = True
            self.circuit_breaker_reasons["daily_loss"] = f"Daily loss limit exceeded: {abs(self.daily_pnl):.2f} > {self.config.daily_loss_limit}"
            logger.critical("Daily loss circuit breaker triggered", daily_pnl=abs(self.daily_pnl), limit=self.config.daily_loss_limit)

        # Weekly loss limit
        if abs(self.weekly_pnl) > self.config.weekly_loss_limit:
            self.circuit_breakers["weekly_loss"] = True
            self.circuit_breaker_reasons["weekly_loss"] = f"Weekly loss limit exceeded: {abs(self.weekly_pnl):.2f} > {self.config.weekly_loss_limit}"
            logger.critical("Weekly loss circuit breaker triggered", weekly_pnl=abs(self.weekly_pnl), limit=self.config.weekly_loss_limit)

        # Monthly loss limit
        if abs(self.monthly_pnl) > self.config.monthly_loss_limit:
            self.circuit_breakers["monthly_loss"] = True
            self.circuit_breaker_reasons["monthly_loss"] = f"Monthly loss limit exceeded: {abs(self.monthly_pnl):.2f} > {self.config.monthly_loss_limit}"
            logger.critical("Monthly loss circuit breaker triggered", monthly_pnl=abs(self.monthly_pnl), limit=self.config.monthly_loss_limit)

        # Drawdown limit
        if self.current_drawdown > self.config.max_intraday_drawdown:
            self.circuit_breakers["drawdown"] = True
            self.circuit_breaker_reasons["drawdown"] = f"Intraday drawdown exceeded: {self.current_drawdown:.2%} > {self.config.max_intraday_drawdown:.2%}"
            logger.critical("Drawdown circuit breaker triggered", drawdown=self.current_drawdown, limit=self.config.max_intraday_drawdown)

    async def _check_leverage_limits(self) -> None:
        """Check leverage and margin limits."""

        if self.portfolio_value <= 0:
            return

        # Gross leverage
        gross_leverage = self.gross_exposure / self.portfolio_value
        if gross_leverage > self.config.max_gross_leverage:
            self.circuit_breakers["leverage"] = True
            self.circuit_breaker_reasons["leverage"] = f"Gross leverage exceeded: {gross_leverage:.2f} > {self.config.max_gross_leverage}"
            logger.critical("Gross leverage circuit breaker triggered", leverage=gross_leverage, limit=self.config.max_gross_leverage)

        # Net leverage
        net_leverage = self.net_exposure / self.portfolio_value
        if net_leverage > self.config.max_net_leverage:
            self.circuit_breakers["leverage"] = True
            self.circuit_breaker_reasons["leverage"] = f"Net leverage exceeded: {net_leverage:.2f} > {self.config.max_net_leverage}"
            logger.critical("Net leverage circuit breaker triggered", leverage=net_leverage, limit=self.config.max_net_leverage)

    async def _check_concentration_limits(self) -> None:
        """Check position and sector concentration limits."""

        if self.portfolio_value <= 0:
            return

        # Check single position concentration
        for symbol, position in self.positions.items():
            quantity = position.get("quantity", 0)
            price = position.get("price", 0)
            notional = abs(quantity * price)
            weight = notional / self.portfolio_value

            if weight > self.config.max_single_position_weight:
                self.circuit_breakers["concentration"] = True
                self.circuit_breaker_reasons["concentration"] = f"Single position concentration exceeded: {weight:.2%} > {self.config.max_single_position_weight:.2%} for {symbol}"
                logger.critical("Position concentration circuit breaker triggered", symbol=symbol, weight=weight, limit=self.config.max_single_position_weight)

        # Check sector concentration
        for sector, exposure in self.sector_exposure.items():
            weight = exposure / self.portfolio_value
            if weight > self.config.max_sector_concentration:
                self.circuit_breakers["concentration"] = True
                self.circuit_breaker_reasons["concentration"] = f"Sector concentration exceeded: {weight:.2%} > {self.config.max_sector_concentration:.2%} for {sector}"
                logger.critical("Sector concentration circuit breaker triggered", sector=sector, weight=weight, limit=self.config.max_sector_concentration)

    async def _check_all_limits(self) -> None:
        """Run all limit checks."""
        await self._check_loss_limits()
        await self._check_leverage_limits()
        await self._check_concentration_limits()

    def is_trading_allowed(self) -> tuple[bool, Optional[str]]:
        """Check if trading is allowed based on circuit breakers."""

        active_breakers = [name for name, active in self.circuit_breakers.items() if active]

        if not active_breakers:
            return True, None

        # Check if auto-reset is possible
        if self.config.circuit_breaker_enabled and self.last_circuit_breaker_time:
            time_since_break = datetime.now() - self.last_circuit_breaker_time
            if time_since_break > self.config.auto_reset_time and not self.config.manual_reset_required:
                # Auto-reset minor circuit breakers
                for breaker in active_breakers:
                    if breaker in ["daily_loss", "drawdown"]:
                        self.circuit_breakers[breaker] = False
                        logger.info(f"Auto-reset circuit breaker: {breaker}")

        # Return the most severe reason
        active_breakers = [name for name, active in self.circuit_breakers.items() if active]
        if active_breakers:
            reason = self.circuit_breaker_reasons.get(active_breakers[0], "Multiple circuit breakers active")
            return False, reason

        return True, None

    def reset_circuit_breaker(self, breaker_name: str) -> bool:
        """Manually reset a specific circuit breaker."""

        if breaker_name in self.circuit_breakers:
            self.circuit_breakers[breaker_name] = False
            self.circuit_breaker_reasons.pop(breaker_name, None)
            logger.warning(f"Circuit breaker manually reset: {breaker_name}")
            return True

        return False

    def reset_all_circuit_breakers(self) -> None:
        """Reset all circuit breakers (emergency/admin use only)."""

        for breaker in self.circuit_breakers:
            self.circuit_breakers[breaker] = False

        self.circuit_breaker_reasons.clear()
        self.last_circuit_breaker_time = None

        logger.warning("All circuit breakers manually reset")

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary."""

        return {
            "pnl": {
                "daily": self.daily_pnl,
                "weekly": self.weekly_pnl,
                "monthly": self.monthly_pnl,
                "peak": self.peak_pnl,
                "drawdown": self.current_drawdown,
                "max_drawdown": self.max_drawdown
            },
            "exposure": {
                "total": self.total_exposure,
                "gross": self.gross_exposure,
                "net": self.net_exposure,
                "portfolio_value": self.portfolio_value,
                "gross_leverage": self.gross_exposure / self.portfolio_value if self.portfolio_value > 0 else 0,
                "net_leverage": self.net_exposure / self.portfolio_value if self.portfolio_value > 0 else 0
            },
            "concentration": {
                "sector_exposure": dict(self.sector_exposure),
                "max_single_position_weight": self.config.max_single_position_weight,
                "max_sector_concentration": self.config.max_sector_concentration
            },
            "circuit_breakers": {
                "active": self.circuit_breakers,
                "reasons": self.circuit_breaker_reasons,
                "trading_allowed": self.is_trading_allowed()[0]
            },
            "limits": {
                "daily_loss_limit": self.config.daily_loss_limit,
                "weekly_loss_limit": self.config.weekly_loss_limit,
                "monthly_loss_limit": self.config.monthly_loss_limit,
                "max_drawdown": self.config.max_intraday_drawdown,
                "max_gross_leverage": self.config.max_gross_leverage,
                "max_net_leverage": self.config.max_net_leverage
            }
        }
