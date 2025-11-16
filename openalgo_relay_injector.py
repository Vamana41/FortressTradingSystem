#!/usr/bin/env python3
"""
OpenAlgo Relay Injector - Uses your existing relay server architecture

This connects to your relay server at ws://localhost:10102 and sends
real-time data in the exact format your AmiBroker expects.
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
RELAY_SERVER_URI = "ws://localhost:10102"
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"

# Complete symbol mapping from your original system - ALL 13 SYMBOLS
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
OPTION_CHAIN_STRIKE_COUNT = 2

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_relay_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoRelayInjector")

class OpenAlgoRelayInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.relay_uri = RELAY_SERVER_URI
        self.symbol_mapping = COMPLETE_SYMBOL_MAPPING.copy()
        self.atm_symbols = []
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
                    logger.info(f"Got quote for {exchange}:{symbol}: {ltp}")
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
    
    def select_atm_options(self) -> List[str]:
        """Select ATM options for Nifty and BankNifty"""
        atm_symbols = []
        
        try:
            logger.info("Starting automatic ATM option selection...")
            
            # Get Nifty ATM options
            nifty_ltp = self.get_quote("NSE", "NIFTY")
            if nifty_ltp:
                nifty_strikes = self.select_atm_strikes(nifty_ltp, NIFTY_STRIKE_INTERVAL)
                # Use current date + 7 days for weekly expiry
                expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                
                for strike in nifty_strikes:
                    for option_type in ["CE", "PE"]:
                        symbol = self.format_option_symbol("NIFTY", expiry_date, strike, option_type)
                        atm_symbols.append(symbol)
                        logger.info(f"Auto-selected Nifty ATM: {symbol}")
            
            # Get BankNifty ATM options
            banknifty_ltp = self.get_quote("NSE", "BANKNIFTY")
            if banknifty_ltp:
                banknifty_strikes = self.select_atm_strikes(banknifty_ltp, BANKNIFTY_STRIKE_INTERVAL)
                expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                
                for strike in banknifty_strikes:
                    for option_type in ["CE", "PE"]:
                        symbol = self.format_option_symbol("BANKNIFTY", expiry_date, strike, option_type)
                        atm_symbols.append(symbol)
                        logger.info(f"Auto-selected BankNifty ATM: {symbol}")
            
            logger.info(f"Total ATM symbols auto-selected: {len(atm_symbols)}")
            return atm_symbols
            
        except Exception as e:
            logger.error(f"Error in automatic ATM selection: {e}")
            return []
    
    def get_all_symbols(self) -> List[Dict[str, str]]:
        """Get all symbols for automatic injection"""
        all_symbols = []
        
        # Add all 13 symbols from your original system
        for openalgo_symbol, amibroker_symbol in self.symbol_mapping.items():
            exchange = openalgo_symbol.split(":")[0]
            symbol = openalgo_symbol.split(":")[1]
            all_symbols.append({
                "openalgo_symbol": openalgo_symbol,
                "amibroker_symbol": amibroker_symbol,
                "exchange": exchange,
                "symbol": symbol
            })
        
        # Add ATM option symbols
        for atm_symbol in self.atm_symbols:
            all_symbols.append({
                "openalgo_symbol": f"NFO:{atm_symbol}",
                "amibroker_symbol": atm_symbol,
                "exchange": "NFO", 
                "symbol": atm_symbol
            })
        
        logger.info(f"Total symbols for automatic injection: {len(all_symbols)}")
        return all_symbols
    
    async def send_rtd_to_relay(self, ami_symbol: str, ltp: float, timestamp: datetime.datetime):
        """Send real-time data to relay server in correct format"""
        try:
            # Format: {"n": "SBIN", "d": 20251116, "t": 134500, "o": 967.85, "h": 969.05, "l": 952.0, "c": 967.85, "v": 11032927}
            d = int(timestamp.strftime("%Y%m%d"))
            t = int(timestamp.strftime("%H%M00"))
            
            # Create RTD bar - using LTP for all OHLC values since we only have LTP
            rtd_bar = [{"n": ami_symbol, "d": d, "t": t, "o": ltp, "h": ltp, "l": ltp, "c": ltp, "v": 0}]
            
            if self.websocket and not self.websocket.closed:
                await self.websocket.send(json.dumps(rtd_bar, separators=(',', ':')))
                logger.info(f"--> Sent RTD to relay: {ami_symbol} LTP: {ltp}")
            else:
                logger.warning(f"Relay connection not available, cannot send RTD for {ami_symbol}")
                
        except Exception as e:
            logger.error(f"Error sending RTD to relay for {ami_symbol}: {e}")
    
    async def connect_to_relay(self):
        """Connect to relay server"""
        try:
            logger.info(f"Connecting to relay server at {self.relay_uri}...")
            self.websocket = await websockets.connect(self.relay_uri)
            logger.info(">>> Connected to Relay Server <<<")
            
            # Send role message
            await self.websocket.send("rolesend")
            logger.info("Sent 'rolesend' to relay")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to relay server: {e}")
            return False
    
    async def start_automatic_injection(self):
        """Start automatic symbols injection with real-time data"""
        all_symbols = self.get_all_symbols()
        
        logger.info("=" * 80)
        logger.info("AUTOMATIC SYMBOLS INJECTION TO RELAY ACTIVE!")
        logger.info("=" * 80)
        logger.info("All symbols are being injected automatically into AmiBroker via relay:")
        
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
            logger.info("OPENALGO RELAY INJECTOR STARTING...")
            logger.info("=" * 80)
            logger.info(f"Managing ALL {len(self.symbol_mapping)} symbols from your original system")
            
            # Test connection first
            if not self.test_connection():
                logger.error("Failed to connect to OpenAlgo - check API key and OpenAlgo status")
                return
            
            # Select ATM options automatically
            logger.info("Automatically selecting ATM options...")
            self.atm_symbols = self.select_atm_options()
            
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
    injector = OpenAlgoRelayInjector()
    await injector.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Injector stopped by user")