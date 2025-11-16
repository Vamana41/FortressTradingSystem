"""Strategy-specific Risk Management for FortressTradingSystem.

Implements strategy-level risk controls including:
- Strategy-specific position limits
- Risk per trade configuration
- Maximum concurrent positions per strategy
- Strategy correlation monitoring
- Performance-based risk adjustment
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyRiskConfig:
    """Strategy-specific risk configuration."""
    strategy_name: str
    
    # Position sizing
    sizing_method: str = "percent_of_equity"
    risk_per_trade: float = 0.02  # 2% risk per trade
    max_position_size: float = 0.05  # 5% of portfolio per position
    
    # Position limits
    max_concurrent_positions: int = 10  # Maximum positions per strategy
    max_positions_per_symbol: int = 1  # Maximum positions per symbol
    max_pyramid_levels: int = 3  # Maximum pyramid levels
    
    # Risk controls
    max_daily_loss: float = 10000  # Maximum daily loss for strategy
    max_drawdown: float = 0.10  # 10% maximum drawdown
    win_rate_threshold: float = 0.35  # Minimum win rate to continue
    
    # Time-based limits
    max_trades_per_day: int = 20  # Maximum trades per day
    max_trades_per_week: int = 100  # Maximum trades per week
    
    # Performance adjustment
    adjust_risk_based_on_performance: bool = True
    risk_adjustment_factor: float = 0.5  # Reduce risk by 50% on poor performance
    performance_lookback_days: int = 30  # Days to look back for performance


class StrategyRiskManager:
    """Strategy-level risk manager with performance-based adjustments."""
    
    def __init__(self):
        self.strategy_configs: Dict[str, StrategyRiskConfig] = {}
        self.strategy_states: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "positions": {},
            "daily_trades": 0,
            "weekly_trades": 0,
            "daily_pnl": 0.0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "peak_pnl": 0.0,
            "current_drawdown": 0.0,
            "circuit_breaker": False,
            "last_trade_time": None,
            "trade_history": [],
            "performance_metrics": {}
        })
        
        self.last_reset_time = datetime.now()
        
        logger.info("StrategyRiskManager initialized")
    
    def register_strategy(self, config: StrategyRiskConfig) -> None:
        """Register a strategy with its risk configuration."""
        
        self.strategy_configs[config.strategy_name] = config
        logger.info(
            "Strategy registered",
            strategy_name=config.strategy_name,
            risk_per_trade=config.risk_per_trade,
            max_concurrent_positions=config.max_concurrent_positions
        )
    
    async def check_strategy_limits(
        self, strategy_name: str, symbol: str, quantity: int, price: float
    ) -> tuple[bool, Optional[str]]:
        """Check if trade complies with strategy-specific limits."""
        
        if strategy_name not in self.strategy_configs:
            return False, f"Strategy {strategy_name} not registered"
        
        config = self.strategy_configs[strategy_name]
        state = self.strategy_states[strategy_name]
        
        # Reset daily/weekly counters if needed
        await self._reset_counters_if_needed(strategy_name)
        
        # Check circuit breaker
        if state["circuit_breaker"]:
            return False, f"Circuit breaker active for strategy {strategy_name}"
        
        # Check daily loss limit
        if abs(state["daily_pnl"]) > config.max_daily_loss:
            return False, f"Daily loss limit exceeded for strategy {strategy_name}"
        
        # Check trade frequency limits
        if state["daily_trades"] >= config.max_trades_per_day:
            return False, f"Daily trade limit exceeded for strategy {strategy_name}"
        
        if state["weekly_trades"] >= config.max_trades_per_week:
            return False, f"Weekly trade limit exceeded for strategy {strategy_name}"
        
        # Check position limits
        current_positions = len(state["positions"])
        if current_positions >= config.max_concurrent_positions:
            return False, f"Max concurrent positions exceeded for strategy {strategy_name}"
        
        # Check symbol-specific limits
        symbol_positions = sum(1 for pos in state["positions"].values() if pos.get("symbol") == symbol)
        if symbol_positions >= config.max_positions_per_symbol:
            return False, f"Max positions per symbol exceeded for strategy {strategy_name}"
        
        # Check win rate threshold
        if state["win_rate"] < config.win_rate_threshold and len(state["trade_history"]) > 10:
            return False, f"Win rate below threshold for strategy {strategy_name}"
        
        # Check drawdown limit
        if state["current_drawdown"] > config.max_drawdown:
            return False, f"Drawdown limit exceeded for strategy {strategy_name}"
        
        return True, None
    
    async def update_strategy_trade(
        self, strategy_name: str, symbol: str, quantity: int, price: float,
        pnl: float, success: bool
    ) -> None:
        """Update strategy state after trade execution."""
        
        if strategy_name not in self.strategy_states:
            return
        
        state = self.strategy_states[strategy_name]
        config = self.strategy_configs.get(strategy_name)
        
        if not config:
            return
        
        # Update trade counters
        state["daily_trades"] += 1
        state["weekly_trades"] += 1
        
        # Update P&L
        state["daily_pnl"] += pnl
        state["total_pnl"] += pnl
        
        # Update peak P&L and drawdown
        if state["total_pnl"] > state["peak_pnl"]:
            state["peak_pnl"] = state["total_pnl"]
        
        state["current_drawdown"] = (state["peak_pnl"] - state["total_pnl"]) / state["peak_pnl"] if state["peak_pnl"] > 0 else 0
        state["max_drawdown"] = max(state["max_drawdown"], state["current_drawdown"])
        
        # Update trade history
        trade_record = {
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "pnl": pnl,
            "success": success,
            "timestamp": datetime.now()
        }
        state["trade_history"].append(trade_record)
        
        # Keep only recent trades for performance calculation
        if len(state["trade_history"]) > 100:
            state["trade_history"] = state["trade_history"][-100:]
        
        # Update win rate
        if len(state["trade_history"]) > 0:
            winning_trades = sum(1 for trade in state["trade_history"] if trade["pnl"] > 0)
            state["win_rate"] = winning_trades / len(state["trade_history"])
        
        # Update position tracking
        if success:
            position_key = f"{symbol}"
            if quantity > 0:  # Opening position
                state["positions"][position_key] = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "timestamp": datetime.now()
                }
            else:  # Closing position
                state["positions"].pop(position_key, None)
        
        # Adjust risk based on performance if enabled
        if config.adjust_risk_based_on_performance:
            await self._adjust_risk_based_on_performance(strategy_name)
        
        # Check circuit breakers
        await self._check_strategy_circuit_breakers(strategy_name)
        
        logger.info(
            "Strategy trade updated",
            strategy_name=strategy_name,
            symbol=symbol,
            pnl=pnl,
            success=success,
            daily_pnl=state["daily_pnl"],
            win_rate=state["win_rate"],
            drawdown=state["current_drawdown"]
        )
    
    async def _adjust_risk_based_on_performance(self, strategy_name: str) -> None:
        """Adjust risk parameters based on recent performance."""
        
        state = self.strategy_states[strategy_name]
        config = self.strategy_configs[strategy_name]
        
        if len(state["trade_history"]) < 10:
            return  # Need minimum history
        
        # Calculate recent performance metrics
        recent_trades = state["trade_history"][-20:]  # Last 20 trades
        recent_win_rate = sum(1 for trade in recent_trades if trade["pnl"] > 0) / len(recent_trades)
        recent_pnl = sum(trade["pnl"] for trade in recent_trades)
        
        # Adjust risk if performance is poor
        if recent_win_rate < 0.3 or recent_pnl < 0:  # Poor performance
            new_risk_per_trade = config.risk_per_trade * config.risk_adjustment_factor
            logger.warning(
                "Reducing strategy risk due to poor performance",
                strategy_name=strategy_name,
                recent_win_rate=recent_win_rate,
                recent_pnl=recent_pnl,
                old_risk_per_trade=config.risk_per_trade,
                new_risk_per_trade=new_risk_per_trade
            )
            config.risk_per_trade = new_risk_per_trade
        elif recent_win_rate > 0.7 and recent_pnl > 0:  # Good performance
            # Gradually increase risk back to normal
            new_risk_per_trade = min(
                config.risk_per_trade * 1.1,  # Increase by 10%
                0.02  # Cap at 2% default
            )
            logger.info(
                "Increasing strategy risk due to good performance",
                strategy_name=strategy_name,
                recent_win_rate=recent_win_rate,
                recent_pnl=recent_pnl,
                old_risk_per_trade=config.risk_per_trade,
                new_risk_per_trade=new_risk_per_trade
            )
            config.risk_per_trade = new_risk_per_trade
    
    async def _check_strategy_circuit_breakers(self, strategy_name: str) -> None:
        """Check strategy-specific circuit breakers."""
        
        state = self.strategy_states[strategy_name]
        config = self.strategy_configs[strategy_name]
        
        # Check daily loss limit
        if abs(state["daily_pnl"]) > config.max_daily_loss:
            state["circuit_breaker"] = True
            logger.critical(
                "Strategy circuit breaker triggered: daily loss limit",
                strategy_name=strategy_name,
                daily_loss=abs(state["daily_pnl"]),
                limit=config.max_daily_loss
            )
        
        # Check drawdown limit
        if state["current_drawdown"] > config.max_drawdown:
            state["circuit_breaker"] = True
            logger.critical(
                "Strategy circuit breaker triggered: drawdown limit",
                strategy_name=strategy_name,
                drawdown=state["current_drawdown"],
                limit=config.max_drawdown
            )
        
        # Check win rate after sufficient history
        if len(state["trade_history"]) > 20 and state["win_rate"] < config.win_rate_threshold:
            state["circuit_breaker"] = True
            logger.critical(
                "Strategy circuit breaker triggered: win rate below threshold",
                strategy_name=strategy_name,
                win_rate=state["win_rate"],
                threshold=config.win_rate_threshold
            )
    
    async def _reset_counters_if_needed(self, strategy_name: str) -> None:
        """Reset daily/weekly counters if needed."""
        
        state = self.strategy_states[strategy_name]
        now = datetime.now()
        
        # Reset daily counters
        if now.date() > self.last_reset_time.date():
            state["daily_trades"] = 0
            state["daily_pnl"] = 0.0
            logger.info(f"Reset daily counters for strategy {strategy_name}")
        
        # Reset weekly counters (simplified - reset on Monday)
        if now.weekday() == 0 and now.date() > self.last_reset_time.date():
            state["weekly_trades"] = 0
            logger.info(f"Reset weekly counters for strategy {strategy_name}")
    
    def get_strategy_risk_summary(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get risk summary for a specific strategy."""
        
        if strategy_name not in self.strategy_states:
            return None
        
        state = self.strategy_states[strategy_name]
        config = self.strategy_configs.get(strategy_name)
        
        if not config:
            return None
        
        return {
            "strategy_name": strategy_name,
            "config": {
                "risk_per_trade": config.risk_per_trade,
                "max_concurrent_positions": config.max_concurrent_positions,
                "max_daily_loss": config.max_daily_loss,
                "max_drawdown": config.max_drawdown,
                "win_rate_threshold": config.win_rate_threshold
            },
            "state": {
                "positions": len(state["positions"]),
                "daily_trades": state["daily_trades"],
                "weekly_trades": state["weekly_trades"],
                "daily_pnl": state["daily_pnl"],
                "total_pnl": state["total_pnl"],
                "win_rate": state["win_rate"],
                "current_drawdown": state["current_drawdown"],
                "max_drawdown": state["max_drawdown"],
                "circuit_breaker": state["circuit_breaker"],
                "trade_history_count": len(state["trade_history"])
            }
        }
    
    def get_all_strategies_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary for all strategies."""
        
        summary = {}
        for strategy_name in self.strategy_configs:
            summary[strategy_name] = self.get_strategy_risk_summary(strategy_name)
        
        return summary
    
    def reset_strategy_circuit_breaker(self, strategy_name: str) -> bool:
        """Reset circuit breaker for a specific strategy."""
        
        if strategy_name in self.strategy_states:
            self.strategy_states[strategy_name]["circuit_breaker"] = False
            logger.warning(f"Strategy circuit breaker manually reset: {strategy_name}")
            return True
        
        return False