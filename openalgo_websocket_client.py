#!/usr/bin/env python3
"""
OpenAlgo WebSocket Client for AmiBroker Integration
Connects directly to OpenAlgo's native WebSocket server (ws://127.0.0.1:8765)
without requiring any .dll or MFC dependencies.
"""

import asyncio
import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Callable

import websockets
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OpenAlgoWebSocketClient')

class OpenAlgoWebSocketClient:
    """
    WebSocket client that connects to OpenAlgo's native WebSocket server
    and provides data to AmiBroker through various methods.
    """

    def __init__(self, api_key: str, ws_url: str = "ws://127.0.0.1:8765"):
        self.api_key = api_key
        self.ws_url = ws_url
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self.subscribed_symbols = set()
        self.quote_cache = {}
        self.running = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 60  # seconds
        self.current_reconnect_delay = self.reconnect_delay

        # Callbacks for data handlers
        self.on_quote_callback = None
        self.on_depth_callback = None
        self.on_status_callback = None

    def set_quote_callback(self, callback: Callable[[Dict], None]):
        """Set callback function for quote data"""
        self.on_quote_callback = callback

    def set_depth_callback(self, callback: Callable[[Dict], None]):
        """Set callback function for market depth data"""
        self.on_depth_callback = callback

    def set_status_callback(self, callback: Callable[[str, str], None]):
        """Set callback function for status updates"""
        self.on_status_callback = callback

    async def connect(self) -> bool:
        """Connect to OpenAlgo WebSocket server"""
        try:
            logger.info(f"🔗 Connecting to OpenAlgo WebSocket at {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            logger.info("✅ Connected to WebSocket server")

            # Authenticate
            success = await self.authenticate()
            if success:
                logger.info("✅ Authentication successful")
                self.current_reconnect_delay = self.reconnect_delay  # Reset reconnect delay
                return True
            else:
                logger.error("❌ Authentication failed")
                await self.disconnect()
                return False

        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.connected = False
            return False

    async def authenticate(self) -> bool:
        """Authenticate with OpenAlgo WebSocket server"""
        if not self.websocket or not self.connected:
            return False

        try:
            auth_message = {
                "action": "authenticate",
                "api_key": self.api_key
            }

            logger.debug(f"🔑 Sending authentication: {auth_message}")
            await self.websocket.send(json.dumps(auth_message))

            # Wait for authentication response
            response = await self.websocket.recv()
            auth_response = json.loads(response)

            logger.debug(f"📨 Authentication response: {auth_response}")

            if auth_response.get("status") == "success":
                self.authenticated = True
                if self.on_status_callback:
                    self.on_status_callback("authenticated", "Successfully authenticated with OpenAlgo")
                return True
            else:
                self.authenticated = False
                if self.on_status_callback:
                    self.on_status_callback("auth_failed", f"Authentication failed: {auth_response}")
                return False

        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            self.authenticated = False
            return False

    async def subscribe(self, symbol: str, exchange: str = "NSE", mode: int = 1) -> bool:
        """Subscribe to market data for a symbol"""
        if not self.websocket or not self.connected or not self.authenticated:
            logger.warning("Cannot subscribe - not connected or authenticated")
            return False

        try:
            subscribe_message = {
                "action": "subscribe",
                "symbol": symbol,
                "exchange": exchange,
                "mode": mode
            }

            logger.info(f"🔔 Subscribing to {exchange}:{symbol} mode {mode}")
            await self.websocket.send(json.dumps(subscribe_message))

            # Wait for subscription response
            response = await self.websocket.recv()
            sub_response = json.loads(response)

            logger.debug(f"📨 Subscription response: {sub_response}")

            if sub_response.get("status") == "success":
                self.subscribed_symbols.add(f"{exchange}:{symbol}")
                logger.info(f"✅ Successfully subscribed to {exchange}:{symbol}")
                return True
            else:
                logger.error(f"❌ Subscription failed: {sub_response}")
                return False

        except Exception as e:
            logger.error(f"❌ Subscription error: {e}")
            return False

    async def unsubscribe(self, symbol: str, exchange: str = "NSE") -> bool:
        """Unsubscribe from market data for a symbol"""
        if not self.websocket or not self.connected or not self.authenticated:
            return False

        try:
            unsubscribe_message = {
                "action": "unsubscribe",
                "symbol": symbol,
                "exchange": exchange
            }

            logger.info(f"🔕 Unsubscribing from {exchange}:{symbol}")
            await self.websocket.send(json.dumps(unsubscribe_message))

            self.subscribed_symbols.discard(f"{exchange}:{symbol}")
            return True

        except Exception as e:
            logger.error(f"❌ Unsubscribe error: {e}")
            return False

    async def listen(self):
        """Listen for incoming messages and handle them"""
        if not self.websocket or not self.connected:
            logger.error("Cannot listen - not connected")
            return

        logger.info("👂 Starting to listen for market data...")

        try:
            async for message in self.websocket:
                await self._handle_message(message)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 WebSocket connection closed")
            self.connected = False
            self.authenticated = False
        except Exception as e:
            logger.error(f"❌ Error in listen loop: {e}")
            self.connected = False
            self.authenticated = False

    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            logger.debug(f"📨 Received: {data}")

            # Handle different message types
            if data.get("type") == "market_data":
                await self._handle_market_data(data)
            elif data.get("action") == "authenticate":
                # Authentication response handled in authenticate method
                pass
            elif data.get("action") == "subscribe":
                # Subscription response handled in subscribe method
                pass
            else:
                logger.debug(f"📝 Other message: {data}")

        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON message: {message}")
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")

    async def _handle_market_data(self, data: Dict):
        """Handle market data messages"""
        try:
            symbol = data.get("symbol")
            exchange = data.get("exchange", "NSE")
            mode = data.get("mode")
            market_data = data.get("data", {})

            if not symbol or not market_data:
                return

            # Cache the quote data
            symbol_key = f"{exchange}:{symbol}"
            self.quote_cache[symbol_key] = {
                "symbol": symbol,
                "exchange": exchange,
                "mode": mode,
                "data": market_data,
                "timestamp": datetime.now().isoformat()
            }

            # Call appropriate callback based on mode
            if mode == 1:  # LTP mode
                if self.on_quote_callback:
                    self.on_quote_callback(market_data)

                logger.info(f"📈 {exchange}:{symbol} LTP: {market_data.get('ltp', 'N/A')}")

            elif mode == 2:  # Quote mode
                if self.on_quote_callback:
                    self.on_quote_callback(market_data)

                logger.info(f"📊 {exchange}:{symbol} Quote: O={market_data.get('open', 'N/A')} "
                         f"H={market_data.get('high', 'N/A')} L={market_data.get('low', 'N/A')} "
                         f"C={market_data.get('close', 'N/A')} V={market_data.get('volume', 'N/A')}")

            elif mode == 4:  # Depth mode
                if self.on_depth_callback:
                    self.on_depth_callback(market_data)

                depth = market_data.get('depth', {})
                buy_depth = depth.get('buy', [])
                sell_depth = depth.get('sell', [])

                if buy_depth:
                    logger.info(f"🟢 {exchange}:{symbol} Buy[0]: Price={buy_depth[0].get('price')} "
                             f"Qty={buy_depth[0].get('quantity')}")
                if sell_depth:
                    logger.info(f"🔴 {exchange}:{symbol} Sell[0]: Price={sell_depth[0].get('price')} "
                             f"Qty={sell_depth[0].get('quantity')}")

        except Exception as e:
            logger.error(f"❌ Error handling market data: {e}")

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        self.running = False

        if self.websocket:
            try:
                # Unsubscribe from all symbols
                for symbol_key in list(self.subscribed_symbols):
                    if ':' in symbol_key:
                        exchange, symbol = symbol_key.split(':', 1)
                        await self.unsubscribe(symbol, exchange)

                await self.websocket.close()
                logger.info("🔌 Disconnected from WebSocket server")
            except Exception as e:
                logger.error(f"❌ Error during disconnect: {e}")
            finally:
                self.websocket = None

        self.connected = False
        self.authenticated = False

    async def run(self, symbols: list = None):
        """Main run loop with auto-reconnect"""
        self.running = True

        if self.on_status_callback:
            self.on_status_callback("starting", "Starting WebSocket client")

        while self.running:
            try:
                # Connect to WebSocket
                connected = await self.connect()
                if not connected:
                    logger.warning(f"⚠️  Connection failed, retrying in {self.current_reconnect_delay}s...")
                    await asyncio.sleep(self.current_reconnect_delay)
                    # Exponential backoff
                    self.current_reconnect_delay = min(
                        self.current_reconnect_delay * 2,
                        self.max_reconnect_delay
                    )
                    continue

                # Subscribe to symbols if provided
                if symbols:
                    for symbol_info in symbols:
                        symbol = symbol_info.get("symbol")
                        exchange = symbol_info.get("exchange", "NSE")
                        mode = symbol_info.get("mode", 1)

                        if symbol:
                            await self.subscribe(symbol, exchange, mode)

                # Listen for messages
                await self.listen()

                # If we get here, connection was lost
                logger.warning("🔌 Connection lost, attempting to reconnect...")

            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")

            if self.running:
                logger.warning(f"⚠️  Reconnecting in {self.current_reconnect_delay}s...")
                await asyncio.sleep(self.current_reconnect_delay)
                # Exponential backoff
                self.current_reconnect_delay = min(
                    self.current_reconnect_delay * 2,
                    self.max_reconnect_delay
                )

        if self.on_status_callback:
            self.on_status_callback("stopped", "WebSocket client stopped")

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Dict]:
        """Get cached quote for a symbol"""
        symbol_key = f"{exchange}:{symbol}"
        return self.quote_cache.get(symbol_key)

    def get_all_quotes(self) -> Dict[str, Dict]:
        """Get all cached quotes"""
        return self.quote_cache.copy()

# AmiBroker Integration Functions
def create_amibroker_data_file(symbol: str, data: Dict, filename: str = None):
    """Create AmiBroker-compatible data file"""
    if not filename:
        filename = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # AmiBroker CSV format: Ticker,Date,Open,High,Low,Close,Volume,OI
    csv_content = f"Ticker,Date,Open,High,Low,Close,Volume,OI\n"

    # Extract data
    market_data = data.get("data", {})
    date_str = datetime.now().strftime('%Y%m%d')

    csv_content += f"{symbol},{date_str},"
    csv_content += f"{market_data.get('open', 0)},"
    csv_content += f"{market_data.get('high', 0)},"
    csv_content += f"{market_data.get('low', 0)},"
    csv_content += f"{market_data.get('close', market_data.get('ltp', 0))},"
    csv_content += f"{market_data.get('volume', 0)},"
    csv_content += f"{market_data.get('oi', 0)}\n"

    # Write to file
    with open(filename, 'w') as f:
        f.write(csv_content)

    logger.info(f"📁 Created AmiBroker data file: {filename}")
    return filename

def create_rtd_server_for_amibroker(client: OpenAlgoWebSocketClient, port: int = 8081):
    """Create an RTD server that AmiBroker can connect to"""
    from aiohttp import web

    app = web.Application()

    async def get_quote(request):
        """Get real-time quote"""
        symbol = request.match_info['symbol']
        exchange = request.query.get('exchange', 'NSE')

        quote = client.get_quote(symbol, exchange)
        if quote:
            return web.json_response(quote)
        else:
            return web.json_response({"error": "No data available"}, status=404)

    async def get_all_quotes(request):
        """Get all cached quotes"""
        quotes = client.get_all_quotes()
        return web.json_response(quotes)

    async def get_status(request):
        """Get connection status"""
        return web.json_response({
            "connected": client.connected,
            "authenticated": client.authenticated,
            "subscribed_symbols": list(client.subscribed_symbols),
            "quote_cache_size": len(client.quote_cache)
        })

    # Setup routes
    app.router.add_get('/quote/{symbol}', get_quote)
    app.router.add_get('/quotes', get_all_quotes)
    app.router.add_get('/status', get_status)

    return app

async def main():
    """Main function"""

    # Get API key
    api_key_file = Path.home() / ".fortress" / "openalgo_api_key.txt"
    if not api_key_file.exists():
        logger.error("❌ API key not found. Please run update_api_key.bat first.")
        return

    with open(api_key_file, 'r') as f:
        api_key = f.read().strip()

    # Create WebSocket client
    client = OpenAlgoWebSocketClient(api_key)

    # Set up data callbacks
    def on_quote(data):
        """Handle quote data"""
        logger.info(f"📈 Quote: LTP={data.get('ltp')} Open={data.get('open')} "
                   f"High={data.get('high')} Low={data.get('low')} "
                   f"Volume={data.get('volume')}")

    def on_depth(data):
        """Handle market depth data"""
        depth = data.get('depth', {})
        buy_depth = depth.get('buy', [])
        sell_depth = depth.get('sell', [])

        if buy_depth:
            logger.info(f"🟢 Buy[0]: Price={buy_depth[0].get('price')} "
                       f"Qty={buy_depth[0].get('quantity')}")
        if sell_depth:
            logger.info(f"🔴 Sell[0]: Price={sell_depth[0].get('price')} "
                       f"Qty={sell_depth[0].get('quantity')}")

    def on_status(status, message):
        """Handle status updates"""
        logger.info(f"📡 Status: {status} - {message}")

    client.set_quote_callback(on_quote)
    client.set_depth_callback(on_depth)
    client.set_status_callback(on_status)

    # Define symbols to subscribe to
    symbols = [
        {"symbol": "RELIANCE", "exchange": "NSE", "mode": 1},  # LTP mode
        {"symbol": "INFY", "exchange": "NSE", "mode": 1},
        {"symbol": "TCS", "exchange": "NSE", "mode": 1},
    ]

    try:
        logger.info("🏰 Starting OpenAlgo WebSocket Client for AmiBroker")
        logger.info("=" * 50)
        logger.info("📊 This client connects to OpenAlgo's native WebSocket")
        logger.info("🔌 WebSocket URL: ws://127.0.0.1:8765")
        logger.info("🔑 API Key loaded successfully")
        logger.info("=" * 50)

        # Start the client
        await client.run(symbols)

    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping client...")
        await client.disconnect()
        logger.info("👋 Client stopped")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
