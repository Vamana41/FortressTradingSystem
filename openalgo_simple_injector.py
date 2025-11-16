#!/usr/bin/env python3
"""
OpenAlgo Simple Symbol Injector - Uses REST API to get symbols and lets OpenAlgo handle WebSocket
This approach subscribes to symbols via WebSocket, then OpenAlgo automatically sends data to AmiBroker
"""

import asyncio
import websockets
import json
import logging
import requests
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OpenAlgoSimpleInjector")

# Configuration
OPENALGO_API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
OPENALGO_BASE_URL = "http://127.0.0.1:5000/api/v1"
WEBSOCKET_URL = "ws://127.0.0.1:8765"

# All symbols from your original system
ALL_SYMBOLS = [
    # NSE Cash
    {"symbol": "SBIN", "exchange": "NSE"},
    {"symbol": "RELIANCE", "exchange": "NSE"},
    {"symbol": "TCS", "exchange": "NSE"},
    {"symbol": "INFY", "exchange": "NSE"},
    {"symbol": "ITC", "exchange": "NSE"},

    # Nifty and BankNifty for ATM options
    {"symbol": "NIFTY", "exchange": "NSE"},
    {"symbol": "BANKNIFTY", "exchange": "NSE"},

    # MCX Commodities
    {"symbol": "CRUDEOIL", "exchange": "MCX"},
    {"symbol": "GOLD", "exchange": "MCX"},
    {"symbol": "SILVER", "exchange": "MCX"},
    {"symbol": "COPPER", "exchange": "MCX"},
    {"symbol": "NATURALGAS", "exchange": "MCX"}
]

class OpenAlgoSimpleInjector:
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.authenticated = False

    async def connect_and_subscribe(self):
        """Connect to OpenAlgo and subscribe to symbols"""
        try:
            logger.info(f"Connecting to OpenAlgo WebSocket at {WEBSOCKET_URL}")
            self.websocket = await websockets.connect(WEBSOCKET_URL)
            self.connected = True
            logger.info("✅ Connected to OpenAlgo WebSocket")

            # Send authentication
            auth_msg = {
                "action": "authenticate",
                "api_key": OPENALGO_API_KEY
            }
            await self.websocket.send(json.dumps(auth_msg))
            logger.info("Sent authentication")

            # Send subscription for all symbols
            subscribe_msg = {
                "action": "subscribe",
                "symbols": ALL_SYMBOLS,
                "mode": "Quote"
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"📊 Subscribed to {len(ALL_SYMBOLS)} symbols")

            # Log the symbols that should now be available
            logger.info("=" * 60)
            logger.info("🎯 SYMBOLS NOW SUBSCRIBED TO OPENALGO:")
            logger.info("=" * 60)
            for symbol_info in ALL_SYMBOLS:
                ami_format = f"{symbol_info['symbol']}-{symbol_info['exchange']}"
                logger.info(f"  ✓ {ami_format}")
            logger.info("=" * 60)
            logger.info("💡 These symbols should now appear in AmiBroker automatically")
            logger.info("💡 OpenAlgo will forward the market data to AmiBroker via its plugin")

            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    async def listen_for_data(self):
        """Listen for incoming market data from OpenAlgo"""
        try:
            while self.connected:
                try:
                    # Wait for data from OpenAlgo (with timeout)
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    data = json.loads(message)

                    # Log incoming data
                    if "data" in data and isinstance(data["data"], dict):
                        symbol = data["data"].get("symbol", "Unknown")
                        ltp = data["data"].get("ltp", 0)
                        exchange = data["data"].get("exchange", "Unknown")
                        ami_format = f"{symbol}-{exchange}"
                        logger.info(f"📈 Received: {ami_format} LTP: {ltp}")
                    else:
                        logger.debug(f"Received message: {data}")

                except asyncio.TimeoutError:
                    # No data received, but connection is still alive
                    logger.debug("No data received in 30 seconds, connection still active")
                    continue
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON received: {e}")
                    continue

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in listen loop: {e}")
            self.connected = False

    async def run(self):
        """Main run method"""
        logger.info("=" * 70)
        logger.info("🚀 OPENALGO SIMPLE SYMBOL INJECTOR")
        logger.info("=" * 70)
        logger.info("This injector subscribes to symbols via OpenAlgo WebSocket")
        logger.info("OpenAlgo will automatically forward data to AmiBroker")
        logger.info("=" * 70)

        # Connect and subscribe
        if await self.connect_and_subscribe():
            logger.info("✅ Successfully subscribed to all symbols!")
            logger.info("🔄 Now listening for market data...")

            # Keep listening for data
            await self.listen_for_data()
        else:
            logger.error("❌ Failed to connect and subscribe")

        # Cleanup
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 WebSocket connection closed")

async def main():
    """Main function"""
    injector = OpenAlgoSimpleInjector()
    try:
        await injector.run()
    except KeyboardInterrupt:
        logger.info("🛑 Injector stopped by user")

if __name__ == "__main__":
    asyncio.run(main())
