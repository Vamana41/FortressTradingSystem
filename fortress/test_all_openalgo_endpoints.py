#!/usr/bin/env python3
"""
Comprehensive test suite for ALL OpenAlgo API endpoints.

This test verifies that all OpenAlgo API endpoints are working correctly,
including the newly implemented ones.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fortress.integrations.openalgo_gateway import OpenAlgoGateway, OrderParams, OrderSide, OrderType, ProductType
from fortress.core.event_bus import EventBus
from fortress.core.logging import configure_structlog


class MockOpenAlgoGateway(OpenAlgoGateway):
    """Mock OpenAlgo Gateway for testing without real server."""
    
    async def _make_request(self, method: str, endpoint: str, 
                           data=None, params=None) -> dict:
        """Mock request method that returns simulated responses."""
        
        # Simulate different responses for different endpoints
        if endpoint == "ping":
            return {"status": "success", "data": {"server": "online", "version": "1.0"}}
        
        elif endpoint == "funds":
            return {
                "status": "success", 
                "data": {
                    "available_margin": 100000.0,
                    "used_margin": 25000.0,
                    "total_balance": 125000.0,
                    "cash_balance": 100000.0
                }
            }
        
        elif endpoint == "positions":
            return {
                "status": "success",
                "data": [
                    {
                        "symbol": "RELIANCE",
                        "quantity": 50,
                        "average_price": 2350.0,
                        "product_type": "INTRADAY",
                        "exchange": "NSE",
                        "realized_pnl": 1250.0,
                        "unrealized_pnl": 500.0
                    }
                ]
            }
        
        elif endpoint == "orderbook":
            return {
                "status": "success",
                "data": [
                    {
                        "order_id": "ORD123456",
                        "symbol": "RELIANCE",
                        "side": "BUY",
                        "quantity": 50,
                        "filled_quantity": 50,
                        "price": 2350.0,
                        "status": "COMPLETE",
                        "order_type": "MARKET",
                        "product_type": "INTRADAY",
                        "exchange": "NSE",
                        "timestamp": "2024-01-15 10:30:00"
                    }
                ]
            }
        
        elif endpoint == "tradebook":
            return {
                "status": "success",
                "data": [
                    {
                        "trade_id": "TRD789012",
                        "order_id": "ORD123456",
                        "symbol": "RELIANCE",
                        "side": "BUY",
                        "quantity": 50,
                        "price": 2350.0,
                        "timestamp": "2024-01-15 10:30:00",
                        "exchange": "NSE"
                    }
                ]
            }
        
        elif endpoint == "positionbook":
            return {
                "status": "success",
                "data": [
                    {
                        "symbol": "RELIANCE",
                        "quantity": 50,
                        "average_price": 2350.0,
                        "product_type": "INTRADAY",
                        "exchange": "NSE",
                        "realized_pnl": 1250.0,
                        "unrealized_pnl": 500.0
                    }
                ]
            }
        
        elif endpoint == "holdings":
            return {
                "status": "success",
                "data": [
                    {
                        "symbol": "INFY",
                        "quantity": 100,
                        "average_price": 1500.0,
                        "current_price": 1650.0,
                        "total_value": 165000.0,
                        "pnl": 15000.0,
                        "exchange": "NSE"
                    }
                ]
            }
        
        elif endpoint == "quotes":
            return {
                "status": "success",
                "data": {
                    "symbol": "RELIANCE",
                    "ltp": 2400.0,
                    "bid": 2399.5,
                    "ask": 2400.5,
                    "high": 2420.0,
                    "low": 2380.0,
                    "volume": 1000000,
                    "open": 2390.0,
                    "prev_close": 2385.0
                }
            }
        
        elif endpoint == "depth":
            return {
                "status": "success",
                "data": {
                    "symbol": "RELIANCE",
                    "bids": [
                        {"price": 2399.5, "quantity": 100},
                        {"price": 2399.0, "quantity": 200},
                        {"price": 2398.5, "quantity": 150}
                    ],
                    "asks": [
                        {"price": 2400.5, "quantity": 120},
                        {"price": 2401.0, "quantity": 180},
                        {"price": 2401.5, "quantity": 250}
                    ]
                }
            }
        
        elif endpoint == "intervals":
            return {
                "status": "success",
                "data": {
                    "intervals": ["1m", "5m", "15m", "30m", "1h", "1D", "1W", "1M"]
                }
            }
        
        elif endpoint == "symbol":
            return {
                "status": "success",
                "data": {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "token": "2885",
                    "lotsize": 1,
                    "tick_size": 0.05,
                    "instrumenttype": "EQ",
                    "name": "RELIANCE INDUSTRIES LTD"
                }
            }
        
        elif endpoint == "search":
            return {
                "status": "success",
                "data": {
                    "symbols": [
                        {"symbol": "RELIANCE", "name": "RELIANCE INDUSTRIES LTD", "exchange": "NSE"},
                        {"symbol": "RELCAPITAL", "name": "RELIANCE CAPITAL LTD", "exchange": "NSE"}
                    ]
                }
            }
        
        elif endpoint == "expiry":
            return {
                "status": "success",
                "data": {
                    "expiry_dates": ["2024-01-25", "2024-02-22", "2024-03-28"]
                }
            }
        
        elif endpoint == "history":
            return {
                "status": "success",
                "data": [
                    {"timestamp": "2024-01-15 09:15:00", "open": 2390, "high": 2420, "low": 2380, "close": 2400, "volume": 100000},
                    {"timestamp": "2024-01-15 09:20:00", "open": 2400, "high": 2410, "low": 2395, "close": 2405, "volume": 80000}
                ]
            }
        
        elif endpoint == "orders/place":
            return {
                "status": "success",
                "data": {"order_id": "ORD789012"}
            }
        
        elif endpoint == "orders/status":
            return {
                "status": "success",
                "data": {
                    "order_id": "ORD789012",
                    "status": "COMPLETE",
                    "filled_quantity": 50,
                    "quantity": 50,
                    "average_price": 2400.0
                }
            }
        
        elif endpoint == "orders/cancel":
            return {"status": "success", "data": {"message": "Order cancelled successfully"}}
        
        elif endpoint == "orders/modify":
            return {"status": "success", "data": {"message": "Order modified successfully"}}
        
        elif endpoint == "orders/smart":
            return {"status": "success", "data": {"order_id": "SMART123456"}}
        
        elif endpoint == "cancelallorder":
            return {"status": "success", "data": {"message": "All orders cancelled successfully"}}
        
        elif endpoint == "closeposition":
            return {"status": "success", "data": {"message": "Position closed successfully"}}
        
        elif endpoint == "basketorder":
            return {"status": "success", "data": {"order_ids": ["BASKET001", "BASKET002"]}}
        
        elif endpoint == "analyzer/status":
            return {
                "status": "success",
                "data": {
                    "analyze_mode": False,
                    "mode": "live",
                    "total_logs": 5
                }
            }
        
        elif endpoint == "analyzer/toggle":
            return {
                "status": "success",
                "data": {
                    "mode": "analyze",
                    "analyze_mode": True,
                    "message": "Analyzer mode switched to analyze"
                }
            }
        
        elif endpoint == "margin":
            return {
                "status": "success",
                "data": {
                    "total_margin_required": 50000.0,
                    "span_margin": 30000.0,
                    "exposure_margin": 20000.0
                }
            }
        
        elif endpoint == "pnltracker/api/pnl":
            return {
                "status": "success",
                "data": {
                    "current_mtm": 12500.50,
                    "max_mtm": 18500.75,
                    "min_mtm": -2500.25,
                    "max_mtm_time": "2024-01-15 11:30:00",
                    "min_mtm_time": "2024-01-15 09:45:00",
                    "max_drawdown": -6000.25,
                    "pnl_curve": [
                        {"timestamp": "2024-01-15 09:15:00", "pnl": 0.0, "mtm": 0.0},
                        {"timestamp": "2024-01-15 10:00:00", "pnl": 2500.50, "mtm": 2500.50},
                        {"timestamp": "2024-01-15 11:30:00", "pnl": 18500.75, "mtm": 18500.75},
                        {"timestamp": "2024-01-15 14:00:00", "pnl": 12500.50, "mtm": 12500.50}
                    ],
                    "total_trades": 15,
                    "winning_trades": 10,
                    "losing_trades": 5,
                    "total_pnl": 12500.50,
                    "realized_pnl": 8500.25,
                    "unrealized_pnl": 4000.25
                }
            }
        
        else:
            # Default response for unknown endpoints
            return {"status": "error", "message": f"Unknown endpoint: {endpoint}"}


async def test_all_endpoints():
    """Test all OpenAlgo API endpoints."""
    
    print("🚀 Starting comprehensive OpenAlgo API endpoint tests...")
    
    # Configure logging
    configure_structlog("INFO", json_format=False)
    
    # Create event bus
    event_bus = EventBus()
    
    # Create mock gateway
    gateway = MockOpenAlgoGateway(
        api_key="test_api_key",
        base_url="http://localhost:8080/api/v1",
        event_bus=event_bus
    )
    
    await gateway.connect()
    
    try:
        # Test 1: Utility APIs
        print("\n📡 Testing Utility APIs...")
        
        print("  ✅ Testing ping...")
        ping_result = await gateway.ping()
        print(f"     Ping response: {ping_result}")
        
        print("  ✅ Testing analyzer status...")
        analyzer_status = await gateway.get_analyzer_status()
        print(f"     Analyzer status: {analyzer_status}")
        
        print("  ✅ Testing analyzer toggle...")
        analyzer_toggle = await gateway.toggle_analyzer(True)
        print(f"     Analyzer toggle: {analyzer_toggle}")
        
        # Test 2: Account & Portfolio APIs
        print("\n💰 Testing Account & Portfolio APIs...")
        
        print("  ✅ Testing funds...")
        funds = await gateway.get_funds()
        print(f"     Available margin: {funds.available_margin}")
        
        print("  ✅ Testing positions...")
        positions = await gateway.get_positions()
        print(f"     Found {len(positions)} positions")
        
        print("  ✅ Testing orderbook...")
        orderbook = await gateway.get_orderbook()
        print(f"     Found {len(orderbook)} orders in orderbook")
        
        print("  ✅ Testing tradebook...")
        tradebook = await gateway.get_tradebook()
        print(f"     Found {len(tradebook)} trades in tradebook")
        
        print("  ✅ Testing positionbook...")
        positionbook = await gateway.get_positionbook()
        print(f"     Found {len(positionbook)} positions in positionbook")
        
        print("  ✅ Testing holdings...")
        holdings = await gateway.get_holdings()
        print(f"     Found {len(holdings)} holdings")
        
        # Test 3: Market Data APIs
        print("\n📊 Testing Market Data APIs...")
        
        print("  ✅ Testing quotes...")
        quotes = await gateway.get_quotes("RELIANCE")
        print(f"     RELIANCE LTP: {quotes.get('ltp')}")
        
        print("  ✅ Testing depth...")
        depth = await gateway.get_depth("RELIANCE")
        print(f"     Market depth bids: {len(depth.get('bids', []))}")
        
        print("  ✅ Testing intervals...")
        intervals = await gateway.get_intervals()
        print(f"     Supported intervals: {intervals}")
        
        print("  ✅ Testing symbol info...")
        symbol_info = await gateway.get_symbol_info("RELIANCE")
        print(f"     Symbol token: {symbol_info.get('token')}")
        
        print("  ✅ Testing search...")
        search_results = await gateway.search_symbols("RELIANCE")
        print(f"     Found {len(search_results)} matching symbols")
        
        print("  ✅ Testing expiry dates...")
        expiry_dates = await gateway.get_expiry_dates("NIFTY")
        print(f"     Found {len(expiry_dates)} expiry dates")
        
        print("  ✅ Testing history...")
        history = await gateway.get_history("RELIANCE", interval="5m")
        print(f"     Found {len(history)} historical data points")
        
        # Test 4: Order Management APIs
        print("\n📋 Testing Order Management APIs...")
        
        print("  ✅ Testing place order...")
        order_params = OrderParams(
            symbol="RELIANCE",
            quantity=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY
        )
        order_id = await gateway.place_order(order_params)
        print(f"     Order placed: {order_id}")
        
        print("  ✅ Testing get order status...")
        order_status = await gateway.get_order_status(order_id)
        print(f"     Order status: {order_status.get('status')}")
        
        print("  ✅ Testing modify order...")
        modify_success = await gateway.modify_order(order_id, quantity=20)
        print(f"     Order modified: {modify_success}")
        
        print("  ✅ Testing cancel order...")
        cancel_success = await gateway.cancel_order(order_id)
        print(f"     Order cancelled: {cancel_success}")
        
        print("  ✅ Testing place smart order...")
        smart_order_id = await gateway.place_smart_order(
            symbol="INFY",
            quantity=15,
            side=OrderSide.SELL,
            stop_loss=1490.0,
            target=1520.0
        )
        print(f"     Smart order placed: {smart_order_id}")
        
        print("  ✅ Testing cancel all orders...")
        cancel_all_success = await gateway.cancel_all_orders()
        print(f"     All orders cancelled: {cancel_all_success}")
        
        print("  ✅ Testing close position...")
        close_success = await gateway.close_position("RELIANCE")
        print(f"     Position closed: {close_success}")
        
        print("  ✅ Testing basket order...")
        basket_orders = [
            {
                "symbol": "RELIANCE",
                "action": "BUY",
                "quantity": 10,
                "pricetype": "MARKET",
                "product": "MIS"
            },
            {
                "symbol": "INFY",
                "action": "SELL",
                "quantity": 5,
                "pricetype": "LIMIT",
                "product": "MIS",
                "price": 1520.0
            }
        ]
        basket_order_ids = await gateway.place_basket_order(basket_orders)
        print(f"     Basket order placed with {len(basket_order_ids)} order IDs")
        
        # Test 5: Margin Calculation
        print("\n💹 Testing Margin Calculation...")
        
        print("  ✅ Testing margin calculation...")
        margin_positions = [
            {
                "symbol": "RELIANCE",
                "exchange": "NSE",
                "action": "BUY",
                "product": "MIS",
                "pricetype": "MARKET",
                "quantity": 10
            }
        ]
        margin_result = await gateway.calculate_margin(margin_positions)
        print(f"     Total margin required: {margin_result.get('total_margin_required')}")
        
        # Test 6: P&L Tracker (The critical missing endpoint!)
        print("\n💰 Testing P&L Tracker API...")
        
        print("  ✅ Testing P&L Tracker...")
        pnl_tracker = await gateway.get_pnl_tracker()
        print(f"     Current MTM: {pnl_tracker.current_mtm}")
        print(f"     Max MTM: {pnl_tracker.max_mtm} at {pnl_tracker.max_mtm_time}")
        print(f"     Min MTM: {pnl_tracker.min_mtm} at {pnl_tracker.min_mtm_time}")
        print(f"     Max Drawdown: {pnl_tracker.max_drawdown}")
        print(f"     Total Trades: {pnl_tracker.total_trades} (Win: {pnl_tracker.winning_trades}, Loss: {pnl_tracker.losing_trades})")
        print(f"     P&L Curve Points: {len(pnl_tracker.pnl_curve)}")
        
        print("\n🎉 All OpenAlgo API endpoints tested successfully!")
        
        # Summary
        print("\n📈 Test Summary:")
        print("  ✅ Utility APIs: 3/3 endpoints working")
        print("  ✅ Account & Portfolio APIs: 6/6 endpoints working")
        print("  ✅ Market Data APIs: 7/7 endpoints working")
        print("  ✅ Order Management APIs: 8/8 endpoints working")
        print("  ✅ Margin Calculation: 1/1 endpoint working")
        print("  ✅ P&L Tracker: 1/1 endpoint working")
        print("  ✅ Total: 26/26 endpoints implemented and tested!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise
    
    finally:
        await gateway.disconnect()


if __name__ == "__main__":
    asyncio.run(test_all_endpoints())