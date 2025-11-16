#!/usr/bin/env python3
"""
OpenAlgo AmiBroker WebSocket Bridge
Direct integration with AmiBroker using WebSocket without any .dll dependencies.
This creates a local RTD server that AmiBroker can connect to via DDE or HTTP.
"""

import asyncio
import json
import logging
import win32com.client
import pythoncom
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
import aiohttp
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OpenAlgoAmiBridge')

class AmiBrokerDDE:
    """DDE Server for AmiBroker integration"""

    def __init__(self, topic: str = "OpenAlgo"):
        self.topic = topic
        self.data = {}
        self.running = False

    def start(self):
        """Start DDE server"""
        try:
            pythoncom.CoInitialize()
            self.server = win32com.client.Dispatch("DDEServer.DDEServer")
            self.server.StartServer(self.topic)
            self.running = True
            logger.info(f"✅ DDE Server started with topic: {self.topic}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start DDE server: {e}")
            return False

    def update_data(self, symbol: str, field: str, value: Any):
        """Update data for DDE"""
        try:
            if self.running:
                self.server.Poke(f"{symbol}", field, str(value))
                logger.debug(f"📊 Updated {symbol}.{field} = {value}")
        except Exception as e:
            logger.error(f"❌ DDE update error: {e}")

    def stop(self):
        """Stop DDE server"""
        try:
            if self.running:
                self.server.StopServer()
                self.running = False
                logger.info("🔌 DDE Server stopped")
        except Exception as e:
            logger.error(f"❌ DDE stop error: {e}")

class OpenAlgoAmiBridge:
    """
    Bridge between OpenAlgo WebSocket and AmiBroker
    Provides multiple integration methods:
    1. DDE (Dynamic Data Exchange) - Real-time data
    2. HTTP API - REST endpoints
    3. CSV Export - File-based import
    """

    def __init__(self, api_key: str, ws_url: str = "ws://127.0.0.1:8765", http_port: int = 8082):
        self.api_key = api_key
        self.ws_url = ws_url
        self.http_port = http_port
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self.quote_cache = {}
        self.subscribed_symbols = set()

        # DDE server
        self.dde_server = AmiBrokerDDE()

        # HTTP server
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes for AmiBroker integration"""
        self.app.router.add_get('/quote/{symbol}', self.get_quote)
        self.app.router.add_get('/quotes', self.get_all_quotes)
        self.app.router.add_get('/export/{symbol}', self.export_csv)
        self.app.router.add_get('/status', self.get_status)
        self.app.router.add_post('/subscribe', self.subscribe_symbol)
        self.app.router.add_post('/dde/update', self.update_dde_data)

    async def connect_websocket(self):
        """Connect to OpenAlgo WebSocket"""
        try:
            import websockets
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            logger.info(f"🔗 Connected to OpenAlgo WebSocket at {self.ws_url}")

            # Authenticate
            auth_message = {
                "action": "authenticate",
                "api_key": self.api_key
            }
            await self.websocket.send(json.dumps(auth_message))

            # Wait for auth response
            response = await self.websocket.recv()
            auth_response = json.loads(response)

            if auth_response.get("status") == "success":
                self.authenticated = True
                logger.info("✅ WebSocket authentication successful")
                return True
            else:
                logger.error(f"❌ WebSocket authentication failed: {auth_response}")
                return False

        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return False

    async def subscribe_symbol(self, symbol: str, exchange: str = "NSE", mode: int = 1):
        """Subscribe to a symbol via WebSocket"""
        if not self.websocket or not self.connected or not self.authenticated:
            return False

        try:
            subscribe_message = {
                "action": "subscribe",
                "symbol": symbol,
                "exchange": exchange,
                "mode": mode
            }

            await self.websocket.send(json.dumps(subscribe_message))
            self.subscribed_symbols.add(f"{exchange}:{symbol}")
            logger.info(f"🔔 Subscribed to {exchange}:{symbol}")
            return True

        except Exception as e:
            logger.error(f"❌ Subscription error: {e}")
            return False

    async def websocket_listener(self):
        """Listen for WebSocket messages"""
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                await self._handle_websocket_message(message)
        except Exception as e:
            logger.error(f"❌ WebSocket listener error: {e}")

    async def _handle_websocket_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)

            if data.get("type") == "market_data":
                symbol = data.get("symbol")
                exchange = data.get("exchange", "NSE")
                market_data = data.get("data", {})

                if symbol and market_data:
                    symbol_key = f"{exchange}:{symbol}"
                    self.quote_cache[symbol_key] = {
                        "symbol": symbol,
                        "exchange": exchange,
                        "data": market_data,
                        "timestamp": datetime.now().isoformat()
                    }

                    # Update DDE if running
                    self.update_dde(symbol, exchange, market_data)

                    # Log the data
                    mode = data.get("mode", 1)
                    if mode == 1:  # LTP
                        logger.info(f"📈 {exchange}:{symbol} LTP: {market_data.get('ltp')}")
                    elif mode == 2:  # Quote
                        logger.info(f"📊 {exchange}:{symbol} O={market_data.get('open')} "
                                   f"H={market_data.get('high')} L={market_data.get('low')} "
                                   f"C={market_data.get('close')} V={market_data.get('volume')}")

        except Exception as e:
            logger.error(f"❌ Message handling error: {e}")

    def update_dde(self, symbol: str, exchange: str, data: Dict):
        """Update DDE server with new data"""
        if self.dde_server.running:
            try:
                # Update common fields
                self.dde_server.update_data(symbol, "LTP", data.get("ltp", 0))
                self.dde_server.update_data(symbol, "OPEN", data.get("open", 0))
                self.dde_server.update_data(symbol, "HIGH", data.get("high", 0))
                self.dde_server.update_data(symbol, "LOW", data.get("low", 0))
                self.dde_server.update_data(symbol, "CLOSE", data.get("close", 0))
                self.dde_server.update_data(symbol, "VOLUME", data.get("volume", 0))
                self.dde_server.update_data(symbol, "OI", data.get("oi", 0))
                self.dde_server.update_data(symbol, "TIMESTAMP", datetime.now().strftime("%H:%M:%S"))

            except Exception as e:
                logger.error(f"❌ DDE update error: {e}")

    # HTTP API handlers
    async def get_quote(self, request):
        """Get quote via HTTP API"""
        symbol = request.match_info['symbol']
        exchange = request.query.get('exchange', 'NSE')
        symbol_key = f"{exchange}:{symbol}"

        if symbol_key in self.quote_cache:
            quote = self.quote_cache[symbol_key]
            return web.json_response(quote)
        else:
            return web.json_response({"error": "No data available"}, status=404)

    async def get_all_quotes(self, request):
        """Get all cached quotes"""
        return web.json_response(self.quote_cache)

    async def export_csv(self, request):
        """Export data as CSV for AmiBroker"""
        symbol = request.match_info['symbol']
        exchange = request.query.get('exchange', 'NSE')
        symbol_key = f"{exchange}:{symbol}"

        if symbol_key not in self.quote_cache:
            return web.json_response({"error": "No data available"}, status=404)

        quote = self.quote_cache[symbol_key]
        data = quote["data"]

        # AmiBroker CSV format
        csv_data = f"Ticker,Date,Open,High,Low,Close,Volume,OI\n"
        csv_data += f"{symbol},{datetime.now().strftime('%Y%m%d')},"
        csv_data += f"{data.get('open', 0)},{data.get('high', 0)},{data.get('low', 0)},"
        csv_data += f"{data.get('close', data.get('ltp', 0))},{data.get('volume', 0)},{data.get('oi', 0)}\n"

        return web.Response(
            text=csv_data,
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{symbol}.csv"'}
        )

    async def get_status(self, request):
        """Get bridge status"""
        return web.json_response({
            "websocket_connected": self.connected,
            "authenticated": self.authenticated,
            "dde_running": self.dde_server.running,
            "subscribed_symbols": list(self.subscribed_symbols),
            "quote_cache_size": len(self.quote_cache),
            "timestamp": datetime.now().isoformat()
        })

    async def subscribe_symbol(self, request):
        """Subscribe to symbol via HTTP"""
        data = await request.json()
        symbol = data.get('symbol')
        exchange = data.get('exchange', 'NSE')
        mode = data.get('mode', 1)

        if not symbol:
            return web.json_response({"error": "Symbol required"}, status=400)

        success = await self.subscribe_symbol(symbol, exchange, mode)
        if success:
            return web.json_response({"status": "subscribed", "symbol": symbol})
        else:
            return web.json_response({"error": "Subscription failed"}, status=500)

    async def update_dde_data(self, request):
        """Update DDE data manually"""
        data = await request.json()
        symbol = data.get('symbol')
        field = data.get('field')
        value = data.get('value')

        if not all([symbol, field, value]):
            return web.json_response({"error": "Symbol, field, and value required"}, status=400)

        self.dde_server.update_data(symbol, field, value)
        return web.json_response({"status": "updated"})

    async def start_http_server(self):
        """Start HTTP server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', self.http_port)
        await site.start()
        logger.info(f"✅ HTTP server started on http://127.0.0.1:{self.http_port}")

    async def start_dde_server(self):
        """Start DDE server"""
        success = self.dde_server.start()
        if success:
            logger.info("✅ DDE server started successfully")
            logger.info("📋 AmiBroker can connect via DDE:")
            logger.info(f"   Topic: {self.topic}")
            logger.info("   Item format: SYMBOL.FIELD")
            logger.info("   Example: RELIANCE.LTP")
        return success

    async def run(self, symbols: list = None):
        """Main run loop"""

        # Start HTTP server
        await self.start_http_server()

        # Start DDE server
        dde_success = await self.start_dde_server()

        # Connect to WebSocket
        ws_success = await self.connect_websocket()

        if ws_success and self.authenticated:
            # Subscribe to symbols
            if symbols:
                for symbol_info in symbols:
                    symbol = symbol_info.get("symbol")
                    exchange = symbol_info.get("exchange", "NSE")
                    mode = symbol_info.get("mode", 1)

                    if symbol:
                        await self.subscribe_symbol(symbol, exchange, mode)

            # Start WebSocket listener
            await self.websocket_listener()

        else:
            logger.error("❌ Failed to connect to WebSocket server")

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down...")

        # Cleanup
        if self.websocket:
            await self.websocket.close()
        self.dde_server.stop()

async def main():
    """Main function"""

    # Get API key
    api_key_file = Path.home() / ".fortress" / "openalgo_api_key.txt"
    if not api_key_file.exists():
        logger.error("❌ API key not found. Please run update_api_key.bat first.")
        return

    with open(api_key_file, 'r') as f:
        api_key = f.read().strip()

    # Create bridge
    bridge = OpenAlgoAmiBridge(api_key)

    # Define symbols to subscribe to
    symbols = [
        {"symbol": "RELIANCE", "exchange": "NSE", "mode": 1},
        {"symbol": "INFY", "exchange": "NSE", "mode": 1},
        {"symbol": "TCS", "exchange": "NSE", "mode": 1},
        {"symbol": "HDFC", "exchange": "NSE", "mode": 1},
    ]

    try:
        logger.info("🏰 OpenAlgo AmiBroker Bridge")
        logger.info("=" * 40)
        logger.info("📊 Multiple integration methods available:")
        logger.info("   1. DDE (Dynamic Data Exchange) - Real-time")
        logger.info("   2. HTTP API - REST endpoints")
        logger.info("   3. CSV Export - File-based import")
        logger.info("")
        logger.info("🚀 Starting bridge...")
        logger.info("")

        await bridge.run(symbols)

    except KeyboardInterrupt:
        logger.info("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
