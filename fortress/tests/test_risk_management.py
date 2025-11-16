"""Comprehensive tests for Risk Management System."""

import asyncio
import pytest
from datetime import datetime

from fortress.core.events import EventBus, EventType
from fortress.core.event_bus import EventBus
from fortress.risk_management import (
    PositionSizer, 
    SizingMethod, 
    PositionSizingResult,
    RiskLimits,
    RiskLimitsConfig,
    PortfolioRiskManager,
    PortfolioRiskConfig,
    StrategyRiskManager,
    StrategyRiskConfig,
    RiskManager,
    RiskManagementConfig
)


class TestPositionSizer:
    """Test position sizing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sizer = PositionSizer()
    
    @pytest.mark.asyncio
    async def test_percent_of_equity_sizing(self):
        """Test percent of equity position sizing."""
        result = await self.sizer.calculate_position_size(
            symbol="RELIANCE",
            signal_type="BUY",
            suggested_quantity=100,
            price=2500.0,
            lot_size=1,
            available_margin=100000,
            total_equity=500000,
            strategy_config={"risk_per_trade": 0.02, "max_position_size": 0.1}
        )
        
        assert result.success
        assert result.final_quantity > 0
        assert result.sizing_method == SizingMethod.PERCENT_OF_EQUITY.value
        assert result.risk_percentage <= 10.0  # Max 10% of equity
        assert result.estimated_cost <= 100000  # Within available margin
    
    @pytest.mark.asyncio
    async def test_fixed_cash_sizing(self):
        """Test fixed cash position sizing."""
        result = await self.sizer.calculate_position_size(
            symbol="RELIANCE",
            signal_type="BUY",
            suggested_quantity=100,
            price=2500.0,
            lot_size=1,
            available_margin=100000,
            total_equity=500000,
            strategy_config={
                "sizing_method": SizingMethod.FIXED_CASH,
                "fixed_cash_per_trade": 25000
            }
        )
        
        assert result.success
        assert result.final_quantity > 0
        assert result.sizing_method == SizingMethod.FIXED_CASH.value
        assert result.risk_amount <= 25000
    
    @pytest.mark.asyncio
    async def test_minimum_lot_requirement(self):
        """Test minimum lot size requirement."""
        result = await self.sizer.calculate_position_size(
            symbol="NIFTY",
            signal_type="BUY",
            suggested_quantity=25,  # Less than 1 lot
            price=18000.0,
            lot_size=50,  # NIFTY lot size
            available_margin=100000,
            total_equity=500000,
            strategy_config={"risk_per_trade": 0.02}
        )
        
        assert result.success
        assert result.final_quantity >= 50  # Minimum 1 lot
        assert result.num_lots >= 1
    
    @pytest.mark.asyncio
    async def test_insufficient_margin(self):
        """Test insufficient margin handling."""
        result = await self.sizer.calculate_position_size(
            symbol="RELIANCE",
            signal_type="BUY",
            suggested_quantity=1000,
            price=2500.0,
            lot_size=1,
            available_margin=1000,  # Very low margin
            total_equity=5000,
            strategy_config={"risk_per_trade": 0.02}
        )
        
        assert not result.success
        assert "Cannot afford one lot" in result.error_message
    
    @pytest.mark.asyncio
    async def test_invalid_price(self):
        """Test invalid price handling."""
        result = await self.sizer.calculate_position_size(
            symbol="RELIANCE",
            signal_type="BUY",
            suggested_quantity=100,
            price=0,  # Invalid price
            lot_size=1,
            available_margin=100000,
            total_equity=500000,
            strategy_config={"risk_per_trade": 0.02}
        )
        
        assert not result.success
        assert "Invalid price for sizing" in result.error_message


class TestRiskLimits:
    """Test risk limits functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = RiskLimitsConfig(
            max_total_exposure=1000000,
            max_open_positions=10,
            max_orders_per_minute=5,
            max_orders_per_hour=50,
            daily_loss_limit=25000
        )
        self.risk_limits = RiskLimits(config)
    
    @pytest.mark.asyncio
    async def test_order_rate_limits(self):
        """Test order rate limiting."""
        # First few orders should pass
        for i in range(3):
            allowed, reason = await self.risk_limits.check_order_limits(
                symbol="RELIANCE", order_type="BUY", quantity=100, price=2500.0
            )
            assert allowed
            assert reason is None
        
        # Exceed rate limit
        for i in range(10):
            await self.risk_limits.check_order_limits(
                symbol="RELIANCE", order_type="BUY", quantity=100, price=2500.0
            )
        
        # Should now fail rate limit
        allowed, reason = await self.risk_limits.check_order_limits(
            symbol="RELIANCE", order_type="BUY", quantity=100, price=2500.0
        )
        assert not allowed
        assert "Orders per minute limit exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_position_limits(self):
        """Test position limit enforcement."""
        # Configure symbol-specific limits
        self.risk_limits.config.symbol_limits["RELIANCE"] = ExposureLimits(
            max_lots=5,
            max_notional=125000,
            max_net_quantity=500
        )
        
        # Should allow within limits
        allowed, reason = await self.risk_limits.check_order_limits(
            symbol="RELIANCE", order_type="BUY", quantity=100, price=2500.0
        )
        assert allowed
        
        # Update exposure to near limit
        await self.risk_limits.update_exposure("RELIANCE", 400, 2500.0, "BUY")
        
        # Should fail position limit
        allowed, reason = await self.risk_limits.check_order_limits(
            symbol="RELIANCE", order_type="BUY", quantity=200, price=2500.0
        )
        assert not allowed
        assert "Symbol net quantity limit exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_on_loss_limit(self):
        """Test circuit breaker activation on loss limit."""
        # Simulate large loss
        await self.risk_limits.update_pnl(-30000, -5000)  # Exceeds 25K daily limit
        
        # Should trigger circuit breaker
        allowed, reason = await self.risk_limits.check_order_limits(
            symbol="RELIANCE", order_type="BUY", quantity=100, price=2500.0
        )
        assert not allowed
        assert "Circuit breaker active" in reason


class TestPortfolioRiskManager:
    """Test portfolio risk management functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = PortfolioRiskConfig(
            daily_loss_limit=50000,
            max_intraday_drawdown=0.03,
            max_gross_leverage=2.0,
            max_single_position_weight=0.15
        )
        self.portfolio_risk = PortfolioRiskManager(config)
    
    @pytest.mark.asyncio
    async def test_loss_limit_circuit_breaker(self):
        """Test loss limit circuit breaker."""
        positions = {
            "RELIANCE": {"quantity": 100, "price": 2500.0},
            "TCS": {"quantity": 50, "price": 3200.0}
        }
        
        await self.portfolio_risk.update_portfolio_state(
            positions=positions,
            cash_balance=500000,
            total_equity=1000000
        )
        
        # Trigger loss limit
        await self.portfolio_risk.update_pnl(-60000, -10000)
        
        trading_allowed, reason = self.portfolio_risk.is_trading_allowed()
        assert not trading_allowed
        assert "Daily loss limit exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_drawdown_circuit_breaker(self):
        """Test drawdown circuit breaker."""
        # Start with positive P&L
        await self.portfolio_risk.update_pnl(0, 50000)
        
        # Create drawdown that exceeds limit
        await self.portfolio_risk.update_pnl(-2000, -35000)  # Total: 13000, Peak: 50000
        
        trading_allowed, reason = self.portfolio_risk.is_trading_allowed()
        assert not trading_allowed
        assert "Intraday drawdown exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_leverage_circuit_breaker(self):
        """Test leverage circuit breaker."""
        # Create high leverage scenario
        positions = {
            "RELIANCE": {"quantity": 1000, "price": 2500.0},  # 2.5M notional
            "TCS": {"quantity": 1000, "price": 3200.0},        # 3.2M notional
        }
        
        await self.portfolio_risk.update_portfolio_state(
            positions=positions,
            cash_balance=100000,
            total_equity=1000000  # 5.7M exposure vs 1M equity = 5.7x leverage
        )
        
        trading_allowed, reason = self.portfolio_risk.is_trading_allowed()
        assert not trading_allowed
        assert "Gross leverage exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_concentration_circuit_breaker(self):
        """Test concentration circuit breaker."""
        # Create concentrated position
        positions = {
            "RELIANCE": {"quantity": 1000, "price": 2500.0},  # 2.5M position
        }
        
        await self.portfolio_risk.update_portfolio_state(
            positions=positions,
            cash_balance=500000,
            total_equity=1000000  # 2.5M position vs 1M equity = 250% concentration
        )
        
        trading_allowed, reason = self.portfolio_risk.is_trading_allowed()
        assert not trading_allowed
        assert "Single position concentration exceeded" in reason


class TestStrategyRiskManager:
    """Test strategy-specific risk management functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.strategy_risk = StrategyRiskManager()
        
        # Register test strategy
        config = StrategyRiskConfig(
            strategy_name="TEST_STRATEGY",
            risk_per_trade=0.02,
            max_concurrent_positions=5,
            max_daily_loss=10000,
            max_drawdown=0.10,
            win_rate_threshold=0.35
        )
        self.strategy_risk.register_strategy(config)
    
    @pytest.mark.asyncio
    async def test_strategy_position_limits(self):
        """Test strategy position limits."""
        # Fill up to limit
        for i in range(5):
            allowed, reason = await self.strategy_risk.check_strategy_limits(
                strategy_name="TEST_STRATEGY",
                symbol=f"STOCK{i}",
                quantity=100,
                price=1000.0
            )
            assert allowed
            
            # Simulate successful trade
            await self.strategy_risk.update_strategy_trade(
                strategy_name="TEST_STRATEGY",
                symbol=f"STOCK{i}",
                quantity=100,
                price=1000.0,
                pnl=1000.0,
                success=True
            )
        
        # Should fail position limit
        allowed, reason = await self.strategy_risk.check_strategy_limits(
            strategy_name="TEST_STRATEGY",
            symbol="STOCK6",
            quantity=100,
            price=1000.0
        )
        assert not allowed
        assert "Max concurrent positions exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_strategy_daily_loss_limit(self):
        """Test strategy daily loss limit."""
        # Trigger daily loss limit
        await self.strategy_risk.update_strategy_trade(
            strategy_name="TEST_STRATEGY",
            symbol="RELIANCE",
            quantity=100,
            price=2500.0,
            pnl=-15000,  # Exceeds 10K daily limit
            success=True
        )
        
        # Should fail daily loss limit
        allowed, reason = await self.strategy_risk.check_strategy_limits(
            strategy_name="TEST_STRATEGY",
            symbol="TCS",
            quantity=100,
            price=3200.0
        )
        assert not allowed
        assert "Daily loss limit exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_strategy_drawdown_limit(self):
        """Test strategy drawdown limit."""
        # Build up some profits
        for i in range(10):
            await self.strategy_risk.update_strategy_trade(
                strategy_name="TEST_STRATEGY",
                symbol="RELIANCE",
                quantity=100,
                price=2500.0,
                pnl=2000.0,
                success=True
            )
        
        # Create large drawdown
        await self.strategy_risk.update_strategy_trade(
            strategy_name="TEST_STRATEGY",
            symbol="RELIANCE",
            quantity=100,
            price=2500.0,
            pnl=-30000,  # Large loss creating >10% drawdown
            success=True
        )
        
        # Should fail drawdown limit
        allowed, reason = await self.strategy_risk.check_strategy_limits(
            strategy_name="TEST_STRATEGY",
            symbol="TCS",
            quantity=100,
            price=3200.0
        )
        assert not allowed
        assert "Drawdown limit exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_strategy_win_rate_threshold(self):
        """Test strategy win rate threshold."""
        # Create poor performance history
        for i in range(20):
            await self.strategy_risk.update_strategy_trade(
                strategy_name="TEST_STRATEGY",
                symbol="RELIANCE",
                quantity=100,
                price=2500.0,
                pnl=-500.0 if i % 3 == 0 else 200.0,  # More losses than wins
                success=True
            )
        
        # Should fail win rate threshold
        allowed, reason = await self.strategy_risk.check_strategy_limits(
            strategy_name="TEST_STRATEGY",
            symbol="TCS",
            quantity=100,
            price=3200.0
        )
        assert not allowed
        assert "Win rate below threshold" in reason


class TestRiskManagerIntegration:
    """Test integrated risk management system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_bus = EventBus()
        
        config = RiskManagementConfig(
            default_sizing_method="percent_of_equity",
            default_risk_per_trade=0.02,
            max_position_size=0.1,
            max_total_exposure=1000000,
            max_open_positions=20,
            daily_loss_limit=50000,
            max_drawdown_percentage=0.05
        )
        
        self.risk_manager = RiskManager(self.event_bus, config)
    
    @pytest.mark.asyncio
    async def test_comprehensive_risk_approval(self):
        """Test comprehensive risk approval process."""
        # Set up portfolio state
        positions = {
            "RELIANCE": {"quantity": 100, "price": 2500.0, "realized_pnl": 5000},
            "TCS": {"quantity": 50, "price": 3200.0, "realized_pnl": 2000}
        }
        
        await self.risk_manager.update_portfolio_state(
            positions=positions,
            cash_balance=200000,
            total_equity=1000000
        )
        
        # Test position sizing
        sizing_result = await self.risk_manager.calculate_position_size(
            symbol="HDFC",
            signal_type="BUY",
            suggested_quantity=200,
            price=1500.0,
            strategy_name="TEST_STRATEGY",
            timeframe="1H"
        )
        
        assert sizing_result.success
        assert sizing_result.final_quantity > 0
        assert sizing_result.risk_percentage <= 10.0  # Max position size
        
        # Test trade approval
        approved, reason = await self.risk_manager.approve_trade(
            symbol="HDFC",
            signal_type="BUY",
            quantity=sizing_result.final_quantity,
            price=1500.0,
            strategy_name="TEST_STRATEGY",
            timeframe="1H",
            estimated_cost=sizing_result.estimated_cost
        )
        
        assert approved
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_risk_circuit_breaker_integration(self):
        """Test circuit breaker integration across all risk levels."""
        # Trigger portfolio-level circuit breaker
        positions = {
            "RELIANCE": {"quantity": 100, "price": 2500.0, "realized_pnl": 0},
        }
        
        await self.risk_manager.update_portfolio_state(
            positions=positions,
            cash_balance=200000,
            total_equity=1000000
        )
        
        # Create large loss to trigger circuit breaker
        await self.risk_manager.portfolio_risk.update_pnl(-60000, -20000)
        
        # Should fail at portfolio level
        sizing_result = await self.risk_manager.calculate_position_size(
            symbol="HDFC",
            signal_type="BUY",
            suggested_quantity=100,
            price=1500.0,
            strategy_name="TEST_STRATEGY",
            timeframe="1H"
        )
        
        assert not sizing_result.success
        assert "Portfolio risk circuit breaker active" in sizing_result.error_message
    
    @pytest.mark.asyncio
    async def test_risk_summary_reporting(self):
        """Test comprehensive risk summary reporting."""
        # Set up test state
        positions = {
            "RELIANCE": {"quantity": 100, "price": 2500.0, "realized_pnl": 5000},
            "TCS": {"quantity": 50, "price": 3200.0, "realized_pnl": 2000}
        }
        
        await self.risk_manager.update_portfolio_state(
            positions=positions,
            cash_balance=200000,
            total_equity=1000000
        )
        
        # Get risk summary
        summary = self.risk_manager.get_risk_summary()
        
        assert "portfolio_state" in summary
        assert "risk_limits" in summary
        assert "portfolio_risk" in summary
        assert "strategy_risk" in summary
        
        # Verify portfolio state
        assert summary["portfolio_state"]["total_equity"] == 1000000
        assert summary["portfolio_state"]["available_margin"] == 200000
        
        # Verify risk limits
        assert summary["risk_limits"]["total_exposure"] > 0
        assert summary["risk_limits"]["open_positions"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])