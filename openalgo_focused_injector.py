#!/usr/bin/env python3
"""
OpenAlgo Focused Symbol Injector - Your Original Symbols Only
Uses OpenAlgo's native APIs to inject only your original symbols
"""

import asyncio
import websockets
import json
import logging
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load configuration
load_dotenv('openalgo_symbol_injector.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OpenAlgoFocusedInjector')

class OpenAlgoFocusedInjector:
    def __init__(self):
        self.ws_url = os.getenv('OPENALGO_WS_URL', 'ws://127.0.0.1:8765')
        self.api_key = '703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b'
        self.base_url = 'http://127.0.0.1:5000/api/v1'
        self.websocket = None
        self.authenticated = False

        # Your original symbols only
        self.target_symbols = [
            "SBIN", "RELIANCE", "TCS", "INFY", "ITC",
            "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "NICKEL"
        ]

        # Found symbols to inject
        self.working_symbols = []

    async def search_symbol(self, query, exchange=None):
        """Search for exact symbol using OpenAlgo Search API"""
        try:
            search_data = {
                "apikey": self.api_key,
                "query": query
            }

            if exchange:
                search_data["exchange"] = exchange

            logger.info(f"Searching for: {query} (exchange: {exchange})")
            response = requests.post(
                f"{self.base_url}/search",
                json=search_data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    symbols = result.get("data", [])
                    # Look for exact match
                    for symbol_info in symbols:
                        if symbol_info["symbol"].upper() == query.upper():
                            logger.info(f"Found exact match: {symbol_info['symbol']} on {symbol_info['exchange']}")
                            return symbol_info

                    # If no exact match, return first result
                    if symbols:
                        logger.info(f"Using first result: {symbols[0]['symbol']} on {symbols[0]['exchange']}")
                        return symbols[0]

                else:
                    logger.warning(f"Search failed for {query}: {result.get('message')}")
            else:
                logger.error(f"Search API error {response.status_code}: {response.text}")

        except Exception as e:
            logger.error(f"Search error for {query}: {e}")

        return None

    async def find_symbols(self):
        """Find your original symbols using OpenAlgo Search API"""
        logger.info("Finding your original symbols using OpenAlgo Search API...")

        # Search for each symbol in appropriate exchanges
        exchange_mapping = {
            "SBIN": ["NSE", "BSE"],
            "RELIANCE": ["NSE", "BSE"],
            "TCS": ["NSE", "BSE"],
            "INFY": ["NSE", "BSE"],
            "ITC": ["NSE", "BSE"],
            "CRUDEOIL": ["MCX"],
            "NATURALGAS": ["MCX"],
            "GOLD": ["MCX"],
            "SILVER": ["MCX"],
            "COPPER": ["MCX"],
            "NICKEL": ["MCX"]
        }

        for symbol in self.target_symbols:
            found = False

            # Try specific exchanges first
            exchanges_to_try = exchange_mapping.get(symbol, ["NSE", "BSE", "MCX"])

            for exchange in exchanges_to_try:
                symbol_info = await self.search_symbol(symbol, exchange)
                if symbol_info:
                    self.working_symbols.append({
                        "symbol": symbol_info["symbol"],
                        "exchange": symbol_info["exchange"],
                        "name": symbol_info.get("name", ""),
                        "instrumenttype": symbol_info.get("instrumenttype", "")
                    })
                    found = True
                    break

            if not found:
                logger.warning(f"❌ Could not find symbol: {symbol}")
            else:
                logger.info(f"✅ Found symbol: {symbol}")

        logger.info(f"Found {len(self.working_symbols)} symbols out of {len(self.target_symbols)}")

        # Show found symbols
        logger.info("Symbols to inject:")
        for symbol_info in self.working_symbols:
            logger.info(f"  - {symbol_info['exchange']}:{symbol_info['symbol']} ({symbol_info.get('name', '')})")

    async def connect(self):
        """Connect to OpenAlgo WebSocket"""
        try:
            logger.info(f"Connecting to OpenAlgo WebSocket at {self.ws_url}...")
            self.websocket = await websockets.connect(self.ws_url)
            logger.info("✅ Connected to OpenAlgo WebSocket!")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            return False

    async def authenticate(self):
        """Authenticate with OpenAlgo using API key"""
        try:
            auth_message = {
                "action": "auth",
                "api_key": self.api_key
            }

            logger.info("Authenticating with OpenAlgo...")
            await self.websocket.send(json.dumps(auth_message))

            response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            auth_data = json.loads(response)

            if auth_data.get("status") == "success":
                logger.info(f"✅ Authentication successful! User: {auth_data.get('user_id')}, Broker: {auth_data.get('broker')}")
                self.authenticated = True
                return True
            else:
                logger.error(f"❌ Authentication failed: {auth_data}")
                return False

        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False

    async def subscribe_symbol(self, symbol_info):
        """Subscribe to a single symbol"""
        try:
            subscribe_message = {
                "action": "subscribe",
                "exchange": symbol_info["exchange"],
                "symbol": symbol_info["symbol"]
            }

            logger.info(f"Subscribing to {symbol_info['exchange']}:{symbol_info['symbol']}")
            await self.websocket.send(json.dumps(subscribe_message))

            # Wait for confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            response_data = json.loads(response)

            status = response_data.get("status", "unknown")

            if status == "success":
                logger.info(f"✅ Successfully subscribed to {symbol_info['exchange']}:{symbol_info['symbol']}")
                return True
            else:
                logger.warning(f"⚠️  Subscription failed for {symbol_info['exchange']}:{symbol_info['symbol']}: {response_data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"❌ Subscription error for {symbol_info['exchange']}:{symbol_info['symbol']}: {e}")
            return False

    async def inject_symbols(self):
        """Inject all found symbols"""
        logger.info("="*60)
        logger.info("OPENALGO FOCUSED SYMBOL INJECTOR STARTING...")
        logger.info("Injecting your original symbols only")
        logger.info("="*60)

        # Subscribe to all symbols
        success_count = 0
        for symbol_info in self.working_symbols:
            if await self.subscribe_symbol(symbol_info):
                success_count += 1

        logger.info(f"✅ Successfully subscribed to {success_count}/{len(self.working_symbols)} symbols")

        if success_count > 0:
            logger.info("🎉 SYMBOLS INJECTED SUCCESSFULLY!")
            logger.info("✅ Check AmiBroker - your symbols should now be available!")
            logger.info("✅ OpenAlgo is now feeding real-time data to AmiBroker!")

            # Keep the connection alive and listen for data
            await self.listen_for_data()
        else:
            logger.error("❌ Failed to inject any symbols")

    async def listen_for_data(self):
        """Listen for real-time data from OpenAlgo"""
        logger.info("Listening for real-time data...")
        logger.info("📊 Data should now appear in AmiBroker!")

        try:
            while True:
                message = await self.websocket.recv()
                data = json.loads(message)

                # Log incoming data (reduced verbosity)
                if "ltp" in str(data).lower():
                    logger.info(f"📊 Data: {data.get('exchange', '')}:{data.get('symbol', '')} LTP: {data.get('ltp', 'N/A')}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error listening for data: {e}")

    async def run(self):
        """Main run loop"""
        try:
            # Find all symbols first
            await self.find_symbols()

            if not self.working_symbols:
                logger.error("No symbols found to inject!")
                return

            # Connect to WebSocket
            if not await self.connect():
                return

            # Authenticate
            if not await self.authenticate():
                return

            # Inject all symbols
            await self.inject_symbols()

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Runtime error: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()
                logger.info("WebSocket connection closed")

async def main():
    """Main function"""
    injector = OpenAlgoFocusedInjector()
    await injector.run()

if __name__ == "__main__":
    asyncio.run(main())
