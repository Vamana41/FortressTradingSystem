#!/usr/bin/env python3
"""
OpenAlgo RTD Server for AmiBroker
A proper Python-based RTD server that provides real-time data to AmiBroker
without requiring MFC or C++ compilation.
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
from typing import Dict, Optional, Any

import aiohttp
import websockets
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OpenAlgoRTD')

class OpenAlgoRTDServer:
    """
    Real-Time Data server that provides data to AmiBroker via:
    1. WebSocket for real-time streaming
    2. HTTP REST API for historical data
    3. CSV export for AmiBroker import
    """
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:5000", ws_url: str = "ws://localhost:8765"):
        self.api_key = api_key
        self.base_url = base_url
        self.ws_url = ws_url
        self.websocket = None
        self.subscribed_symbols = set()
        self.quote_cache = {}
        self.running = False
        self.app = web.Application()
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup HTTP routes for AmiBroker integration"""
        self.app.router.add_get('/rtd/quote/{symbol}', self.get_quote)
        self.app.router.add_get('/rtd/history/{symbol}', self.get_history)
        self.app.router.add_get('/rtd/export/{symbol}', self.export_csv)
        self.app.router.add_get('/rtd/status', self.get_status)
        self.app.router.add_post('/rtd/subscribe', self.subscribe_symbol)
        self.app.router.add_post('/rtd/unsubscribe', self.unsubscribe_symbol)
        
    async def start(self, host: str = '127.0.0.1', port: int = 8080):
        """Start the RTD server"""
        self.running = True
        logger.info(f"Starting OpenAlgo RTD Server on {host}:{port}")
        
        # Start WebSocket connection in background
        asyncio.create_task(self._websocket_loop())
        
        # Start HTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"✅ RTD Server running on http://{host}:{port}")
        logger.info(f"📊 Endpoints available:")
        logger.info(f"   - Quote: http://{host}:{port}/rtd/quote/SYMBOL-EXCHANGE")
        logger.info(f"   - History: http://{host}:{port}/rtd/history/SYMBOL-EXCHANGE")
        logger.info(f"   - CSV Export: http://{host}:{port}/rtd/export/SYMBOL-EXCHANGE")
        logger.info(f"   - Status: http://{host}:{port}/rtd/status")
        
        # Keep running
        while self.running:
            await asyncio.sleep(1)
            
    async def stop(self):
        """Stop the RTD server"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
        logger.info("RTD Server stopped")
        
    async def _websocket_loop(self):
        """Maintain WebSocket connection to OpenAlgo"""
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.websocket = websocket
                    logger.info(f"🔗 Connected to OpenAlgo WebSocket at {self.ws_url}")
                    
                    # Authenticate
                    auth_msg = {
                        "action": "authenticate",
                        "api_key": self.api_key
                    }
                    await websocket.send(json.dumps(auth_msg))
                    
                    # Subscribe to symbols
                    for symbol in self.subscribed_symbols:
                        await self._subscribe_symbol_ws(symbol)
                    
                    # Listen for messages
                    async for message in websocket:
                        await self._handle_websocket_message(message)
                        
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
                self.websocket = None
                await asyncio.sleep(5)  # Retry after 5 seconds
                
    async def _handle_websocket_message(self, message: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            if data.get("type") == "quote":
                symbol = data.get("symbol")
                if symbol:
                    self.quote_cache[symbol] = {
                        "ltp": float(data.get("ltp", 0)),
                        "open": float(data.get("open", 0)),
                        "high": float(data.get("high", 0)),
                        "low": float(data.get("low", 0)),
                        "close": float(data.get("close", 0)),
                        "volume": int(data.get("volume", 0)),
                        "oi": int(data.get("oi", 0)),
                        "timestamp": datetime.now().isoformat()
                    }
                    logger.debug(f"📈 Updated quote for {symbol}: {self.quote_cache[symbol]['ltp']}")
                    
        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON message: {message}")
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
            
    async def _subscribe_symbol_ws(self, symbol: str):
        """Subscribe to a symbol via WebSocket"""
        if self.websocket:
            try:
                subscribe_msg = {
                    "action": "subscribe",
                    "symbol": symbol
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info(f"🔔 Subscribed to {symbol}")
            except Exception as e:
                logger.error(f"❌ Failed to subscribe to {symbol}: {e}")
                
    async def get_quote(self, request):
        """Get real-time quote for a symbol"""
        symbol = request.match_info['symbol']
        
        # Parse symbol and exchange
        if '-' in symbol:
            symbol_name, exchange = symbol.rsplit('-', 1)
        else:
            symbol_name = symbol
            exchange = 'NSE'
            
        # Check cache first
        if symbol in self.quote_cache:
            quote = self.quote_cache[symbol]
            return web.json_response({
                "symbol": symbol,
                "ltp": quote["ltp"],
                "open": quote["open"],
                "high": quote["high"],
                "low": quote["low"],
                "close": quote["close"],
                "volume": quote["volume"],
                "oi": quote["oi"],
                "timestamp": quote["timestamp"],
                "source": "cache"
            })
        
        # Fetch from OpenAlgo API
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/v1/quotes"
                payload = {
                    "apikey": self.api_key,
                    "symbol": symbol_name,
                    "exchange": exchange
                }
                
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=2)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return web.json_response({
                            "symbol": symbol,
                            "ltp": float(data.get("ltp", 0)),
                            "open": float(data.get("open", 0)),
                            "high": float(data.get("high", 0)),
                            "low": float(data.get("low", 0)),
                            "close": float(data.get("close", 0)),
                            "volume": int(data.get("volume", 0)),
                            "oi": int(data.get("oi", 0)),
                            "timestamp": datetime.now().isoformat(),
                            "source": "api"
                        })
                    else:
                        return web.json_response({"error": f"API error: {response.status}"}, status=500)
        except asyncio.TimeoutError:
            return web.json_response({"error": "Request timeout"}, status=408)
        except Exception as e:
            logger.error(f"❌ Error fetching quote: {e}")
            return web.json_response({"error": str(e)}, status=500)
            
    async def get_history(self, request):
        """Get historical data for a symbol"""
        symbol = request.match_info['symbol']
        
        # Parse parameters
        interval = request.query.get('interval', '1m')
        period = request.query.get('period', '1d')
        
        # Parse symbol and exchange
        if '-' in symbol:
            symbol_name, exchange = symbol.rsplit('-', 1)
        else:
            symbol_name = symbol
            exchange = 'NSE'
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/v1/history"
                payload = {
                    "apikey": self.api_key,
                    "symbol": symbol_name,
                    "exchange": exchange,
                    "interval": interval,
                    "period": period
                }
                
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return web.json_response(data)
                    else:
                        return web.json_response({"error": f"API error: {response.status}"}, status=500)
        except asyncio.TimeoutError:
            return web.json_response({"error": "Request timeout"}, status=408)
        except Exception as e:
            logger.error(f"❌ Error fetching history: {e}")
            return web.json_response({"error": str(e)}, status=500)
            
    async def export_csv(self, request):
        """Export data as CSV for AmiBroker import"""
        symbol = request.match_info['symbol']
        
        # Get quote data
        quote_response = await self.get_quote(request)
        if quote_response.status != 200:
            return quote_response
            
        quote_data = json.loads(quote_response.text)
        
        # Format for AmiBroker CSV import
        csv_data = f"Ticker,Date,Open,High,Low,Close,Volume,OI\n"
        csv_data += f"{symbol},{datetime.now().strftime('%Y%m%d')},"
        csv_data += f"{quote_data['open']},{quote_data['high']},{quote_data['low']},"
        csv_data += f"{quote_data['ltp']},{quote_data['volume']},{quote_data['oi']}\n"
        
        return web.Response(
            text=csv_data,
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{symbol}_{datetime.now().strftime("%Y%m%d")}.csv"'}
        )
        
    async def get_status(self, request):
        """Get server status"""
        return web.json_response({
            "status": "running",
            "websocket_connected": self.websocket is not None,
            "subscribed_symbols": list(self.subscribed_symbols),
            "quote_cache_size": len(self.quote_cache),
            "timestamp": datetime.now().isoformat()
        })
        
    async def subscribe_symbol(self, request):
        """Subscribe to a symbol"""
        data = await request.json()
        symbol = data.get('symbol')
        
        if symbol:
            self.subscribed_symbols.add(symbol)
            if self.websocket:
                await self._subscribe_symbol_ws(symbol)
            return web.json_response({"status": "subscribed", "symbol": symbol})
        else:
            return web.json_response({"error": "Symbol required"}, status=400)
            
    async def unsubscribe_symbol(self, request):
        """Unsubscribe from a symbol"""
        data = await request.json()
        symbol = data.get('symbol')
        
        if symbol:
            self.subscribed_symbols.discard(symbol)
            return web.json_response({"status": "unsubscribed", "symbol": symbol})
        else:
            return web.json_response({"error": "Symbol required"}, status=400)

async def main():
    """Main function to start the RTD server"""
    
    # Get API key from file or environment
    api_key_file = Path.home() / ".fortress" / "openalgo_api_key.txt"
    if api_key_file.exists():
        with open(api_key_file, 'r') as f:
            api_key = f.read().strip()
    else:
        logger.error("❌ API key not found. Please run update_api_key.bat first.")
        return
        
    # Create and start server
    server = OpenAlgoRTDServer(api_key)
    
    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info("🛑 Shutting down RTD server...")
        asyncio.create_task(server.stop())
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("🛑 RTD server stopped by user")
    except Exception as e:
        logger.error(f"❌ RTD server error: {e}")

if __name__ == "__main__":
    print("🏰 OpenAlgo RTD Server for AmiBroker")
    print("=" * 40)
    print("📊 This server provides real-time data to AmiBroker via:")
    print("   - HTTP API for quotes and historical data")
    print("   - CSV export for AmiBroker import")
    print("   - WebSocket for real-time streaming")
    print()
    print("🎯 AmiBroker Integration:")
    print("   1. Use AmiBroker's ASCII import feature")
    print("   2. Point to: http://127.0.0.1:8080/rtd/export/SYMBOL-EXCHANGE")
    print("   3. Example: http://127.0.0.1:8080/rtd/export/RELIANCE-NSE")
    print()
    print("🚀 Starting server...")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")