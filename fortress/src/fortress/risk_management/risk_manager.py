"""Risk Management Orchestrator for FortressTradingSystem.

Main risk management service that coordinates:
- Position sizing calculations
- Risk limit enforcement  
- Portfolio risk monitoring
- Strategy-specific risk controls
- Margin management and P&L tracking
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any, List
import asyncio

from ..core.logging import get_logger
from ..core.event_bus import EventBus
from ..core.events import EventType, RiskEvent, MarginEvent
from .position_sizer import PositionSizer, PositionSizingResult
from .risk_limits import RiskLimits, RiskLimitsConfig
from .portfolio_risk import PortfolioRiskManager, PortfolioRiskConfig
from .strategy_risk import StrategyRiskManager, StrategyRiskConfig

logger = get_logger(__name__)


@dataclass
class RiskManagementConfig:
    """Risk management system configuration."""
    # Position sizing
    default_sizing_method: str = "percent_of_equity"
    default_risk_per_trade: float = 0.02  # 2%
    
    # Risk limits
    max_position_size: float = 0.1  # 10% of portfolio
    max_total_exposure: float = 5000000  # 5M max exposure
    max_open_positions: int = 50
    
    # Portfolio risk
    daily_loss_limit: float = 50000  # 50K daily loss limit
    max_drawdown_percentage: float = 0.05  # 5% max drawdown
    max_gross_leverage: float = 2.0
    
    # Circuit breakers
    circuit_breaker_enabled: bool = True
    auto_reset_enabled: bool = True


class RiskManager:
    """Main risk management orchestrator."""
    
    def __init__(
        self,
        event_bus: EventBus,
        config: RiskManagementConfig,
        openalgo_gateway=None
    ):
        self.event_bus = event_bus
        self.config = config
        self.openalgo_gateway = openalgo_gateway
        
        # Initialize components
        self.position_sizer = PositionSizer(default_method=config.default_sizing_method)
        
        # Risk limits
        risk_limits_config = RiskLimitsConfig(
            max_total_exposure=config.max_total_exposure,
            max_open_positions=config.max_open_positions
        )
        self.risk_limits = RiskLimits(risk_limits_config)
        
        # Portfolio risk
        portfolio_config = PortfolioRiskConfig(
            daily_loss_limit=config.daily_loss_limit,
            max_intraday_drawdown=config.max_drawdown_percentage,
            max_gross_leverage=config.max_gross_leverage
        )
        self.portfolio_risk = PortfolioRiskManager(portfolio_config)
        
        # Strategy risk
        self.strategy_risk = StrategyRiskManager()
        
        # State tracking
        self.total_equity = 0.0
        self.available_margin = 0.0
        self.used_margin = 0.0
        self.positions: Dict[str, Any] = {}
        
        logger.info("RiskManager initialized", config=config)
    
    async def calculate_position_size(
        self,
        symbol: str,
        signal_type: str,
        suggested_quantity: int,
        price: float,
        strategy_name: str,
        timeframe: str,
        symbol_info: Optional[Dict[str, Any]] = None
    ) -> PositionSizingResult:
        """Calculate optimal position size with comprehensive risk checks."""
        
        logger.info(
            "Calculating position size",
            symbol=symbol,
            signal_type=signal_type,
            suggested_quantity=suggested_quantity,
            price=price,
            strategy_name=strategy_name,
            timeframe=timeframe
        )
        
        # Get strategy risk configuration
        strategy_config = self._get_strategy_config(strategy_name, timeframe)
        
        # Get symbol information (lot size, etc.)
        if not symbol_info and self.openalgo_gateway:
            symbol_info = await self.openalgo_gateway.get_symbol_info(symbol)
        
        lot_size = symbol_info.get("lot_size", 1) if symbol_info else 1
        
        # Check if trading is allowed at portfolio level
        trading_allowed, reason = self.portfolio_risk.is_trading_allowed()
        if not trading_allowed:
            return PositionSizingResult(
                final_quantity=0,
                estimated_cost=0,
                num_lots=0,
                lot_size=lot_size,
                sizing_method=self.config.default_sizing_method,
                sizing_rationale="Portfolio risk circuit breaker active",
                risk_amount=0,
                risk_percentage=0,
                available_margin_used=0,
                success=False,
                error_message=reason
            )
        
        # Check strategy-specific limits
        strategy_allowed, strategy_reason = await self.strategy_risk.check_strategy_limits(
            strategy_name, symbol, suggested_quantity, price
        )
        if not strategy_allowed:
            return PositionSizingResult(
                final_quantity=0,
                estimated_cost=0,
                num_lots=0,
                lot_size=lot_size,
                sizing_method=self.config.default_sizing_method,
                sizing_rationale="Strategy risk limits exceeded",
                risk_amount=0,
                risk_percentage=0,
                available_margin_used=0,
                success=False,
                error_message=strategy_reason
            )
        
        # Check risk limits
        limits_allowed, limits_reason = await self.risk_limits.check_order_limits(
            symbol, signal_type, suggested_quantity, price
        )
        if not limits_allowed:
            return PositionSizingResult(
                final_quantity=0,
                estimated_cost=0,
                num_lots=0,
                lot_size=lot_size,
                sizing_method=self.config.default_sizing_method,
                sizing_rationale="Risk limits exceeded",
                risk_amount=0,
                risk_percentage=0,
                available_margin_used=0,
                success=False,
                error_message=limits_reason
            )
        
        # Calculate position size
        sizing_result = await self.position_sizer.calculate_position_size(
            symbol=symbol,
            signal_type=signal_type,
            suggested_quantity=suggested_quantity,
            price=price,
            lot_size=lot_size,
            available_margin=self.available_margin,
            total_equity=self.total_equity,
            strategy_config=strategy_config,
            symbol_info=symbol_info
        )
        
        if sizing_result.success:
            logger.info(
                "Position sizing successful",
                symbol=symbol,
                final_quantity=sizing_result.final_quantity,
                estimated_cost=sizing_result.estimated_cost,
                sizing_method=sizing_result.sizing_method,
                risk_percentage=sizing_result.risk_percentage
            )
        else:
            logger.error(
                "Position sizing failed",
                symbol=symbol,
                error_message=sizing_result.error_message
            )
        
        return sizing_result
    
    async def approve_trade(
        self,
        symbol: str,
        signal_type: str,
        quantity: int,
        price: float,
        strategy_name: str,
        timeframe: str,
        estimated_cost: float
    ) -> tuple[bool, Optional[str]]:
        """Approve or reject trade based on comprehensive risk analysis."""
        
        logger.info(
            "Approving trade",
            symbol=symbol,
            signal_type=signal_type,
            quantity=quantity,
            price=price,
            strategy_name=strategy_name,
            timeframe=timeframe,
            estimated_cost=estimated_cost
        )
        
        # Check portfolio risk
        trading_allowed, reason = self.portfolio_risk.is_trading_allowed()
        if not trading_allowed:
            return False, f"Portfolio risk: {reason}"
        
        # Check strategy risk
        strategy_allowed, strategy_reason = await self.strategy_risk.check_strategy_limits(
            strategy_name, symbol, quantity, price
        )
        if not strategy_allowed:
            return False, f"Strategy risk: {strategy_reason}"
        
        # Check risk limits
        limits_allowed, limits_reason = await self.risk_limits.check_order_limits(
            symbol, signal_type, quantity, price
        )
        if not limits_allowed:
            return False, f"Risk limits: {limits_reason}"
        
        # Check margin availability
        if estimated_cost > self.available_margin:
            return False, f"Insufficient margin: {estimated_cost} > {self.available_margin}"
        
        # Lock margin pessimistically
        await self._lock_margin(symbol, estimated_cost)
        
        logger.info("Trade approved", symbol=symbol, quantity=quantity, estimated_cost=estimated_cost)
        return True, None
    
    async def process_trade_execution(
        self,
        symbol: str,
        signal_type: str,
        quantity: int,
        price: float,
        strategy_name: str,
        actual_cost: float,
        success: bool
    ) -> None:
        """Process trade execution results and update risk state."""
        
        logger.info(
            "Processing trade execution",
            symbol=symbol,
            signal_type=signal_type,
            quantity=quantity,
            price=price,
            strategy_name=strategy_name,
            actual_cost=actual_cost,
            success=success
        )
        
        # Update risk limits exposure
        await self.risk_limits.update_exposure(symbol, quantity, price, signal_type)
        
        # Update strategy state
        pnl = 0.0  # Would be calculated from actual execution
        await self.strategy_risk.update_strategy_trade(
            strategy_name, symbol, quantity, price, pnl, success
        )
        
        # Release/reconcile margin
        await self._release_margin(symbol, actual_cost, success)
        
        # Publish risk events
        if success:
            await self.event_bus.publish(RiskEvent(
                event_type=EventType.RISK_CHECK_PASSED,
                symbol=symbol,
                data={
                    "quantity": quantity,
                    "price": price,
                    "actual_cost": actual_cost,
                    "strategy": strategy_name
                }
            ))
        else:
            await self.event_bus.publish(RiskEvent(
                event_type=EventType.RISK_CHECK_FAILED,
                symbol=symbol,
                data={
                    "quantity": quantity,
                    "price": price,
                    "reason": "Trade execution failed"
                }
            ))
    
    async def update_portfolio_state(
        self,
        positions: Dict[str, Any],
        cash_balance: float,
        total_equity: float,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0
    ) -> None:
        """Update portfolio state and risk metrics."""
        
        self.positions = positions
        self.total_equity = total_equity
        self.available_margin = cash_balance
        self.used_margin = total_equity - cash_balance
        
        # Update portfolio risk manager
        await self.portfolio_risk.update_portfolio_state(positions, cash_balance, total_equity)
        
        # Update P&L tracking
        if realized_pnl != 0.0 or unrealized_pnl != 0.0:
            await self.portfolio_risk.update_pnl(realized_pnl, unrealized_pnl)
            await self.risk_limits.update_pnl(realized_pnl, unrealized_pnl)
        
        logger.info(
            "Updated portfolio state",
            total_equity=total_equity,
            available_margin=cash_balance,
            used_margin=self.used_margin,
            positions_count=len(positions),
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl
        )
    
    async def _lock_margin(self, symbol: str, estimated_cost: float) -> None:
        """Pessimistically lock margin for trade."""
        
        self.available_margin -= estimated_cost
        self.used_margin += estimated_cost
        
        # Publish margin lock event
        await self.event_bus.publish(MarginEvent(
            event_type=EventType.MARGIN_LOCKED,
            symbol=symbol,
            data={
                "estimated_cost": estimated_cost,
                "available_margin": self.available_margin,
                "used_margin": self.used_margin
            }
        ))
        
        logger.info(
            "Margin locked",
            symbol=symbol,
            estimated_cost=estimated_cost,
            available_margin=self.available_margin,
            used_margin=self.used_margin
        )
    
    async def _release_margin(self, symbol: str, actual_cost: float, success: bool) -> None:
        """Release or reconcile margin after trade execution."""
        
        if success:
            # Trade successful - margin was used correctly
            # No additional adjustment needed
            pass
        else:
            # Trade failed - release locked margin
            self.available_margin += actual_cost
            self.used_margin -= actual_cost
        
        # Publish margin release event
        await self.event_bus.publish(MarginEvent(
            event_type=EventType.MARGIN_RELEASED,
            symbol=symbol,
            data={
                "actual_cost": actual_cost,
                "success": success,
                "available_margin": self.available_margin,
                "used_margin": self.used_margin
            }
        ))
        
        logger.info(
            "Margin released/reconciled",
            symbol=symbol,
            actual_cost=actual_cost,
            success=success,
            available_margin=self.available_margin,
            used_margin=self.used_margin
        )
    
    def _get_strategy_config(self, strategy_name: str, timeframe: str) -> Dict[str, Any]:
        """Get strategy-specific risk configuration."""
        
        # This would typically load from configuration
        # For now, return default configuration
        return {
            "sizing_method": self.config.default_sizing_method,
            "risk_per_trade": self.config.default_risk_per_trade,
            "max_position_size": self.config.max_position_size
        }
    
    def register_strategy(self, strategy_name: str, timeframe: str, config: Dict[str, Any]) -> None:
        """Register strategy-specific risk configuration."""
        
        strategy_risk_config = StrategyRiskConfig(
            strategy_name=f"{strategy_name}:{timeframe}",
            sizing_method=config.get("sizing_method", self.config.default_sizing_method),
            risk_per_trade=config.get("risk_per_trade", self.config.default_risk_per_trade),
            max_position_size=config.get("max_position_size", self.config.max_position_size),
            max_concurrent_positions=config.get("max_concurrent_positions", 10),
            max_daily_loss=config.get("max_daily_loss", 10000),
            max_drawdown=config.get("max_drawdown", 0.10)
        )
        
        self.strategy_risk.register_strategy(strategy_risk_config)
        
        logger.info(
            "Strategy risk configuration registered",
            strategy_name=strategy_name,
            timeframe=timeframe,
            config=config
        )
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary."""
        
        return {
            "portfolio_state": {
                "total_equity": self.total_equity,
                "available_margin": self.available_margin,
                "used_margin": self.used_margin,
                "margin_utilization": self.used_margin / self.total_equity if self.total_equity > 0 else 0
            },
            "risk_limits": self.risk_limits.get_exposure_summary(),
            "portfolio_risk": self.portfolio_risk.get_risk_summary(),
            "strategy_risk": self.strategy_risk.get_all_strategies_risk_summary()
        }
    
    async def reset_circuit_breaker(self, breaker_type: str, identifier: Optional[str] = None) -> bool:
        """Reset circuit breaker (admin function)."""
        
        if breaker_type == "portfolio":
            return self.portfolio_risk.reset_circuit_breaker(identifier) if identifier else self.portfolio_risk.reset_all_circuit_breakers()
        elif breaker_type == "risk_limits":
            return self.risk_limits.reset_circuit_breaker()
        elif breaker_type == "strategy":
            if identifier:
                return self.strategy_risk.reset_strategy_circuit_breaker(identifier)
        
        return False