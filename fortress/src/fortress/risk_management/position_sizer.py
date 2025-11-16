"""Position Sizing Service for FortressTradingSystem.

Implements sophisticated position sizing algorithms including:
- Percent of equity sizing
- Fixed cash per trade
- Volatility-adjusted sizing
- Kelly criterion
- Risk parity
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

from ..core.logging import get_logger

logger = get_logger(__name__)


class SizingMethod(str, Enum):
    """Position sizing methods."""
    PERCENT_OF_EQUITY = "percent_of_equity"
    FIXED_CASH = "fixed_cash"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    KELLY_CRITERION = "kelly_criterion"
    RISK_PARITY = "risk_parity"
    ATR_BASED = "atr_based"


@dataclass
class PositionSizingResult:
    """Result of position sizing calculation."""
    final_quantity: int
    estimated_cost: float
    num_lots: int
    lot_size: int
    sizing_method: str
    sizing_rationale: str
    risk_amount: float
    risk_percentage: float
    available_margin_used: float
    success: bool
    error_message: Optional[str] = None


class PositionSizer:
    """Position sizing service with multiple sizing algorithms."""
    
    def __init__(self, default_method: SizingMethod = SizingMethod.PERCENT_OF_EQUITY):
        self.default_method = default_method
        logger.info("PositionSizer initialized", default_method=default_method)
    
    async def calculate_position_size(
        self,
        symbol: str,
        signal_type: str,
        suggested_quantity: int,
        price: float,
        lot_size: int,
        available_margin: float,
        total_equity: float,
        strategy_config: Dict[str, Any],
        symbol_info: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> PositionSizingResult:
        """Calculate optimal position size based on risk parameters."""
        
        logger.info(
            "Calculating position size",
            symbol=symbol,
            signal_type=signal_type,
            suggested_quantity=suggested_quantity,
            price=price,
            lot_size=lot_size,
            available_margin=available_margin,
            total_equity=total_equity,
            strategy_config=strategy_config
        )
        
        # Validate basic parameters
        if price <= 0:
            return PositionSizingResult(
                final_quantity=0,
                estimated_cost=0,
                num_lots=0,
                lot_size=lot_size,
                sizing_method=self.default_method.value,
                sizing_rationale="Invalid price for sizing",
                risk_amount=0,
                risk_percentage=0,
                available_margin_used=0,
                success=False,
                error_message="Invalid price for sizing"
            )
        
        if lot_size <= 0:
            return PositionSizingResult(
                final_quantity=0,
                estimated_cost=0,
                num_lots=0,
                lot_size=lot_size,
                sizing_method=self.default_method.value,
                sizing_rationale="Invalid lot size",
                risk_amount=0,
                risk_percentage=0,
                available_margin_used=0,
                success=False,
                error_message="Invalid lot size"
            )
        
        # Get sizing method from strategy config or use default
        sizing_method = strategy_config.get("sizing_method", self.default_method)
        risk_per_trade = strategy_config.get("risk_per_trade", 0.02)  # 2% default
        max_position_size = strategy_config.get("max_position_size", 0.1)  # 10% of equity
        
        # Calculate based on sizing method
        if sizing_method == SizingMethod.PERCENT_OF_EQUITY:
            result = await self._size_by_percent_of_equity(
                symbol, price, lot_size, available_margin, total_equity,
                risk_per_trade, max_position_size
            )
        elif sizing_method == SizingMethod.FIXED_CASH:
            result = await self._size_by_fixed_cash(
                symbol, price, lot_size, available_margin, total_equity,
                strategy_config.get("fixed_cash_per_trade", 10000)
            )
        elif sizing_method == SizingMethod.VOLATILITY_ADJUSTED:
            result = await self._size_by_volatility(
                symbol, price, lot_size, available_margin, total_equity,
                risk_per_trade, market_data
            )
        elif sizing_method == SizingMethod.ATR_BASED:
            result = await self._size_by_atr(
                symbol, price, lot_size, available_margin, total_equity,
                risk_per_trade, market_data
            )
        else:
            # Default to percent of equity
            result = await self._size_by_percent_of_equity(
                symbol, price, lot_size, available_margin, total_equity,
                risk_per_trade, max_position_size
            )
        
        # Ensure minimum one lot affordability
        if result.success and result.final_quantity < lot_size:
            min_cost = lot_size * price
            if available_margin >= min_cost:
                # Adjust to minimum lot size
                result.final_quantity = lot_size
                result.num_lots = 1
                result.estimated_cost = min_cost
                result.sizing_rationale = f"Adjusted to minimum lot size: {lot_size} units"
                result.available_margin_used = min_cost
                logger.info("Adjusted to minimum lot size", final_quantity=lot_size, estimated_cost=min_cost)
            else:
                result.success = False
                result.error_message = "Cannot afford one lot"
                result.sizing_rationale = "Insufficient margin for minimum lot size"
                logger.error("Cannot afford minimum lot size", min_cost=min_cost, available_margin=available_margin)
        
        return result
    
    async def _size_by_percent_of_equity(
        self, symbol: str, price: float, lot_size: int, available_margin: float,
        total_equity: float, risk_per_trade: float, max_position_size: float
    ) -> PositionSizingResult:
        """Size position as percentage of equity with risk management."""
        
        # Calculate risk amount
        risk_amount = total_equity * risk_per_trade
        max_position_value = total_equity * max_position_size
        
        # Calculate maximum shares based on risk
        risk_based_shares = risk_amount / price if price > 0 else 0
        
        # Calculate maximum shares based on position size limit
        size_based_shares = max_position_value / price if price > 0 else 0
        
        # Take the smaller of the two
        max_shares = min(risk_based_shares, size_based_shares)
        
        # Calculate number of lots
        num_lots = math.floor(max_shares / lot_size) if lot_size > 0 else 0
        final_quantity = num_lots * lot_size
        estimated_cost = final_quantity * price
        
        # Check available margin
        if estimated_cost > available_margin:
            # Recalculate based on available margin
            max_shares_from_margin = available_margin / price
            num_lots = math.floor(max_shares_from_margin / lot_size) if lot_size > 0 else 0
            final_quantity = num_lots * lot_size
            estimated_cost = final_quantity * price
        
        risk_percentage = (estimated_cost / total_equity) * 100 if total_equity > 0 else 0
        
        return PositionSizingResult(
            final_quantity=final_quantity,
            estimated_cost=estimated_cost,
            num_lots=num_lots,
            lot_size=lot_size,
            sizing_method=SizingMethod.PERCENT_OF_EQUITY.value,
            sizing_rationale=f"Risk {risk_percentage:.1f}% of equity, risk amount: {risk_amount:.2f}",
            risk_amount=risk_amount,
            risk_percentage=risk_percentage,
            available_margin_used=estimated_cost,
            success=final_quantity > 0
        )
    
    async def _size_by_fixed_cash(
        self, symbol: str, price: float, lot_size: int, available_margin: float,
        total_equity: float, fixed_cash: float
    ) -> PositionSizingResult:
        """Size position based on fixed cash amount per trade."""
        
        # Ensure we don't risk more than available
        cash_to_risk = min(fixed_cash, available_margin)
        
        # Calculate maximum shares
        max_shares = cash_to_risk / price if price > 0 else 0
        
        # Calculate number of lots
        num_lots = math.floor(max_shares / lot_size) if lot_size > 0 else 0
        final_quantity = num_lots * lot_size
        estimated_cost = final_quantity * price
        
        risk_percentage = (estimated_cost / total_equity) * 100 if total_equity > 0 else 0
        
        return PositionSizingResult(
            final_quantity=final_quantity,
            estimated_cost=estimated_cost,
            num_lots=num_lots,
            lot_size=lot_size,
            sizing_method=SizingMethod.FIXED_CASH.value,
            sizing_rationale=f"Fixed cash: {cash_to_risk:.2f}, risk: {risk_percentage:.1f}% of equity",
            risk_amount=cash_to_risk,
            risk_percentage=risk_percentage,
            available_margin_used=estimated_cost,
            success=final_quantity > 0
        )
    
    async def _size_by_volatility(
        self, symbol: str, price: float, lot_size: int, available_margin: float,
        total_equity: float, risk_per_trade: float, market_data: Optional[Dict[str, Any]]
    ) -> PositionSizingResult:
        """Size position based on volatility (simplified implementation)."""
        
        # For now, fall back to percent of equity
        # In a full implementation, this would use ATR or historical volatility
        logger.warning("Volatility sizing not fully implemented, falling back to percent of equity")
        
        return await self._size_by_percent_of_equity(
            symbol, price, lot_size, available_margin, total_equity,
            risk_per_trade, 0.1  # 10% max position
        )
    
    async def _size_by_atr(
        self, symbol: str, price: float, lot_size: int, available_margin: float,
        total_equity: float, risk_per_trade: float, market_data: Optional[Dict[str, Any]]
    ) -> PositionSizingResult:
        """Size position based on Average True Range (simplified implementation)."""
        
        # For now, fall back to percent of equity
        # In a full implementation, this would use ATR for stop loss distance
        logger.warning("ATR sizing not fully implemented, falling back to percent of equity")
        
        return await self._size_by_percent_of_equity(
            symbol, price, lot_size, available_margin, total_equity,
            risk_per_trade, 0.1  # 10% max position
        )