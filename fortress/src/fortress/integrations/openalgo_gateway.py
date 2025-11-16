# ===================================================================================
# ==                 Fortress Trading System: OpenAlgo Gateway                       ==
# ===================================================================================
#
# This module provides integration with OpenAlgo - the single gateway to brokers.
# OpenAlgo holds the Fyers token and provides unified API access to multiple brokers.
# Our Fortress system communicates with OpenAlgo via HTTP API, never directly with brokers.
#
# Key Features:
# - Unified broker API access through OpenAlgo
# - Position synchronization with broker accounts
# - Order placement and management
# - Real-time market data and quotes
# - Funds and margin information
# - Comprehensive error handling and retry logic
#
# ===================================================================================

import asyncio
import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ..core.logging import get_logger
from ..core.event_bus import EventBus
from ..core.events import Event, EventType


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ProductType(str, Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    MARGIN = "MARGIN"
    BO = "BO"  # Bracket Order
    CO = "CO"  # Cover Order


@dataclass
class OrderParams:
    symbol: str
    quantity: int
    side: OrderSide
    order_type: OrderType
    product_type: ProductType
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    disclosed_quantity: Optional[int] = None
    validity: str = "DAY"


@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    product_type: str
    exchange: str
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class Funds:
    available_margin: float
    used_margin: float
    total_balance: float
    cash_balance: float


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    quantity: int
    filled_quantity: int
    price: float
    status: str
    order_type: str
    product_type: str
    exchange: str
    timestamp: str


@dataclass
class Trade:
    trade_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: str
    exchange: str


@dataclass
class Holding:
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    total_value: float
    pnl: float
    exchange: str


@dataclass
class PnLDataPoint:
    timestamp: str
    pnl: float
    mtm: float


@dataclass
class PnLTracker:
    """Real-time P&L tracking data structure."""
    current_mtm: float
    max_mtm: float
    min_mtm: float
    max_mtm_time: str
    min_mtm_time: str
    max_drawdown: float
    pnl_curve: List[PnLDataPoint]
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float


class OpenAlgoGateway:
    """
    OpenAlgo Gateway - Single point of access to all brokers.
    
    This class provides a unified interface to interact with OpenAlgo,
    which serves as the single gateway to multiple brokers including Fyers,
    Zerodha, Angel, and others.
    """
    
    def __init__(self, 
                 api_key: str,
                 base_url: str = "http://localhost:5000/api/v1",
                 event_bus: Optional[EventBus] = None):
        """
        Initialize OpenAlgo Gateway.
        
        Args:
            api_key: OpenAlgo API key for authentication
            base_url: OpenAlgo server base URL (default: http://localhost:8080/api/v1)
            event_bus: Optional event bus for publishing events
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.event_bus = event_bus
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = get_logger("openalgo_gateway")
        
        # Rate limiting
        self._last_request_time = datetime.min
        self._min_request_interval = 0.1  # 100ms between requests
        
        self.logger.info(f"OpenAlgo Gateway initialized with base URL: {self.base_url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Establish connection to OpenAlgo server."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "FortressTradingSystem/1.0"
                }
            )
            self.logger.info("Connected to OpenAlgo server")
    
    async def disconnect(self):
        """Close connection to OpenAlgo server."""
        if self.session:
            try:
                await self.session.aclose()
            except Exception as e:
                self.logger.warning(f"Error closing session: {e}")
            finally:
                self.session = None
                self.logger.info("Disconnected from OpenAlgo server")
    
    async def _rate_limit(self):
        """Implement rate limiting between requests."""
        now = datetime.now()
        time_since_last = (now - self._last_request_time).total_seconds()
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = datetime.now()
    
    async def _make_request(self, 
                           method: str, 
                           endpoint: str, 
                           data: Optional[Dict[str, Any]] = None,
                           params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Make HTTP request to OpenAlgo API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters
            
        Returns:
            API response as dictionary
            
        Raises:
            httpx.HTTPError: On network errors
            ValueError: On API errors
        """
        if not self.session:
            raise RuntimeError("Gateway not connected. Call connect() first.")
        
        await self._rate_limit()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Add API key to request
        request_data = data.copy() if data else {}
        request_data["apikey"] = self.api_key
        
        self.logger.debug(f"Making {method} request to {url}")
        
        try:
            if method in ["POST", "PUT"]:
                response = await self.session.request(
                    method=method,
                    url=url,
                    json=request_data,
                    timeout=30.0
                )
            else:  # GET, DELETE
                response = await self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=30.0
                )
            
            response_text = response.text
            self.logger.debug(f"Response status: {response.status_code}, body: {response_text[:500]}")
            
            if response.status_code != 200:
                raise httpx.HTTPError(f"HTTP {response.status_code}: {response_text}")
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON response: {response_text}") from e
            
            # Check OpenAlgo-specific status
            if result.get("status") == "error":
                raise ValueError(f"API error: {result.get('message', 'Unknown error')}")
            
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(f"Request timeout to {url}")
            raise
        except httpx.HTTPError as e:
            self.logger.error(f"Request failed to {url}: {e}")
            raise
    
    # ==================== Account Information APIs ====================
    
    async def get_orderbook(self) -> List[Order]:
        """
        Get all orders for the day from broker.
        
        Returns:
            List of Order objects
        """
        self.logger.info("Fetching orderbook from broker")
        
        try:
            response = await self._make_request("POST", "orderbook")
            
            orders = []
            if response.get("status") == "success" and response.get("data"):
                # Handle the correct structure: data contains 'orders' key
                data = response["data"]
                if isinstance(data, dict) and "orders" in data:
                    orders_list = data["orders"]
                else:
                    orders_list = data if isinstance(data, list) else []
                
                for order_data in orders_list:
                    order = Order(
                        order_id=order_data.get("order_id", ""),
                        symbol=order_data.get("symbol", ""),
                        side=order_data.get("side", ""),
                        quantity=order_data.get("quantity", 0),
                        filled_quantity=order_data.get("filled_quantity", 0),
                        price=order_data.get("price", 0.0),
                        status=order_data.get("status", ""),
                        order_type=order_data.get("order_type", ""),
                        product_type=order_data.get("product_type", ""),
                        exchange=order_data.get("exchange", "NSE"),
                        timestamp=order_data.get("timestamp", "")
                    )
                    orders.append(order)
            
            self.logger.info(f"Retrieved {len(orders)} orders from orderbook")
            return orders
            
        except Exception as e:
            self.logger.error(f"Failed to get orderbook: {e}")
            raise
    
    async def get_tradebook(self) -> List[Trade]:
        """
        Get executed trades from broker.
        
        Returns:
            List of Trade objects
        """
        self.logger.info("Fetching tradebook from broker")
        
        try:
            response = await self._make_request("POST", "tradebook")
            
            trades = []
            if response.get("status") == "success" and response.get("data"):
                for trade_data in response["data"]:
                    trade = Trade(
                        trade_id=trade_data.get("trade_id", ""),
                        order_id=trade_data.get("order_id", ""),
                        symbol=trade_data.get("symbol", ""),
                        side=trade_data.get("side", ""),
                        quantity=trade_data.get("quantity", 0),
                        price=trade_data.get("price", 0.0),
                        timestamp=trade_data.get("timestamp", ""),
                        exchange=trade_data.get("exchange", "NSE")
                    )
                    trades.append(trade)
            
            self.logger.info(f"Retrieved {len(trades)} trades from tradebook")
            return trades
            
        except Exception as e:
            self.logger.error(f"Failed to get tradebook: {e}")
            raise
    
    async def get_positionbook(self) -> List[Position]:
        """
        Get detailed position information from broker.
        
        Returns:
            List of Position objects with detailed information
        """
        self.logger.info("Fetching positionbook from broker")
        
        try:
            response = await self._make_request("POST", "positionbook")
            
            positions = []
            if response.get("status") == "success" and response.get("data"):
                for pos_data in response["data"]:
                    position = Position(
                        symbol=pos_data.get("symbol", ""),
                        quantity=pos_data.get("quantity", 0),
                        average_price=pos_data.get("average_price", 0.0),
                        product_type=pos_data.get("product_type", "INTRADAY"),
                        exchange=pos_data.get("exchange", "NSE"),
                        realized_pnl=pos_data.get("realized_pnl", 0.0),
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0.0)
                    )
                    positions.append(position)
            
            self.logger.info(f"Retrieved {len(positions)} positions from positionbook")
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get positionbook: {e}")
            raise
    
    async def get_holdings(self) -> List[Holding]:
        """
        Get stock holdings with P&L details from broker.
        
        Returns:
            List of Holding objects
        """
        self.logger.info("Fetching holdings from broker")
        
        try:
            response = await self._make_request("POST", "holdings")
            
            holdings = []
            if response.get("status") == "success" and response.get("data"):
                holdings_data = response["data"]
                if isinstance(holdings_data, dict) and "holdings" in holdings_data:
                    holdings_list = holdings_data["holdings"]
                else:
                    holdings_list = holdings_data if isinstance(holdings_data, list) else []
                
                for holding_data in holdings_list:
                    holding = Holding(
                        symbol=holding_data.get("symbol", ""),
                        quantity=holding_data.get("quantity", 0),
                        average_price=holding_data.get("average_price", 0.0),
                        current_price=holding_data.get("current_price", 0.0),
                        total_value=holding_data.get("total_value", 0.0),
                        pnl=holding_data.get("pnl", 0.0),
                        exchange=holding_data.get("exchange", "NSE")
                    )
                    holdings.append(holding)
            
            self.logger.info(f"Retrieved {len(holdings)} holdings from broker")
            return holdings
            
        except Exception as e:
            self.logger.error(f"Failed to get holdings: {e}")
            raise
    
    async def get_positions(self) -> List[Position]:
        """
        Get current open positions from broker.
        
        Returns:
            List of Position objects
        """
        self.logger.info("Fetching positions from broker")
        
        try:
            response = await self._make_request("POST", "positionbook")
            
            positions = []
            if response.get("status") == "success" and response.get("data"):
                for pos_data in response["data"]:
                    # Handle different position formats from different brokers
                    position = Position(
                        symbol=pos_data.get("symbol", ""),
                        quantity=pos_data.get("quantity", 0),
                        average_price=pos_data.get("average_price", 0.0),
                        product_type=pos_data.get("product_type", "INTRADAY"),
                        exchange=pos_data.get("exchange", "NSE"),
                        realized_pnl=pos_data.get("realized_pnl", 0.0),
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0.0)
                    )
                    positions.append(position)
            
            self.logger.info(f"Retrieved {len(positions)} positions from broker")
            
            # Publish event
            if self.event_bus:
                event = Event(
                    event_id=f"pos_sync_{int(datetime.now().timestamp() * 1000)}",
                    event_type=EventType.POSITION_SYNC,
                    source="openalgo_gateway",
                    data={"positions": [vars(pos) for pos in positions]}
                )
                await self.event_bus.publish(event)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            raise
    
    async def get_funds(self) -> Funds:
        """
        Get account funds and margin information.
        
        Returns:
            Funds object with account information
        """
        self.logger.info("Fetching funds from broker")
        
        try:
            response = await self._make_request("POST", "funds")
            
            if response.get("status") == "success" and response.get("data"):
                funds_data = response["data"]
                
                # Handle different fund formats from different brokers
                funds = Funds(
                    available_margin=funds_data.get("available_margin", 0.0),
                    used_margin=funds_data.get("used_margin", 0.0),
                    total_balance=funds_data.get("total_balance", 0.0),
                    cash_balance=funds_data.get("cash_balance", 0.0)
                )
                
                self.logger.info(f"Retrieved funds: Available Margin: {funds.available_margin}")
                
                # Publish event
                if self.event_bus:
                    event = Event(
                        event_id=f"funds_update_{int(datetime.now().timestamp() * 1000)}",
                        event_type=EventType.FUNDS_UPDATE,
                        source="openalgo_gateway",
                        data=vars(funds)
                    )
                    await self.event_bus.publish(event)
                
                return funds
            else:
                raise ValueError("Invalid funds response format")
                
        except Exception as e:
            self.logger.error(f"Failed to get funds: {e}")
            raise
    
    async def cancel_all_orders(self) -> bool:
        """
        Cancel all pending orders.
        
        Returns:
            True if all orders were cancelled successfully
        """
        self.logger.info("Cancelling all pending orders")
        
        try:
            response = await self._make_request("POST", "cancelallorder")
            
            success = response.get("status") == "success"
            
            if success:
                self.logger.info("All orders cancelled successfully")
                
                # Publish event
                if self.event_bus:
                    event = Event(
                        event_id=f"all_orders_cancelled_{int(datetime.now().timestamp() * 1000)}",
                        event_type=EventType.ORDER_CANCELLED,
                        source="openalgo_gateway",
                        data={"action": "cancel_all"}
                    )
                    await self.event_bus.publish(event)
            else:
                self.logger.warning(f"Failed to cancel all orders: {response.get('message')}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to cancel all orders: {e}")
            raise
    
    async def close_position(self, symbol: str, exchange: str = "NSE", 
                           product_type: Optional[str] = None) -> bool:
        """
        Close open position for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (default: NSE)
            product_type: Product type (optional)
            
        Returns:
            True if position was closed successfully
        """
        self.logger.info(f"Closing position for {symbol} on {exchange}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange
            }
            
            if product_type:
                data["product_type"] = product_type
            
            response = await self._make_request("POST", "closeposition", data=data)
            
            success = response.get("status") == "success"
            
            if success:
                self.logger.info(f"Position for {symbol} closed successfully")
            else:
                self.logger.warning(f"Failed to close position for {symbol}: {response.get('message')}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to close position for {symbol}: {e}")
            raise
    
    async def place_basket_order(self, orders: List[Dict[str, Any]]) -> List[str]:
        """
        Execute multiple orders in a single request.
        
        Args:
            orders: List of order dictionaries with required fields:
                   - symbol: Trading symbol
                   - action: BUY/SELL
                   - quantity: Order quantity
                   - pricetype: MARKET/LIMIT/STOP
                   - product: MIS/CNC/NRML
                   - price: Price for LIMIT orders (optional)
                   
        Returns:
            List of order IDs
        """
        self.logger.info(f"Placing basket order with {len(orders)} orders")
        
        try:
            data = {"orders": orders}
            
            response = await self._make_request("POST", "basketorder", data=data)
            
            order_ids = []
            if response.get("status") == "success" and response.get("data"):
                order_ids = response["data"].get("order_ids", [])
                self.logger.info(f"Basket order placed successfully with {len(order_ids)} order IDs")
            else:
                raise ValueError(f"Failed to place basket order: {response.get('message', 'Unknown error')}")
            
            return order_ids
            
        except Exception as e:
            self.logger.error(f"Failed to place basket order: {e}")
            raise
    
    # ==================== Market Data APIs ====================
    
    async def get_depth(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get market depth (order book) for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (default: NSE)
            
        Returns:
            Market depth data with bids and asks
        """
        self.logger.debug(f"Fetching market depth for {symbol} on {exchange}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange
            }
            
            response = await self._make_request("POST", "depth", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                depth_data = response["data"]
                self.logger.debug(f"Retrieved market depth for {symbol}")
                return depth_data
            else:
                raise ValueError(f"Failed to get market depth for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to get market depth for {symbol}: {e}")
            raise
    
    async def get_intervals(self) -> List[str]:
        """
        Get supported time intervals for historical data.
        
        Returns:
            List of supported intervals (1m, 5m, 15m, 1h, 1D, etc.)
        """
        self.logger.debug("Fetching supported intervals")
        
        try:
            response = await self._make_request("POST", "intervals")
            
            if response.get("status") == "success" and response.get("data"):
                intervals = response["data"].get("intervals", [])
                self.logger.debug(f"Retrieved {len(intervals)} supported intervals")
                return intervals
            else:
                raise ValueError("Failed to get supported intervals")
                
        except Exception as e:
            self.logger.error(f"Failed to get intervals: {e}")
            raise
    
    async def get_symbol_info(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get detailed information about a trading symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (default: NSE)
            
        Returns:
            Symbol information including lot size, tick size, etc.
        """
        self.logger.debug(f"Fetching symbol info for {symbol} on {exchange}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange
            }
            
            response = await self._make_request("POST", "symbol", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                symbol_data = response["data"]
                self.logger.debug(f"Retrieved symbol info for {symbol}")
                return symbol_data
            else:
                raise ValueError(f"Failed to get symbol info for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to get symbol info for {symbol}: {e}")
            raise
    
    async def search_symbols(self, query: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
        """
        Search for trading symbols.
        
        Args:
            query: Search query (symbol name or partial name)
            exchange: Exchange (default: NSE)
            
        Returns:
            List of matching symbols with details
        """
        self.logger.debug(f"Searching symbols for '{query}' on {exchange}")
        
        try:
            data = {
                "query": query,
                "exchange": exchange
            }
            
            response = await self._make_request("POST", "search", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                symbols = response["data"].get("symbols", [])
                self.logger.debug(f"Found {len(symbols)} matching symbols for '{query}'")
                return symbols
            else:
                raise ValueError(f"Failed to search symbols for '{query}'")
                
        except Exception as e:
            self.logger.error(f"Failed to search symbols for '{query}': {e}")
            raise
    
    async def get_expiry_dates(self, symbol: str, exchange: str = "NFO", 
                              instrument_type: str = "options") -> List[str]:
        """
        Get available expiry dates for derivatives.
        
        Args:
            symbol: Trading symbol (e.g., NIFTY)
            exchange: Exchange (default: NFO)
            instrument_type: 'options' or 'futures' (default: options)
            
        Returns:
            List of expiry dates
        """
        self.logger.debug(f"Fetching expiry dates for {symbol} on {exchange}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange,
                "instrumenttype": instrument_type
            }
            
            response = await self._make_request("POST", "expiry", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                expiry_dates = response["data"].get("expiry_dates", [])
                self.logger.debug(f"Retrieved {len(expiry_dates)} expiry dates for {symbol}")
                return expiry_dates
            else:
                raise ValueError(f"Failed to get expiry dates for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to get expiry dates for {symbol}: {e}")
            raise
    
    async def get_quotes(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get real-time quotes for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (default: NSE)
            
        Returns:
            Quote data dictionary
        """
        self.logger.debug(f"Fetching quotes for {symbol} on {exchange}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange
            }
            
            response = await self._make_request("POST", "quotes", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                quote_data = response["data"]
                self.logger.debug(f"Retrieved quote for {symbol}: LTP {quote_data.get('ltp')}")
                return quote_data
            else:
                raise ValueError(f"Failed to get quotes for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to get quotes for {symbol}: {e}")
            raise
    
    async def get_history(self, 
                         symbol: str, 
                         exchange: str = "NSE",
                         interval: str = "1m",
                         from_date: Optional[str] = None,
                         to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (default: NSE)
            interval: Time interval (1m, 5m, 1h, 1D, etc.)
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
            
        Returns:
            List of historical data points
        """
        self.logger.debug(f"Fetching history for {symbol} on {exchange} with interval {interval}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange,
                "interval": interval
            }
            
            if from_date:
                data["from_date"] = from_date
            if to_date:
                data["to_date"] = to_date
            
            response = await self._make_request("POST", "history", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                history_data = response["data"]
                self.logger.debug(f"Retrieved {len(history_data)} historical data points for {symbol}")
                return history_data
            else:
                raise ValueError(f"Failed to get history for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to get history for {symbol}: {e}")
            raise
    
    # ==================== Order Management APIs ====================
    
    async def place_order(self, order_params: OrderParams, strategy: str = "FortressStrategy", exchange: str = "NSE") -> str:
        """
        Place a new order.
        
        Args:
            order_params: Order parameters
            strategy: Strategy name (default: "FortressStrategy")
            exchange: Exchange (default: "NSE")
            
        Returns:
            Order ID as string
        """
        self.logger.info(f"Placing {order_params.side} order for {order_params.symbol} x{order_params.quantity}")
        
        try:
            data = {
                "strategy": strategy,
                "exchange": exchange,
                "symbol": order_params.symbol,
                "action": order_params.side.value,  # Changed from 'side' to 'action'
                "quantity": order_params.quantity,
                "pricetype": self._map_order_type(order_params.order_type),  # Changed from 'type' to 'pricetype'
                "product": self._map_product_type(order_params.product_type),  # Changed from 'productType' to 'product'
            }
            
            if order_params.price:
                data["price"] = order_params.price
            if order_params.trigger_price:
                data["trigger_price"] = order_params.trigger_price
            if order_params.disclosed_quantity:
                data["disclosed_quantity"] = order_params.disclosed_quantity
            
            response = await self._make_request("POST", "placeorder", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                order_id = response["data"].get("order_id", "")
                self.logger.info(f"Order placed successfully: {order_id}")
                
                # Publish event
                if self.event_bus:
                    event = Event(
                        event_id=f"order_placed_{order_id}_{int(datetime.now().timestamp() * 1000)}",
                        event_type=EventType.ORDER_PLACED,
                        source="openalgo_gateway",
                        data={
                            "order_id": order_id,
                            "symbol": order_params.symbol,
                            "quantity": order_params.quantity,
                            "side": order_params.side.value,
                            "order_type": order_params.order_type.value
                        }
                    )
                    await self.event_bus.publish(event)
                
                return order_id
            else:
                raise ValueError(f"Failed to place order: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status information
        """
        self.logger.debug(f"Fetching status for order {order_id}")
        
        try:
            data = {"order_id": order_id}
            response = await self._make_request("POST", "orderstatus", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                return response["data"]
            else:
                raise ValueError(f"Failed to get order status for {order_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to get order status for {order_id}: {e}")
            raise
    
    async def cancel_order(self, order_id: str, strategy: str = "FortressStrategy") -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
            strategy: Strategy name (default: "FortressStrategy")
            
        Returns:
            True if cancellation was successful
        """
        self.logger.info(f"Cancelling order {order_id}")
        
        try:
            data = {
                "strategy": strategy,
                "orderid": order_id
            }
            response = await self._make_request("POST", "cancelorder", data=data)
            
            success = response.get("status") == "success"
            
            if success:
                self.logger.info(f"Order {order_id} cancelled successfully")
                
                # Publish event
                if self.event_bus:
                    event = Event(
                        event_id=f"order_cancelled_{order_id}_{int(datetime.now().timestamp() * 1000)}",
                        event_type=EventType.ORDER_CANCELLED,
                        source="openalgo_gateway",
                        data={"order_id": order_id}
                    )
                    await self.event_bus.publish(event)
            else:
                self.logger.warning(f"Failed to cancel order {order_id}: {response.get('message')}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    async def modify_order(self, 
                          order_id: str, 
                          quantity: Optional[int] = None,
                          price: Optional[float] = None,
                          trigger_price: Optional[float] = None,
                          strategy: str = "FortressStrategy",
                          exchange: str = "NSE",
                          symbol: Optional[str] = None,
                          action: Optional[str] = None,
                          product: str = "MIS",
                          pricetype: str = "MARKET") -> bool:
        """
        Modify an existing pending order.
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
            strategy: Strategy name (default: "FortressStrategy")
            exchange: Exchange (default: "NSE")
            symbol: Symbol (optional)
            action: Action BUY/SELL (optional)
            product: Product type (default: "MIS")
            pricetype: Price type (default: "MARKET")
            
        Returns:
            True if modification was successful
        """
        self.logger.info(f"Modifying order {order_id}")
        
        try:
            data = {
                "strategy": strategy,
                "exchange": exchange,
                "orderid": order_id,
                "product": product,
                "pricetype": pricetype,
                "quantity": quantity if quantity is not None else 1,
                "price": price if price is not None else 0,
                "disclosed_quantity": 0,
                "trigger_price": trigger_price if trigger_price is not None else 0
            }
            
            if symbol is not None:
                data["symbol"] = symbol
            if action is not None:
                data["action"] = action
            
            response = await self._make_request("POST", "modifyorder", data=data)
            
            success = response.get("status") == "success"
            
            if success:
                self.logger.info(f"Order {order_id} modified successfully")
            else:
                self.logger.warning(f"Failed to modify order {order_id}: {response.get('message')}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to modify order {order_id}: {e}")
            raise
    
    # ==================== Utility APIs ====================
    
    async def ping(self) -> Dict[str, Any]:
        """
        Health check endpoint to verify OpenAlgo server is running.
        
        Returns:
            Server status information
        """
        self.logger.debug("Pinging OpenAlgo server")
        
        try:
            response = await self._make_request("POST", "ping")
            
            if response.get("status") == "success":
                self.logger.debug("OpenAlgo server ping successful")
                return response.get("data", {})
            else:
                raise ValueError("Ping failed")
                
        except Exception as e:
            self.logger.error(f"Failed to ping server: {e}")
            raise
    
    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Symbol to get quote for (e.g., "SBIN")
            exchange: Exchange (default: "NSE")
            
        Returns:
            Quote data including bid, ask, last traded price, etc.
        """
        self.logger.debug(f"Fetching quote for {exchange}:{symbol}")
        
        try:
            data = {
                "symbol": symbol,
                "exchange": exchange
            }
            response = await self._make_request("POST", "quotes", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                quote_data = response["data"]
                self.logger.debug(f"Quote retrieved for {exchange}:{symbol}: LTP {quote_data.get('ltp', 0)}")
                return quote_data
            else:
                raise ValueError(f"Failed to get quote for {exchange}:{symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to get quote for {exchange}:{symbol}: {e}")
            raise
    
    async def get_analyzer_status(self) -> Dict[str, Any]:
        """
        Get analyzer (sandbox) mode status.
        
        Returns:
            Analyzer status information including mode and logs
        """
        self.logger.debug("Fetching analyzer status")
        
        try:
            response = await self._make_request("POST", "analyzer/status")
            
            if response.get("status") == "success" and response.get("data"):
                status_data = response["data"]
                self.logger.debug(f"Analyzer status: {status_data.get('mode', 'unknown')}")
                return status_data
            else:
                raise ValueError("Failed to get analyzer status")
                
        except Exception as e:
            self.logger.error(f"Failed to get analyzer status: {e}")
            raise
    
    async def toggle_analyzer(self, mode: bool) -> Dict[str, Any]:
        """
        Toggle analyzer (sandbox) mode.
        
        Args:
            mode: True for analyze mode, False for live mode
            
        Returns:
            Updated analyzer status
        """
        mode_str = "analyze" if mode else "live"
        self.logger.info(f"Toggling analyzer mode to {mode_str}")
        
        try:
            data = {"mode": mode}
            response = await self._make_request("POST", "analyzer/toggle", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                status_data = response["data"]
                self.logger.info(f"Analyzer mode toggled to {status_data.get('mode', 'unknown')}")
                return status_data
            else:
                raise ValueError(f"Failed to toggle analyzer mode: {response.get('message')}")
                
        except Exception as e:
            self.logger.error(f"Failed to toggle analyzer mode: {e}")
            raise
    
    async def calculate_margin(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate margin requirements for single or multiple positions.
        
        Args:
            positions: List of position dictionaries with:
                      - symbol: Trading symbol
                      - exchange: Exchange
                      - action: BUY/SELL
                      - product: MIS/CNC/NRML
                      - pricetype: MARKET/LIMIT/STOP
                      - quantity: Order quantity
                      - price: Price for LIMIT orders (optional)
                      
        Returns:
            Margin calculation results including total margin required
        """
        self.logger.debug(f"Calculating margin for {len(positions)} positions")
        
        try:
            data = {"positions": positions}
            response = await self._make_request("POST", "margin", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                margin_data = response["data"]
                self.logger.debug(f"Margin calculated: {margin_data.get('total_margin_required', 0)}")
                return margin_data
            else:
                raise ValueError(f"Failed to calculate margin: {response.get('message')}")
                
        except Exception as e:
            self.logger.error(f"Failed to calculate margin: {e}")
            raise
    
    # ==================== P&L Tracker API ====================
    
    async def get_pnl_tracker(self) -> PnLTracker:
        """
        Get real-time P&L tracking data with advanced charting capabilities.
        
        This endpoint provides:
        - Current MTM (Mark-to-Market) P&L
        - Max/Min MTM with timestamps
        - Maximum drawdown tracking
        - Interactive intraday P&L curve from 9 AM IST
        - Trading statistics (win/loss ratios)
        
        Returns:
            PnLTracker object with comprehensive P&L data
        """
        self.logger.info("Fetching P&L tracker data")
        
        try:
            response = await self._make_request("POST", "pnltracker/api/pnl")
            
            if response.get("status") == "success" and response.get("data"):
                data = response["data"]
                
                # Parse P&L curve data points
                pnl_curve = []
                if "pnl_curve" in data and data["pnl_curve"]:
                    for point in data["pnl_curve"]:
                        pnl_curve.append(PnLDataPoint(
                            timestamp=point.get("timestamp", ""),
                            pnl=point.get("pnl", 0.0),
                            mtm=point.get("mtm", 0.0)
                        ))
                
                # Create PnLTracker object
                pnl_tracker = PnLTracker(
                    current_mtm=data.get("current_mtm", 0.0),
                    max_mtm=data.get("max_mtm", 0.0),
                    min_mtm=data.get("min_mtm", 0.0),
                    max_mtm_time=data.get("max_mtm_time", ""),
                    min_mtm_time=data.get("min_mtm_time", ""),
                    max_drawdown=data.get("max_drawdown", 0.0),
                    pnl_curve=pnl_curve,
                    total_trades=data.get("total_trades", 0),
                    winning_trades=data.get("winning_trades", 0),
                    losing_trades=data.get("losing_trades", 0),
                    total_pnl=data.get("total_pnl", 0.0),
                    realized_pnl=data.get("realized_pnl", 0.0),
                    unrealized_pnl=data.get("unrealized_pnl", 0.0)
                )
                
                self.logger.info(f"P&L tracker data retrieved: Current MTM: {pnl_tracker.current_mtm}")
                return pnl_tracker
                
            else:
                raise ValueError(f"Failed to get P&L tracker data: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Failed to get P&L tracker data: {e}")
            raise
    
    # ==================== Smart Order APIs ====================
    
    async def place_smart_order(self, 
                               symbol: str,
                               quantity: int,
                               side: OrderSide,
                               product_type: ProductType = ProductType.INTRADAY,
                               stop_loss: Optional[float] = None,
                               target: Optional[float] = None) -> str:
        """
        Place a smart order with automatic stop loss and target.
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            side: BUY or SELL
            product_type: Product type (default: INTRADAY)
            stop_loss: Stop loss price
            target: Target price
            
        Returns:
            Smart order ID
        """
        self.logger.info(f"Placing smart order for {symbol} x{quantity} {side.value}")
        
        try:
            data = {
                "symbol": symbol,
                "quantity": quantity,
                "side": side.value,
                "productType": product_type.value
            }
            
            if stop_loss:
                data["stop_loss"] = stop_loss
            if target:
                data["target"] = target
            
            response = await self._make_request("POST", "orders/smart", data=data)
            
            if response.get("status") == "success" and response.get("data"):
                order_id = response["data"].get("order_id", "")
                self.logger.info(f"Smart order placed successfully: {order_id}")
                return order_id
            else:
                raise ValueError(f"Failed to place smart order: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Failed to place smart order: {e}")
            raise
    
    # ==================== Utility Methods ====================
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map OrderType enum to OpenAlgo format."""
        mapping = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT", 
            OrderType.STOP: "SL",
            OrderType.STOP_LIMIT: "SL-M"
        }
        return mapping.get(order_type, "MARKET")
    
    def _map_product_type(self, product_type: ProductType) -> str:
        """Map ProductType enum to OpenAlgo format."""
        mapping = {
            ProductType.INTRADAY: "MIS",
            ProductType.DELIVERY: "CNC",
            ProductType.MARGIN: "NRML",
            ProductType.BO: "MIS",  # Bracket orders use MIS
            ProductType.CO: "MIS"   # Cover orders use MIS
        }
        return mapping.get(product_type, "MIS")
    
    async def health_check(self) -> bool:
        """
        Check if OpenAlgo server is healthy and accessible.
        
        Returns:
            True if server is healthy
        """
        try:
            # Use ping endpoint for health check
            await self.ping()
            self.logger.info("OpenAlgo gateway health check passed")
            return True
        except Exception as e:
            self.logger.error(f"OpenAlgo gateway health check failed: {e}")
            return False
    
    async def wait_for_order_fill(self, 
                                 order_id: str, 
                                 timeout: int = 60,
                                 poll_interval: int = 2) -> Dict[str, Any]:
        """
        Wait for order to be filled or rejected.
        
        Args:
            order_id: Order ID to monitor
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Final order status
        """
        self.logger.info(f"Waiting for order {order_id} to fill (timeout: {timeout}s)")
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                order_status = await self.get_order_status(order_id)
                
                status = order_status.get("status", "").upper()
                filled_quantity = order_status.get("filled_quantity", 0)
                total_quantity = order_status.get("quantity", 0)
                
                self.logger.debug(f"Order {order_id} status: {status}, filled: {filled_quantity}/{total_quantity}")
                
                # Check if order is complete
                if status in ["COMPLETE", "FILLED", "REJECTED", "CANCELLED"]:
                    self.logger.info(f"Order {order_id} final status: {status}")
                    return order_status
                
                # Check if fully filled
                if filled_quantity >= total_quantity and total_quantity > 0:
                    self.logger.info(f"Order {order_id} fully filled: {filled_quantity}/{total_quantity}")
                    return order_status
                
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                self.logger.warning(f"Error checking order {order_id} status: {e}")
                await asyncio.sleep(poll_interval)
        
        self.logger.warning(f"Order {order_id} timeout after {timeout}s")
        raise TimeoutError(f"Order {order_id} did not complete within {timeout} seconds")


# ==================== Factory Function ====================

async def create_openalgo_gateway(api_key: str, 
                                 base_url: str = "http://localhost:5000/api/v1",
                                 event_bus: Optional[EventBus] = None) -> OpenAlgoGateway:
    """
    Factory function to create and connect OpenAlgo Gateway.
    
    Args:
        api_key: OpenAlgo API key
        base_url: OpenAlgo server base URL
        event_bus: Optional event bus
        
    Returns:
        Connected OpenAlgoGateway instance
    """
    gateway = OpenAlgoGateway(api_key, base_url, event_bus)
    await gateway.connect()
    
    # Perform health check
    if not await gateway.health_check():
        raise RuntimeError("OpenAlgo gateway health check failed")
    
    return gateway