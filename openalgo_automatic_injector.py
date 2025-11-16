#!/usr/bin/env python3
"""
OpenAlgo Automatic Symbol Injector - Using OpenAlgo's Native WebSocket

This script connects to OpenAlgo's WebSocket at ws://127.0.0.1:8765
and automatically injects all symbols including ATM options for AmiBroker.
"""

import asyncio
import websockets
import json
import logging
import datetime
import os
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple
import pytz
import math
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv("openalgo_symbol_injector.env")

# Configuration
OPENALGO_API_KEY = os.getenv("OPENALGO_API_KEY", "")
OPENALGO_BASE_URL = "http://127.0.0.1:5000"
OPENALGO_WS_URL = "ws://127.0.0.1:8765"
MASTER_CONTRACT_PATH = r"C:\AmiPyScripts\fyers_contracts"
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"

# Complete Symbol Mapping from your original system
COMPLETE_SYMBOL_MAPPING = {
    "MCX:CRUDEOILM25APRFUT": "CRUDEOILM-FUT",
    "MCX:GOLDPETAL25FEBFUT": "GOLDPETAL-FUT",
    "MCX:GOLDM25FEBFUT": "GOLDM-FUT",
    "MCX:NATGASMINI25APRFUT": "NATGASMINI-FUT",
    "MCX:SILVERMIC25APRFUT": "SILVERMIC-FUT",
    "MCX:ZINCMINI25APRFUT": "ZINCMINI-FUT",
    "MCX:ALUMINI25APRFUT": "ALUMINI-FUT",
    "MCX:COPPER25APRFUT": "COPPER-FUT",
    "MCX:LEADMINI25APRFUT": "LEADMINI-FUT",
    "NSE:BANKNIFTY25APRFUT": "BANKNIFTY-FUT",
    "NSE:NIFTY25APRFUT": "NIFTY-FUT",
    "NSE:SBIN-EQ": "SBIN",
}

# ATM Selection Settings
BANKNIFTY_INDEX_SYMBOL = "NSE:NIFTYBANK-INDEX"
NIFTY_INDEX_SYMBOL = "NSE:NIFTY50-INDEX"
BANKNIFTY_STRIKE_INTERVAL = 100
NIFTY_STRIKE_INTERVAL = 50
ATM_SELECTION_TIME_STR = "09:13:15"
OPTION_CHAIN_STRIKE_COUNT = 2

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_automatic_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoAutomaticInjector")

class OpenAlgoAutomaticInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.ws_url = OPENALGO_WS_URL
        self.websocket = None
        self.symbol_mapping = COMPLETE_SYMBOL_MAPPING.copy()
        self.atm_symbols = []
        self.subscribed_symbols = set()

    def get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def get_index_ltp(self, symbol: str) -> Optional[float]:
        """Get current LTP for an index"""
        try:
            url = f"{self.base_url}/api/v1/quotes"
            params = {"symbol": symbol}
            response = requests.get(url, headers=self.get_headers(), params=params)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return float(data["data"]["ltp"])
                else:
                    logger.error(f"API error for {symbol}: {data.get('message', 'Unknown error')}")
            elif response.status_code == 403:
                logger.error(f"API key invalid for {symbol} - need to refresh")
                return None
            else:
                logger.error(f"HTTP {response.status_code} error for {symbol}")
                return None

        except Exception as e:
            logger.error(f"Error getting LTP for {symbol}: {e}")
            return None

    async def get_expiry_dates(self, symbol: str) -> List[str]:
        """Get expiry dates for a symbol"""
        try:
            url = f"{self.base_url}/api/v1/expiry"
            params = {
                "symbol": symbol.replace("-INDEX", ""),
                "exchange": "NFO",
                "instrument_type": "options"
            }
            response = requests.get(url, headers=self.get_headers(), params=params)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data["data"]
                else:
                    logger.error(f"API error getting expiry: {data.get('message', 'Unknown error')}")
            else:
                logger.error(f"HTTP {response.status_code} error getting expiry")
                return []

        except Exception as e:
            logger.error(f"Error getting expiry dates: {e}")
            return []

    def select_atm_strikes(self, index_price: float, strike_interval: int) -> List[int]:
        """Select ATM strikes based on index price"""
        atm_strike = round(index_price / strike_interval) * strike_interval
        strikes = []
        for i in range(-OPTION_CHAIN_STRIKE_COUNT, OPTION_CHAIN_STRIKE_COUNT + 1):
            strikes.append(atm_strike + (i * strike_interval))
        return strikes

    def format_option_symbol(self, underlying: str, expiry: str, strike: int, option_type: str) -> str:
        """Format option symbol in AmiBroker format"""
        # Convert expiry from YYYY-MM-DD to DDMMMYY format
        expiry_date = datetime.datetime.strptime(expiry, "%Y-%m-%d")
        expiry_str = expiry_date.strftime("%d%b%y").upper()

        # Format: NIFTY17JAN2519500CE
        return f"{underlying}{expiry_str}{strike}{option_type}"

    async def select_and_subscribe_atm_options(self) -> List[str]:
        """Select ATM options for Nifty and BankNifty"""
        atm_symbols = []

        try:
            # Get Nifty ATM options
            nifty_ltp = await self.get_index_ltp(NIFTY_INDEX_SYMBOL)
            if nifty_ltp:
                nifty_expiry_dates = await self.get_expiry_dates(NIFTY_INDEX_SYMBOL)
                if nifty_expiry_dates:
                    nifty_strikes = self.select_atm_strikes(nifty_ltp, NIFTY_STRIKE_INTERVAL)
                    for strike in nifty_strikes:
                        for option_type in ["CE", "PE"]:
                            symbol = self.format_option_symbol("NIFTY", nifty_expiry_dates[0], strike, option_type)
                            atm_symbols.append(symbol)
                            logger.info(f"Selected Nifty ATM: {symbol}")

            # Get BankNifty ATM options
            banknifty_ltp = await self.get_index_ltp(BANKNIFTY_INDEX_SYMBOL)
            if banknifty_ltp:
                banknifty_expiry_dates = await self.get_expiry_dates(BANKNIFTY_INDEX_SYMBOL)
                if banknifty_expiry_dates:
                    banknifty_strikes = self.select_atm_strikes(banknifty_ltp, BANKNIFTY_STRIKE_INTERVAL)
                    for strike in banknifty_strikes:
                        for option_type in ["CE", "PE"]:
                            symbol = self.format_option_symbol("BANKNIFTY", banknifty_expiry_dates[0], strike, option_type)
                            atm_symbols.append(symbol)
                            logger.info(f"Selected BankNifty ATM: {symbol}")

            logger.info(f"Total ATM symbols selected: {len(atm_symbols)}")
            return atm_symbols

        except Exception as e:
            logger.error(f"Error selecting ATM options: {e}")
            return []

    async def connect_to_openalgo_websocket(self) -> bool:
        """Connect to OpenAlgo WebSocket"""
        try:
            logger.info(f"Connecting to OpenAlgo WebSocket at {self.ws_url}...")
            self.websocket = await websockets.connect(self.ws_url, max_size=16*1024*1024)

            # Authenticate with OpenAlgo
            auth_message = {
                "action": "authenticate",
                "api_key": self.api_key
            }
            await self.websocket.send(json.dumps(auth_message))

            # Wait for authentication response
            response = await self.websocket.recv()
            auth_response = json.loads(response)

            if auth_response.get("status") == "success":
                logger.info("Successfully authenticated with OpenAlgo WebSocket")
                return True
            else:
                logger.error(f"Authentication failed: {auth_response.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Error connecting to OpenAlgo WebSocket: {e}")
            return False

    async def subscribe_to_symbols(self, symbols: List[Dict[str, str]], mode: int = 1):
        """Subscribe to symbols via OpenAlgo WebSocket"""
        try:
            for symbol_info in symbols:
                subscribe_message = {
                    "action": "subscribe",
                    "symbol": symbol_info["symbol"],
                    "exchange": symbol_info["exchange"],
                    "mode": mode
                }
                await self.websocket.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to {symbol_info['symbol']}.{symbol_info['exchange']} in mode {mode}")

        except Exception as e:
            logger.error(f"Error subscribing to symbols: {e}")

    async def handle_market_data(self, data: Dict):
        """Handle incoming market data from OpenAlgo"""
        try:
            if data.get("type") == "market_data":
                topic = data.get("topic", "")
                market_data = data.get("data", {})

                if market_data:
                    symbol = market_data.get("symbol", "")
                    exchange = market_data.get("exchange", "")
                    ltp = market_data.get("ltp", 0)

                    # Log the data for AmiBroker integration
                    logger.info(f"Market Data: {symbol}.{exchange} LTP: {ltp}")

                    # Here you would format the data for AmiBroker
                    # For now, we're logging it - you can add your AmiBroker integration here

        except Exception as e:
            logger.error(f"Error handling market data: {e}")

    async def send_all_symbols_to_amibroker(self):
        """Send all symbols for AmiBroker discovery"""
        try:
            # Combine complete symbol mapping with ATM symbols
            all_symbols = []

            # Add futures and equity symbols
            for openalgo_symbol, amibroker_symbol in self.symbol_mapping.items():
                exchange = openalgo_symbol.split(":")[0]
                symbol = openalgo_symbol.split(":")[1]
                all_symbols.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "amibroker_symbol": amibroker_symbol
                })

            # Add ATM option symbols
            for atm_symbol in self.atm_symbols:
                all_symbols.append({
                    "symbol": atm_symbol,
                    "exchange": "NFO",
                    "amibroker_symbol": atm_symbol
                })

            logger.info(f"Total symbols for AmiBroker: {len(all_symbols)}")

            # Subscribe to all symbols
            await self.subscribe_to_symbols(all_symbols)

            return True

        except Exception as e:
            logger.error(f"Error sending symbols to AmiBroker: {e}")
            return False

    async def run_daily_atm_selection(self):
        """Run daily ATM option selection"""
        try:
            logger.info("Starting daily ATM option selection...")
            self.atm_symbols = await self.select_and_subscribe_atm_options()

            if self.atm_symbols:
                logger.info(f"Successfully selected {len(self.atm_symbols)} ATM symbols")
                # Send all symbols including new ATM options
                await self.send_all_symbols_to_amibroker()
            else:
                logger.warning("No ATM symbols selected")

        except Exception as e:
            logger.error(f"Error in daily ATM selection: {e}")

    async def listen_for_market_data(self):
        """Listen for market data from OpenAlgo WebSocket"""
        try:
            while True:
                if self.websocket and not self.websocket.closed:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    await self.handle_market_data(data)
                else:
                    logger.warning("WebSocket connection lost, attempting to reconnect...")
                    if await self.connect_to_openalgo_websocket():
                        await self.send_all_symbols_to_amibroker()
                    else:
                        await asyncio.sleep(5)  # Wait before retrying

        except websockets.exceptions.ConnectionClosed:
            logger.error("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in market data listener: {e}")

    async def run(self):
        """Main run method"""
        try:
            logger.info("Starting OpenAlgo Automatic Symbol Injector...")
            logger.info(f"Managing {len(self.symbol_mapping)} symbols from your original system")

            # Connect to OpenAlgo WebSocket
            if not await self.connect_to_openalgo_websocket():
                logger.error("Failed to connect to OpenAlgo WebSocket")
                return

            # Run daily ATM selection
            await self.run_daily_atm_selection()

            # Start listening for market data
            logger.info("Starting market data listener...")
            await self.listen_for_market_data()

        except Exception as e:
            logger.error(f"Error in main run method: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()

async def main():
    """Main function"""
    injector = OpenAlgoAutomaticInjector()
    await injector.run()

if __name__ == "__main__":
    asyncio.run(main())
