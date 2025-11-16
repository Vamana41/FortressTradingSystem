#!/usr/bin/env python3
"""
OpenAlgo Working Relay Injector - Uses your existing relay server architecture
with only the symbols that actually work with OpenAlgo
"""

import asyncio
import websockets
import json
import logging
import datetime
import time
import requests
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv("openalgo_symbol_injector.env")

# Configuration
OPENALGO_API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
OPENALGO_BASE_URL = "http://127.0.0.1:5000/api/v1"
RELAY_SERVER_URI = "ws://127.0.0.1:8765"
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"

# Working symbols that actually work with OpenAlgo
# Format: OpenAlgo format -> AmiBroker format (symbol-exchange)
WORKING_SYMBOL_MAPPING = {
    "NSE:SBIN": "SBIN-NSE",
    "NSE:RELIANCE": "RELIANCE-NSE",
    "NSE:TCS": "TCS-NSE",
    "NSE:INFY": "INFY-NSE",
    "NSE:ITC": "ITC-NSE",
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_working_relay_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoWorkingRelayInjector")

class OpenAlgoWorkingRelayInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.relay_uri = RELAY_SERVER_URI
        self.symbol_mapping = WORKING_SYMBOL_MAPPING.copy()
        self.websocket = None
        self.running = False

    def test_connection(self) -> bool:
        """Test connection to OpenAlgo using correct POST endpoint"""
        try:
            url = f"{self.base_url}/quotes"
            payload = {
                'apikey': self.api_key,
                'exchange': 'NSE',
                'symbol': 'SBIN'
            }
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    ltp = data["data"]["ltp"]
                    logger.info(f"SUCCESS: Quotes API working! SBIN LTP: {ltp}")
                    return True
                else:
                    logger.warning(f"Quotes response: {data}")
            elif response.status_code == 403:
                logger.error(f"API key invalid - need to refresh")
                return False
            else:
                logger.warning(f"Quotes HTTP {response.status_code}: {response.text}")

            return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_quote(self, exchange: str, symbol: str) -> Optional[float]:
        """Get current quote using correct POST endpoint"""
        try:
            url = f"{self.base_url}/quotes"
            payload = {
                'apikey': self.api_key,
                'exchange': exchange,
                'symbol': symbol
            }
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    ltp = float(data["data"]["ltp"])
                    return ltp
                else:
                    logger.error(f"API error for {exchange}:{symbol}: {data.get('message', 'Unknown error')}")
            elif response.status_code == 403:
                logger.error(f"API key invalid - need to refresh")
                return None
            else:
                logger.error(f"HTTP {response.status_code} error for {exchange}:{symbol}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting quote for {exchange}:{symbol}: {e}")
            return None

    def get_all_symbols(self) -> List[Dict[str, str]]:
        """Get all working symbols for automatic injection"""
        all_symbols = []

        for openalgo_symbol, amibroker_symbol in self.symbol_mapping.items():
            exchange = openalgo_symbol.split(":")[0]
            symbol = openalgo_symbol.split(":")[1]
            all_symbols.append({
                "openalgo_symbol": openalgo_symbol,
                "amibroker_symbol": amibroker_symbol,
                "exchange": exchange,
                "symbol": symbol
            })

        logger.info(f"Total working symbols for automatic injection: {len(all_symbols)}")
        return all_symbols

    async def send_rtd_to_relay(self, ami_symbol: str, ltp: float, timestamp: datetime.datetime):
        """Send real-time data to relay server in correct format"""
        try:
            # Format: {"n": "SBIN", "d": 20251116, "t": 134500, "o": 967.85, "h": 969.05, "l": 952.0, "c": 967.85, "v": 11032927}
            d = int(timestamp.strftime("%Y%m%d"))
            t = int(timestamp.strftime("%H%M00"))

            # Create RTD bar - using LTP for all OHLC values since we only have LTP
            rtd_bar = [{"n": ami_symbol, "d": d, "t": t, "o": ltp, "h": ltp, "l": ltp, "c": ltp, "v": 0}]

            if self.websocket:
                await self.websocket.send(json.dumps(rtd_bar, separators=(',', ':')))
                logger.info(f"--> SENT TO RELAY: {ami_symbol} LTP: {ltp}")
            else:
                logger.warning(f"Relay connection not available, cannot send RTD for {ami_symbol}")

        except Exception as e:
            logger.error(f"Error sending RTD to relay for {ami_symbol}: {e}")

    async def connect_to_relay(self):
        """Connect to relay server"""
        try:
            logger.info(f"Connecting to relay server at {self.relay_uri}...")
            self.websocket = await websockets.connect(self.relay_uri)
            logger.info(">>> CONNECTED TO RELAY SERVER <<<")

            # Send role message
            await self.websocket.send("rolesend")
            logger.info("Sent 'rolesend' to relay")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to relay server: {e}")
            return False

    async def start_automatic_injection(self):
        """Start automatic symbols injection with real-time data to relay"""
        all_symbols = self.get_all_symbols()

        logger.info("=" * 80)
        logger.info("AUTOMATIC SYMBOLS INJECTION TO RELAY ACTIVE!")
        logger.info("=" * 80)
        logger.info("All working symbols are being injected automatically into AmiBroker via relay:")

        # Display all symbols
        for symbol_info in all_symbols:
            logger.info(f"  {symbol_info['openalgo_symbol']} -> {symbol_info['amibroker_symbol']}")

        logger.info("=" * 80)
        logger.info("Real-time data streaming to relay starting...")
        logger.info("=" * 80)

        # Connect to relay first
        if not await self.connect_to_relay():
            logger.error("Failed to connect to relay server - cannot proceed")
            return

        # Stream data continuously
        cycle_count = 0
        self.running = True

        while self.running:
            try:
                cycle_count += 1
                logger.info(f"--- Data Cycle #{cycle_count} ---")

                for symbol_info in all_symbols:
                    exchange = symbol_info["exchange"]
                    symbol = symbol_info["symbol"]
                    amibroker_symbol = symbol_info["amibroker_symbol"]

                    # Get real-time data using correct POST endpoint
                    ltp = self.get_quote(exchange, symbol)

                    if ltp is not None:
                        timestamp = datetime.datetime.now()

                        # Send to relay server
                        await self.send_rtd_to_relay(amibroker_symbol, ltp, timestamp)

                        # Log the data injection
                        logger.info(f"AUTO-INJECT: {amibroker_symbol} LTP: {ltp} Time: {timestamp.isoformat()}")
                    else:
                        logger.warning(f"No data for {exchange}:{symbol}")

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

                logger.info(f"--- End Cycle #{cycle_count} ---")

                # Wait before next cycle
                await asyncio.sleep(3)  # Update every 3 seconds

            except KeyboardInterrupt:
                logger.info("Stopping automatic symbols injection")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in automatic injection: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def run(self):
        """Main run method - AUTOMATIC SYMBOLS INJECTION"""
        try:
            logger.info("=" * 80)
            logger.info("OPENALGO WORKING RELAY INJECTOR STARTING...")
            logger.info("=" * 80)
            logger.info(f"Managing {len(self.symbol_mapping)} working symbols")

            # Test connection first
            if not self.test_connection():
                logger.error("Failed to connect to OpenAlgo - check API key and OpenAlgo status")
                return

            # Start automatic real-time data streaming to relay
            await self.start_automatic_injection()

        except Exception as e:
            logger.error(f"Error in automatic injection: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()
                logger.info("Closed relay connection")

async def main():
    """Main async entry point"""
    injector = OpenAlgoWorkingRelayInjector()
    await injector.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Injector stopped by user")
