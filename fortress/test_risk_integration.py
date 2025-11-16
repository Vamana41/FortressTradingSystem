"""Simple test script for Risk Management integration."""

import asyncio
from fortress.core.event_bus import EventBus
from fortress.brain import FortressBrain

async def test_brain_integration():
    """Test Risk Management integration with Fortress Brain."""
    print("Testing Risk Management integration with Fortress Brain...")
    
    # Initialize components
    event_bus = EventBus()
    brain = FortressBrain('test_brain')
    
    await brain.initialize(event_bus)
    print("✓ Brain initialized with event bus")
    
    # Register a strategy
    await brain.register_strategy('MA_CROSSOVER', '1H', 'RELIANCE', {'risk_per_trade': 0.02})
    print("✓ Strategy registered")
    
    # Update portfolio state
    positions = {
        'RELIANCE': {
            'net_quantity': 100, 
            'average_price': 2500.0, 
            'realized_pnl': 5000, 
            'unrealized_pnl': 2000
        }
    }
    await brain.update_portfolio_state(
        positions=positions,
        cash_balance=200000,
        total_equity=1000000,
        realized_pnl=5000,
        unrealized_pnl=2000
    )
    print("✓ Portfolio state updated")
    
    # Test signal processing with risk management
    success = await brain.process_signal(
        symbol='RELIANCE',
        signal_type='BUY',
        quantity=50,
        timeframe='1H',
        strategy_name='MA_CROSSOVER',
        price=2600.0
    )
    print(f"✓ Signal processing result: {success}")
    
    # Get risk summary
    risk_summary = brain.get_risk_summary()
    print(f"✓ Risk summary retrieved:")
    print(f"  - Portfolio equity: {risk_summary['portfolio_state']['total_equity']}")
    print(f"  - Available margin: {risk_summary['portfolio_state']['available_margin']}")
    print(f"  - Margin utilization: {risk_summary['portfolio_state']['margin_utilization']:.2%}")
    
    print("\n✅ Risk Management integration test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_brain_integration())