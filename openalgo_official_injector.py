#!/usr/bin/env python3
"""
OpenAlgo Official Symbol Injector - Follows OpenAlgo documentation exactly
Uses WebSocket to subscribe to symbols, which are then automatically sent to AmiBroker via the official plugin
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
logger = logging.getLogger("OpenAlgoOfficialInjector")

# Configuration - Using official OpenAlgo settings
OPENALGO_API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
REST_API_URL = "http://127.0.0.1:5000/api/v1"
WEBSOCKET_URL = "ws://127.0.0.1:8765"

# All symbols from your original system in OpenAlgo format
# Based on https://docs.openalgo.in/symbol-format
ALL_SYMBOLS = [
    # NSE Cash - Format: SYMBOL (not NSE:SYMBOL)
    {"symbol": "SBIN", "exchange": "NSE"},
    {"symbol": "RELIANCE", "exchange": "NSE"},
    {"symbol": "TCS", "exchange": "NSE"},
    {"symbol": "INFY", "exchange": "NSE"},
    {"symbol": "ITC", "exchange": "NSE"},
    
    # Nifty and BankNifty indices for ATM options
    {"symbol": "NIFTY", "exchange": "NSE"},
    {"symbol": "BANKNIFTY", "exchange": "NSE"},
    
    # MCX Commodities - Format: SYMBOL (not MCX:SYMBOL)
    {"symbol": "CRUDEOIL", "exchange": "MCX"},
    {"symbol": "GOLD", "exchange": "MCX"},
    {"symbol": "SILVER", "exchange": "MCX"},
    {"symbol": "COPPER", "exchange": "MCX"},
    {"symbol": "NATURALGAS", "exchange": "MCX"}
]

class OpenAlgoOfficialInjector:
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.authenticated = False
        
    async def connect_to_openalgo_websocket(self):
        """Connect to OpenAlgo WebSocket using official protocol"""
        try:
            logger.info(f"🔗 Connecting to OpenAlgo WebSocket at {WEBSOCKET_URL}")
            self.websocket = await websockets.connect(WEBSOCKET_URL)
            self.connected = True
            logger.info("✅ Connected to OpenAlgo WebSocket")
            
            # Authenticate using API key
            auth_message = {
                "action": "authenticate",
                "api_key": OPENALGO_API_KEY
            }
            
            await self.websocket.send(json.dumps(auth_message))
            logger.info("📤 Sent authentication request")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            return False
    
    async def subscribe_to_symbols(self, symbols: List[Dict[str, str]]):
        """Subscribe to market data for symbols using official format"""
        if not self.connected:
            logger.error("Not connected to WebSocket")
            return False
            
        try:
            # Subscribe to each symbol individually (official OpenAlgo format)
            for symbol_info in symbols:
                symbol = symbol_info["symbol"]
                exchange = symbol_info["exchange"]
                
                subscribe_message = {
                    "action": "subscribe",
                    "symbol": symbol,
                    "exchange": exchange,
                    "mode": "Quote"  # Options: LTP, Quote, Depth
                }
                
                await self.websocket.send(json.dumps(subscribe_message))
                logger.info(f"📤 Subscribed to {exchange}:{symbol}")
                
                # Small delay between subscriptions
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ Successfully subscribed to {len(symbols)} symbols")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to symbols: {e}")
            return False
    
    async def listen_for_market_data(self):
        """Listen for market data from OpenAlgo"""
        try:
            logger.info("👂 Listening for market data from OpenAlgo...")
            logger.info("📊 Data will be automatically forwarded to AmiBroker via the official plugin")
            
            while self.connected:
                try:
                    # Receive market data with timeout
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    # Log received data
                    if "data" in data and isinstance(data["data"], dict):
                        symbol_data = data["data"]
                        symbol = symbol_data.get("symbol", "Unknown")
                        exchange = symbol_data.get("exchange", "Unknown")
                        ltp = symbol_data.get("ltp", 0)
                        
                        # Format for AmiBroker (SYMBOL-EXCHANGE format)
                        ami_format = f"{symbol}-{exchange}"
                        logger.info(f"📈 Received: {ami_format} LTP: {ltp}")
                        
                        # This data is automatically sent to AmiBroker via the official plugin
                        # No additional processing needed!
                        
                    else:
                        # Log other messages (auth responses, etc.)
                        logger.debug(f"📨 Received: {data}")
                        
                        # Check if this is an authentication response
                        if data.get("status") == "success" and "authenticated" in str(data).lower():
                            self.authenticated = True
                            logger.info("✅ Authentication successful!")
                        
                except asyncio.TimeoutError:
                    # No data received, but connection is still alive
                    logger.debug("⏰ No data received in 30 seconds, connection still active")
                    continue
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️  Invalid JSON received: {e}")
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"❌ Error in listen loop: {e}")
            self.connected = False
    
    async def run_injection(self):
        """Main injection process following OpenAlgo official protocol"""
        logger.info("=" * 80)
        logger.info("🏛️  OPENALGO OFFICIAL SYMBOL INJECTOR")
        logger.info("=" * 80)
        logger.info("This injector follows OpenAlgo official documentation")
        logger.info("Symbols subscribed via WebSocket are automatically sent to AmiBroker")
        logger.info("=" * 80)
        
        # Test REST API first to verify symbols work
        logger.info("🔍 Testing symbols via REST API first...")
        working_symbols = []
        
        for symbol_info in ALL_SYMBOLS:
            symbol = symbol_info["symbol"]
            exchange = symbol_info["exchange"]
            
            try:
                # Test via REST API
                url = f"{REST_API_URL}/quotes"
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
                        logger.info(f"✅ {exchange}:{symbol} - LTP: {ltp}")
                        working_symbols.append(symbol_info)
                    else:
                        logger.warning(f"⚠️  {exchange}:{symbol} - API error: {data}")
                else:
                    logger.error(f"❌ {exchange}:{symbol} - HTTP error: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ {exchange}:{symbol} - Failed: {e}")
        
        logger.info(f"🔍 Found {len(working_symbols)} working symbols out of {len(ALL_SYMBOLS)}")
        
        if not working_symbols:
            logger.error("❌ No working symbols found. Check API key and OpenAlgo status.")
            return
        
        # Connect to WebSocket
        if not await self.connect_to_openalgo_websocket():
            logger.error("❌ Failed to connect to OpenAlgo WebSocket")
            return
        
        # Subscribe to working symbols
        if not await self.subscribe_to_symbols(working_symbols):
            logger.error("❌ Failed to subscribe to symbols")
            return
        
        logger.info("🎯 SYMBOLS NOW ACTIVE:")
        logger.info("=" * 60)
        for symbol_info in working_symbols:
            symbol = symbol_info["symbol"]
            exchange = symbol_info["exchange"]
            ami_format = f"{symbol}-{exchange}"
            logger.info(f"   ✓ {ami_format}")
        logger.info("=" * 60)
        logger.info("💡 These symbols should now appear automatically in AmiBroker!")
        logger.info("💡 The official OpenAlgo plugin will handle the data forwarding.")
        
        # Listen for market data
        await self.listen_for_market_data()
        
        # Cleanup
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 WebSocket connection closed")

async def main():
    """Main function"""
    injector = OpenAlgoOfficialInjector()
    try:
        await injector.run_injection()
    except KeyboardInterrupt:
        logger.info("🛑 Injector stopped by user")

if __name__ == "__main__":
    asyncio.run(main())