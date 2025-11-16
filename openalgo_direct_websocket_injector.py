#!/usr/bin/env python3
"""
OpenAlgo Direct WebSocket Injector - Connects directly to OpenAlgo's WebSocket server
This eliminates the need for a separate relay server and uses OpenAlgo's native WebSocket implementation
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
OPENALGO_API_KEY = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
OPENALGO_BASE_URL = "http://127.0.0.1:5000/api/v1"
OPENALGO_WS_URL = "ws://127.0.0.1:8765"
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
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_direct_websocket_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoDirectWebSocketInjector")

class OpenAlgoDirectWebSocketInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.ws_url = OPENALGO_WS_URL
        self.symbol_mapping = WORKING_SYMBOL_MAPPING.copy()
        self.websocket = None
        self.running = False
        
    def test_connection(self) -> bool:
        """Test connection to OpenAlgo using correct POST endpoint"""
        try:
            url = f"{self.base_url}/ping"
            payload = {
                'apikey': self.api_key
            }
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    broker = data["data"]["broker"]
                    logger.info(f"SUCCESS: OpenAlgo API working! Connected to broker: {broker}")
                    return True
                else:
                    logger.warning(f"Ping response: {data}")
            elif response.status_code == 403:
                logger.error(f"API key invalid - need to refresh")
                return False
            else:
                logger.warning(f"Ping HTTP {response.status_code}: {response.text}")
            
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
    
    async def send_rtd_to_openalgo_ws(self, ami_symbol: str, ltp: float, timestamp: datetime.datetime):
        """Send real-time data to OpenAlgo WebSocket in correct RTD format"""
        try:
            # Format: {"n": "SBIN-NSE", "d": 20251116, "t": 134500, "o": 967.85, "h": 969.05, "l": 952.0, "c": 967.85, "v": 11032927}
            d = int(timestamp.strftime("%Y%m%d"))
            t = int(timestamp.strftime("%H%M00"))
            
            # Create RTD bar - using LTP for all OHLC values since we only have LTP
            rtd_bar = [{"n": ami_symbol, "d": d, "t": t, "o": ltp, "h": ltp, "l": ltp, "c": ltp, "v": 0}]
            
            if self.websocket:
                await self.websocket.send(json.dumps(rtd_bar, separators=(',', ':')))
                logger.info(f"--> SENT TO OPENALGO WS: {ami_symbol} LTP: {ltp}")
            else:
                logger.warning(f"OpenAlgo WebSocket not connected, cannot send RTD for {ami_symbol}")
                
        except Exception as e:
            logger.error(f"Error sending RTD to OpenAlgo WebSocket for {ami_symbol}: {e}")
    
    async def connect_to_openalgo_ws(self):
        """Connect to OpenAlgo WebSocket server"""
        try:
            logger.info(f"Connecting to OpenAlgo WebSocket at {self.ws_url}...")
            self.websocket = await websockets.connect(self.ws_url)
            logger.info(">>> CONNECTED TO OPENALGO WEBSOCKET SERVER <<<")
            
            # Send authentication or role message if needed
            auth_message = {
                "type": "auth",
                "apikey": self.api_key
            }
            await self.websocket.send(json.dumps(auth_message))
            logger.info("Sent authentication to OpenAlgo WebSocket")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAlgo WebSocket: {e}")
            return False
    
    async def start_automatic_injection(self):
        """Start automatic symbols injection with real-time data to OpenAlgo WebSocket"""
        all_symbols = self.get_all_symbols()
        
        logger.info("=" * 80)
        logger.info("AUTOMATIC SYMBOLS INJECTION TO OPENALGO WEBSOCKET ACTIVE!")
        logger.info("=" * 80)
        logger.info("All working symbols are being injected automatically into AmiBroker via OpenAlgo:")
        
        # Display all symbols
        for symbol_info in all_symbols:
            logger.info(f"  {symbol_info['openalgo_symbol']} -> {symbol_info['amibroker_symbol']}")
        
        logger.info("=" * 80)
        logger.info("Real-time data streaming to OpenAlgo WebSocket starting...")
        logger.info("=" * 80)
        
        # Connect to OpenAlgo WebSocket first
        if not await self.connect_to_openalgo_ws():
            logger.error("Failed to connect to OpenAlgo WebSocket - cannot proceed")
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
                        
                        # Send to OpenAlgo WebSocket
                        await self.send_rtd_to_openalgo_ws(amibroker_symbol, ltp, timestamp)
                        
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
            logger.info("OPENALGO DIRECT WEBSOCKET INJECTOR STARTING...")
            logger.info("=" * 80)
            logger.info(f"Managing {len(self.symbol_mapping)} working symbols")
            
            # Test connection first
            if not self.test_connection():
                logger.error("Failed to connect to OpenAlgo - check API key and OpenAlgo status")
                return
            
            # Start automatic real-time data streaming to OpenAlgo WebSocket
            await self.start_automatic_injection()
            
        except Exception as e:
            logger.error(f"Error in automatic injection: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()
                logger.info("Closed OpenAlgo WebSocket connection")

async def main():
    """Main async entry point"""
    injector = OpenAlgoDirectWebSocketInjector()
    await injector.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Injector stopped by user")