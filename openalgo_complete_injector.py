#!/usr/bin/env python3
"""
OpenAlgo Native Symbol Injector with Full Exchange Support
Uses OpenAlgo's native APIs to automatically inject symbols from ALL exchanges
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
logger = logging.getLogger('OpenAlgoCompleteInjector')

class OpenAlgoCompleteInjector:
    def __init__(self):
        self.ws_url = os.getenv('OPENALGO_WS_URL', 'ws://127.0.0.1:8765')
        self.api_key = '703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b'
        self.base_url = 'http://127.0.0.1:5000/api/v1'
        self.websocket = None
        self.authenticated = False

        # Original symbols from your system
        self.original_symbols = [
            "SBIN", "RELIANCE", "TCS", "INFY", "ITC",
            "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "NICKEL"
        ]

        # ATM options will be added
        self.atm_symbols = []

        # All working symbols found
        self.working_symbols = []

    async def search_symbols(self, query, exchange=None):
        """Search for symbols using OpenAlgo Search API"""
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
                    logger.info(f"Found {len(symbols)} symbols for {query}")
                    return symbols
                else:
                    logger.warning(f"Search failed for {query}: {result.get('message')}")
            else:
                logger.error(f"Search API error {response.status_code}: {response.text}")

        except Exception as e:
            logger.error(f"Search error for {query}: {e}")

        return []

    async def get_atm_options(self):
        """Get ATM options using OpenAlgo OptionSymbol API"""
        try:
            # Get current date for expiry
            today = datetime.now()

            # Get next monthly expiry (last Thursday of month)
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            last_thursday = last_day - ((last_day - calendar.THURSDAY) % 7)
            if last_thursday < today.day:
                # Next month
                if today.month == 12:
                    next_month = 1
                    next_year = today.year + 1
                else:
                    next_month = today.month + 1
                    next_year = today.year
                last_day = calendar.monthrange(next_year, next_month)[1]
                last_thursday = last_day - ((last_day - calendar.THURSDAY) % 7)
                expiry_date = f"{last_thursday:02d}{calendar.month_abbr[next_month].upper()}{str(next_year)[2:]}"
            else:
                expiry_date = f"{last_thursday:02d}{calendar.month_abbr[today.month].upper()}{str(today.year)[2:]}"

            logger.info(f"Getting ATM options for expiry: {expiry_date}")

            # Get NIFTY ATM
            nifty_atm_data = {
                "apikey": self.api_key,
                "strategy": "nifty_atm",
                "underlying": "NIFTY",
                "exchange": "NSE_INDEX",
                "expiry_date": expiry_date,
                "strike_int": 50,
                "offset": "ATM",
                "option_type": "CE"
            }

            response = requests.post(
                f"{self.base_url}/optionsymbol",
                json=nifty_atm_data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    nifty_ce = result.get("symbol")
                    nifty_exchange = result.get("exchange", "NFO")
                    logger.info(f"NIFTY ATM CE: {nifty_ce}")
                    self.atm_symbols.append({"symbol": nifty_ce, "exchange": nifty_exchange})

                    # Get PE as well
                    nifty_atm_data["option_type"] = "PE"
                    response = requests.post(
                        f"{self.base_url}/optionsymbol",
                        json=nifty_atm_data,
                        timeout=10
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "success":
                            nifty_pe = result.get("symbol")
                            logger.info(f"NIFTY ATM PE: {nifty_pe}")
                            self.atm_symbols.append({"symbol": nifty_pe, "exchange": nifty_exchange})

            # Get BANKNIFTY ATM
            banknifty_atm_data = {
                "apikey": self.api_key,
                "strategy": "banknifty_atm",
                "underlying": "BANKNIFTY",
                "exchange": "NSE_INDEX",
                "expiry_date": expiry_date,
                "strike_int": 100,
                "offset": "ATM",
                "option_type": "CE"
            }

            response = requests.post(
                f"{self.base_url}/optionsymbol",
                json=banknifty_atm_data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    banknifty_ce = result.get("symbol")
                    banknifty_exchange = result.get("exchange", "NFO")
                    logger.info(f"BANKNIFTY ATM CE: {banknifty_ce}")
                    self.atm_symbols.append({"symbol": banknifty_ce, "exchange": banknifty_exchange})

                    # Get PE as well
                    banknifty_atm_data["option_type"] = "PE"
                    response = requests.post(
                        f"{self.base_url}/optionsymbol",
                        json=banknifty_atm_data,
                        timeout=10
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "success":
                            banknifty_pe = result.get("symbol")
                            logger.info(f"BANKNIFTY ATM PE: {banknifty_pe}")
                            self.atm_symbols.append({"symbol": banknifty_pe, "exchange": banknifty_exchange})

        except Exception as e:
            logger.error(f"ATM options error: {e}")

    async def find_all_symbols(self):
        """Find all symbols using OpenAlgo Search API"""
        logger.info("Finding all symbols using OpenAlgo Search API...")

        # Get ATM options first
        await self.get_atm_options()

        # Search for each original symbol
        for symbol in self.original_symbols:
            # Search in different exchanges
            exchanges_to_try = ["NSE", "BSE", "MCX", "NFO", "CDS"]

            for exchange in exchanges_to_try:
                symbols = await self.search_symbols(symbol, exchange)
                if symbols:
                    for found_symbol in symbols:
                        self.working_symbols.append({
                            "symbol": found_symbol["symbol"],
                            "exchange": found_symbol["exchange"],
                            "name": found_symbol.get("name", ""),
                            "instrumenttype": found_symbol.get("instrumenttype", "")
                        })
                    break  # Found symbol, move to next one

            # If not found with exchange filter, try without
            if not any(s["symbol"] == symbol for s in self.working_symbols):
                symbols = await self.search_symbols(symbol)
                if symbols:
                    for found_symbol in symbols:
                        self.working_symbols.append({
                            "symbol": found_symbol["symbol"],
                            "exchange": found_symbol["exchange"],
                            "name": found_symbol.get("name", ""),
                            "instrumenttype": found_symbol.get("instrumenttype", "")
                        })

        # Add ATM options
        for atm_option in self.atm_symbols:
            self.working_symbols.append({
                "symbol": atm_option["symbol"],
                "exchange": atm_option["exchange"],
                "name": f"ATM Option {atm_option['symbol']}",
                "instrumenttype": "OPTIDX"
            })

        logger.info(f"Found {len(self.working_symbols)} total symbols")

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

            logger.info(f"Subscribing to {symbol_info['exchange']}:{symbol_info['symbol']} ({symbol_info.get('name', '')})")
            await self.websocket.send(json.dumps(subscribe_message))

            # Wait for confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            response_data = json.loads(response)

            status = response_data.get("status", "unknown")

            if status == "success":
                logger.info(f"✅ Successfully subscribed to {symbol_info['exchange']}:{symbol_info['symbol']}")
                return True
            elif status == "partial":
                # Check individual subscription status
                subscriptions = response_data.get("subscriptions", [])
                for sub in subscriptions:
                    sub_status = sub.get('status', 'unknown')
                    if sub_status == "success":
                        logger.info(f"✅ Successfully subscribed to {symbol_info['exchange']}:{symbol_info['symbol']}")
                        return True
                    else:
                        logger.warning(f"⚠️  Failed to subscribe to {symbol_info['exchange']}:{symbol_info['symbol']}: {sub.get('message', 'Unknown error')}")
                        return False
            else:
                logger.warning(f"⚠️  Subscription failed for {symbol_info['exchange']}:{symbol_info['symbol']}: {response_data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"❌ Subscription error for {symbol_info['exchange']}:{symbol_info['symbol']}: {e}")
            return False

    async def inject_all_symbols(self):
        """Inject all found symbols"""
        logger.info("="*60)
        logger.info("OPENALGO COMPLETE SYMBOL INJECTOR STARTING...")
        logger.info("="*60)

        logger.info(f"Injecting {len(self.working_symbols)} symbols:")
        for symbol_info in self.working_symbols:
            logger.info(f"  - {symbol_info['exchange']}:{symbol_info['symbol']} ({symbol_info.get('name', '')})")

        # Subscribe to all symbols
        success_count = 0
        for symbol_info in self.working_symbols:
            if await self.subscribe_symbol(symbol_info):
                success_count += 1

        logger.info(f"✅ Successfully subscribed to {success_count}/{len(self.working_symbols)} symbols")

        if success_count > 0:
            logger.info("🎉 SYMBOLS INJECTED SUCCESSFULLY!")
            logger.info("✅ Check AmiBroker - all symbols should now be available!")
            logger.info("✅ OpenAlgo is now feeding real-time data to AmiBroker!")

            # Keep the connection alive and listen for data
            await self.listen_for_data()
        else:
            logger.error("❌ Failed to inject any symbols")

    async def listen_for_data(self):
        """Listen for real-time data from OpenAlgo"""
        logger.info("Listening for real-time data...")

        try:
            while True:
                message = await self.websocket.recv()
                data = json.loads(message)

                # Log incoming data (you can remove this if too verbose)
                if "ltp" in str(data).lower():
                    logger.info(f"📊 Data received: {data}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error listening for data: {e}")

    async def run(self):
        """Main run loop"""
        try:
            # Find all symbols first
            await self.find_all_symbols()

            # Connect to WebSocket
            if not await self.connect():
                return

            # Authenticate
            if not await self.authenticate():
                return

            # Inject all symbols
            await self.inject_all_symbols()

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
    injector = OpenAlgoCompleteInjector()
    await injector.run()

if __name__ == "__main__":
    asyncio.run(main())
