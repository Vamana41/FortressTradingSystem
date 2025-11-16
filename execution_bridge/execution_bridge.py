# ======================================================================================
# ==  Execution Bridge Service (v1.0) - Fortress Trading System                        ==
# ======================================================================================
# The Execution Bridge is the critical missing link in the signal flow chain.
#
# Signal Flow: AmiBroker → Watcher → Strategist → EXECUTION BRIDGE → OpenAlgo → Broker
#
# This service:
# 1. Receives validated trade signals from the Strategist via ZMQ
# 2. Performs final risk validation and position checks
# 3. Places orders through OpenAlgo APIs (WITHOUT modifying OpenAlgo)
# 4. Monitors order execution status
# 5. Publishes execution results back to the event bus
#
# ======================================================================================

import zmq
import json
import logging
import asyncio
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ======================================================================================
# == CONFIGURATION                                                                    ==
# ======================================================================================

# OpenAlgo API Configuration (DO NOT MODIFY OPENALGO)
OPENALGO_BASE_URL = os.getenv("OPENALGO_HOST", "http://127.0.0.1:5000")
OPENALGO_API_KEY = os.getenv("OPENALGO_API_KEY", "")

# ZMQ Configuration
ZMQ_SUB_URL = "tcp://127.0.0.1:5556"  # Subscribe to Strategist
ZMQ_PUB_URL = "tcp://127.0.0.1:5555"  # Publish execution results

# Trading Configuration
MAX_POSITION_SIZE_PERCENT = 0.10  # Max 10% of capital per position
MIN_ORDER_VALUE = 1000  # Minimum order value
MAX_SLIPPAGE_PERCENT = 0.50  # Maximum allowed slippage

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "execution_bridge.log")

# ======================================================================================
# == LOGGING SETUP                                                                    ==
# ======================================================================================

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - EXECUTION_BRIDGE - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ExecutionBridge")

# ======================================================================================
# == OPENALGO API INTEGRATION (CONSUMES ONLY - NO MODIFICATIONS)                    ==
# ======================================================================================

class OpenAlgoAPIClient:
    """Client for OpenAlgo API integration - consumes APIs without modification"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Generic API request handler with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAlgo API request failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_funds(self) -> Dict[str, Any]:
        """Get account funds/margin information"""
        return self._make_request("GET", "/api/v1/funds")

    def get_positions(self) -> Dict[str, Any]:
        """Get current positions"""
        return self._make_request("GET", "/api/v1/positions")

    def get_quotes(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """Get real-time quotes"""
        params = {"symbol": symbol, "exchange": exchange}
        return self._make_request("GET", "/api/v1/quotes", params=params)

    def get_orderbook(self) -> Dict[str, Any]:
        """Get order book"""
        return self._make_request("GET", "/api/v1/orderbook")

    def place_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Place a new order"""
        return self._make_request("POST", "/api/v1/placeorder", json=order_data)

    def modify_order(self, order_id: str, modify_data: Dict[str, Any]) -> Dict[str, Any]:
        """Modify an existing order"""
        data = {"order_id": order_id, **modify_data}
        return self._make_request("PUT", "/api/v1/modifyorder", json=data)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        return self._make_request("DELETE", f"/api/v1/cancelorder/{order_id}")

# ======================================================================================
# == RISK MANAGEMENT ENGINE                                                          ==
# ======================================================================================

class RiskManager:
    """Risk management and position validation"""

    def __init__(self, api_client: OpenAlgoAPIClient):
        self.api_client = api_client
        self._funds_cache = {}
        self._positions_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = 30  # 30 seconds cache

    def _get_funds_data(self) -> Dict[str, Any]:
        """Get funds data with caching"""
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_ttl:
            self._funds_cache = self.api_client.get_funds()
            self._cache_timestamp = current_time
        return self._funds_cache

    def _get_positions_data(self) -> Dict[str, Any]:
        """Get positions data with caching"""
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_ttl:
            self._positions_cache = self.api_client.get_positions()
            self._cache_timestamp = current_time
        return self._positions_cache

    def validate_trade_signal(self, signal: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate a trade signal against risk parameters
        Returns: (is_valid, reason)
        """
        try:
            symbol = signal.get("symbol", "")
            action = signal.get("action", "").upper()
            quantity = signal.get("quantity", 0)
            price = signal.get("price", 0)

            # Get current funds and positions
            funds_data = self._get_funds_data()
            positions_data = self._get_positions_data()

            if funds_data.get("status") != "success":
                return False, "Unable to fetch funds data"

            # Extract available margin
            funds = funds_data.get("data", {})
            available_margin = float(funds.get("availablecash", 0))

            # Calculate order value
            order_value = quantity * price

            # Minimum order value check
            if order_value < MIN_ORDER_VALUE:
                return False, f"Order value {order_value:.2f} below minimum {MIN_ORDER_VALUE}"

            # Maximum position size check
            max_position_value = available_margin * MAX_POSITION_SIZE_PERCENT
            if order_value > max_position_value:
                return False, f"Order value {order_value:.2f} exceeds max position size {max_position_value:.2f}"

            # Check existing positions for the symbol
            if positions_data.get("status") == "success":
                positions = positions_data.get("data", [])
                for pos in positions:
                    if pos.get("symbol") == symbol:
                        current_qty = abs(int(pos.get("quantity", 0)))
                        if action == "BUY" and current_qty > 0:
                            return False, f"Already have {current_qty} shares of {symbol}"
                        break

            # Get current market price for slippage check
            if action == "BUY":
                quote_data = self.api_client.get_quotes(symbol, signal.get("exchange", "NSE"))
                if quote_data.get("status") == "success":
                    market_price = float(quote_data.get("data", {}).get("ltp", price))
                    slippage = abs(price - market_price) / market_price * 100
                    if slippage > MAX_SLIPPAGE_PERCENT:
                        return False, f"Slippage {slippage:.2f}% exceeds maximum {MAX_SLIPPAGE_PERCENT}%"

            return True, "Signal validated successfully"

        except Exception as e:
            logger.error(f"Error validating trade signal: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"

# ======================================================================================
# == ORDER EXECUTION ENGINE                                                           ==
# ======================================================================================

class OrderExecutor:
    """Handles order placement and monitoring"""

    def __init__(self, api_client: OpenAlgoAPIClient, risk_manager: RiskManager):
        self.api_client = api_client
        self.risk_manager = risk_manager

    async def execute_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a validated trade signal
        Returns execution result with order details
        """
        try:
            # Validate signal first
            is_valid, reason = self.risk_manager.validate_trade_signal(signal)
            if not is_valid:
                logger.warning(f"Signal validation failed: {reason}")
                return {
                    "status": "rejected",
                    "reason": reason,
                    "signal": signal,
                    "timestamp": datetime.now().isoformat()
                }

            # Prepare order data for OpenAlgo
            order_data = {
                "strategy": signal.get("source", "ExecutionBridge"),
                "symbol": signal.get("symbol"),
                "action": signal.get("action"),
                "exchange": signal.get("exchange", "NSE"),
                "price_type": signal.get("order_type", "MARKET"),
                "product": signal.get("product", "MIS"),
                "quantity": signal.get("quantity")
            }

            # Add price if limit order
            if signal.get("price"):
                order_data["price"] = signal.get("price")

            logger.info(f"Placing order via OpenAlgo: {order_data}")

            # Place the order through OpenAlgo API
            order_response = self.api_client.place_order(order_data)

            if order_response.get("status") == "success":
                order_id = order_response.get("orderid")
                logger.info(f"Order placed successfully: {order_id}")

                # Wait a moment for order processing
                await asyncio.sleep(2)

                # Check order status
                orderbook = self.api_client.get_orderbook()
                order_status = "unknown"

                if orderbook.get("status") == "success":
                    orders = orderbook.get("data", {}).get("orders", [])
                    for order in orders:
                        if order.get("orderid") == order_id:
                            order_status = order.get("order_status", "unknown")
                            break

                return {
                    "status": "executed",
                    "order_id": order_id,
                    "order_status": order_status,
                    "signal": signal,
                    "order_response": order_response,
                    "timestamp": datetime.now().isoformat()
                }

            else:
                error_msg = order_response.get("message", "Unknown error")
                logger.error(f"Order placement failed: {error_msg}")
                return {
                    "status": "failed",
                    "reason": error_msg,
                    "signal": signal,
                    "order_response": order_response,
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Error executing signal: {e}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e),
                "signal": signal,
                "timestamp": datetime.now().isoformat()
            }

# ======================================================================================
# == MAIN EXECUTION BRIDGE SERVICE                                                   ==
# ======================================================================================

class ExecutionBridge:
    """Main Execution Bridge Service"""

    def __init__(self):
        # Initialize OpenAlgo API client
        self.api_client = OpenAlgoAPIClient(OPENALGO_BASE_URL, OPENALGO_API_KEY)

        # Initialize components
        self.risk_manager = RiskManager(self.api_client)
        self.order_executor = OrderExecutor(self.api_client, self.risk_manager)

        # ZMQ sockets
        self.context = None
        self.sub_socket = None
        self.pub_socket = None

        logger.info("Execution Bridge initialized")
        logger.info(f"OpenAlgo API endpoint: {OPENALGO_BASE_URL}")
        logger.info(f"ZMQ Subscriber: {ZMQ_SUB_URL}")
        logger.info(f"ZMQ Publisher: {ZMQ_PUB_URL}")

    async def process_execution_request(self, signal: Dict[str, Any]) -> None:
        """Process an execution request from the Strategist"""
        logger.info(f"Processing execution request: {signal}")

        try:
            # Execute the signal
            result = await self.order_executor.execute_signal(signal)

            # Publish result to event bus
            topic = "events.execution.result"
            message = json.dumps(result)

            self.pub_socket.send_string(f"{topic} {message}")
            logger.info(f"Published execution result: {topic}")

        except Exception as e:
            logger.error(f"Error processing execution request: {e}", exc_info=True)

            # Publish error result
            error_result = {
                "status": "error",
                "reason": str(e),
                "signal": signal,
                "timestamp": datetime.now().isoformat()
            }

            try:
                self.pub_socket.send_string(f"events.execution.result {json.dumps(error_result)}")
            except Exception as pub_err:
                logger.critical(f"Failed to publish error result: {pub_err}")

    async def run(self) -> None:
        """Main execution loop"""
        try:
            # Setup ZMQ
            self.context = zmq.Context()

            # Subscriber socket for execution requests
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.connect(ZMQ_SUB_URL)
            self.sub_socket.subscribe("request.execute_order")

            # Publisher socket for results
            self.pub_socket = self.context.socket(zmq.PUB)
            self.pub_socket.connect(ZMQ_PUB_URL)

            logger.info("Execution Bridge is running and listening for signals...")

            while True:
                try:
                    # Receive execution request
                    string = self.sub_socket.recv_string()
                    topic, message = string.split(' ', 1)

                    if topic == "request.execute_order":
                        signal_data = json.loads(message)
                        logger.info(f"Received execution request on topic: {topic}")

                        # Process the request asynchronously
                        asyncio.create_task(self.process_execution_request(signal_data))

                except zmq.ZMQError as e:
                    logger.error(f"ZMQ error: {e}")
                    await asyncio.sleep(1)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Execution Bridge shutting down...")
        except Exception as e:
            logger.critical(f"Fatal error in Execution Bridge: {e}", exc_info=True)
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            if self.sub_socket:
                self.sub_socket.close()
            if self.pub_socket:
                self.pub_socket.close()
            if self.context:
                self.context.term()
            logger.info("Execution Bridge cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# ======================================================================================
# == MAIN ENTRY POINT                                                                ==
# ======================================================================================

async def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("STARTING EXECUTION BRIDGE SERVICE")
    logger.info("="*60)

    # Validate configuration
    if not OPENALGO_API_KEY:
        logger.critical("OPENALGO_API_KEY not configured in environment variables")
        return

    if not OPENALGO_BASE_URL:
        logger.critical("OPENALGO_HOST not configured in environment variables")
        return

    # Create and run the execution bridge
    bridge = ExecutionBridge()

    try:
        await bridge.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.critical(f"Execution Bridge failed: {e}", exc_info=True)
    finally:
        logger.info("Execution Bridge stopped")

if __name__ == "__main__":
    # Test OpenAlgo connectivity before starting
    print("Testing OpenAlgo connectivity...")
    test_client = OpenAlgoAPIClient(OPENALGO_BASE_URL, OPENALGO_API_KEY)
    test_response = test_client.get_funds()

    if test_response.get("status") == "success":
        print("✅ OpenAlgo connection successful")
        print("🚀 Starting Execution Bridge Service...")
        asyncio.run(main())
    else:
        print("❌ OpenAlgo connection failed. Please check configuration.")
        print(f"Response: {test_response}")
