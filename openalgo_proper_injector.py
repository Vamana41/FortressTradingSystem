#!/usr/bin/env python3
"""
OpenAlgo Proper Symbol Injector - Uses correct OpenAlgo WebSocket protocol
This sends symbols to OpenAlgo via WebSocket, which then forwards to AmiBroker
"""

import asyncio
import websockets
import json
import logging
import datetime
import time
import requests
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OpenAlgoProperInjector")

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
    
    # Nifty ATM Options (will be calculated dynamically)
    {"symbol": "NIFTY", "exchange": "NSE"},
    
    # BankNifty ATM Options (will be calculated dynamically)  
    {"symbol": "BANKNIFTY", "exchange": "NSE"},
    
    # MCX Commodities
    {"symbol": "CRUDEOIL", "exchange": "MCX"},
    {"symbol": "GOLD", "exchange": "MCX"},
    {"symbol": "SILVER", "exchange": "MCX"},
    {"symbol": "COPPER", "exchange": "MCX"},
    {"symbol": "NATURALGAS", "exchange": "MCX"}
]

class OpenAlgoProperInjector:
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.authenticated = False
        
    async def connect_to_openalgo(self):
        """Connect to OpenAlgo WebSocket server"""
        try:
            logger.info(f"Connecting to OpenAlgo WebSocket at {WEBSOCKET_URL}")
            self.websocket = await websockets.connect(WEBSOCKET_URL)
            
            # Authenticate first
            auth_msg = {
                "action": "authenticate",
                "api_key": OPENALGO_API_KEY
            }
            
            await self.websocket.send(json.dumps(auth_msg))
            logger.info("Sent authentication request")
            
            # Wait for authentication response
            response = await self.websocket.recv()
            auth_data = json.loads(response)
            
            if auth_data.get("status") == "success":
                self.authenticated = True
                self.connected = True
                logger.info("✅ Successfully authenticated with OpenAlgo")
                return True
            else:
                logger.error(f"❌ Authentication failed: {auth_data}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to OpenAlgo: {e}")
            return False
    
    async def subscribe_to_symbols(self, symbols: List[Dict[str, str]]):
        """Subscribe to market data for symbols"""
        if not self.connected or not self.authenticated:
            logger.error("Not connected or authenticated")
            return False
            
        try:
            subscribe_msg = {
                "action": "subscribe",
                "symbols": symbols,
                "mode": "Quote"
            }
            
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {len(symbols)} symbols")
            
            # Wait for subscription confirmation
            response = await self.websocket.recv()
            sub_data = json.loads(response)
            logger.info(f"Subscription response: {sub_data}")
            
            return sub_data.get("status") == "success"
            
        except Exception as e:
            logger.error(f"Failed to subscribe to symbols: {e}")
            return False
    
    async def get_quotes_from_rest_api(self, symbols: List[Dict[str, str]]):
        """Get current quotes using REST API"""
        quotes = {}
        
        for symbol_info in symbols:
            symbol = symbol_info["symbol"]
            exchange = symbol_info["exchange"]
            
            try:
                # Use OpenAlgo REST API to get quotes
                url = f"{OPENALGO_BASE_URL}/quotes"
                payload = {
                    "apikey": OPENALGO_API_KEY,
                    "exchange": exchange,
                    "symbol": symbol
                }
                
                response = requests.post(url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        quote_data = data.get("data", {})
                        ltp = quote_data.get("ltp", 0)
                        
                        # Format for AmiBroker
                        ami_symbol = f"{symbol}-{exchange}"
                        quotes[ami_symbol] = {
                            "symbol": symbol,
                            "exchange": exchange,
                            "ltp": ltp,
                            "open": quote_data.get("open", ltp),
                            "high": quote_data.get("high", ltp),
                            "low": quote_data.get("low", ltp),
                            "prev_close": quote_data.get("prev_close", ltp),
                            "volume": quote_data.get("volume", 0)
                        }
                        
                        logger.info(f"Got quote for {ami_symbol}: LTP {ltp}")
                    else:
                        logger.warning(f"API error for {symbol}: {data}")
                else:
                    logger.error(f"HTTP error for {symbol}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Failed to get quote for {symbol}: {e}")
                
        return quotes
    
    async def run_injection_loop(self):
        """Main injection loop"""
        logger.info("Starting OpenAlgo symbol injection...")
        
        # Connect to OpenAlgo
        if not await self.connect_to_openalgo():
            logger.error("Failed to connect to OpenAlgo")
            return
        
        # Subscribe to all symbols
        if not await self.subscribe_to_symbols(ALL_SYMBOLS):
            logger.error("Failed to subscribe to symbols")
            return
        
        logger.info("✅ Successfully subscribed to all symbols!")
        logger.info("Symbols will now be automatically available in AmiBroker via OpenAlgo")
        
        # Keep the connection alive and handle incoming data
        try:
            cycle = 1
            while True:
                logger.info(f"--- Cycle #{cycle} ---")
                
                # Get current quotes
                quotes = await self.get_quotes_from_rest_api(ALL_SYMBOLS)
                
                if quotes:
                    logger.info(f"Retrieved quotes for {len(quotes)} symbols")
                    for ami_symbol, quote in quotes.items():
                        logger.info(f"  {ami_symbol}: LTP {quote['ltp']}")
                
                # Wait before next cycle
                await asyncio.sleep(5)
                cycle += 1
                
        except KeyboardInterrupt:
            logger.info("Stopping injection...")
        except Exception as e:
            logger.error(f"Error in injection loop: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()
                logger.info("WebSocket connection closed")

async def main():
    """Main function"""
    logger.info("=" * 80)
    logger.info("OPENALGO PROPER SYMBOL INJECTOR")
    logger.info("=" * 80)
    logger.info("This injector uses OpenAlgo's native WebSocket protocol")
    logger.info("to automatically inject symbols into AmiBroker")
    logger.info("=" * 80)
    
    injector = OpenAlgoProperInjector()
    await injector.run_injection_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Injector stopped by user")