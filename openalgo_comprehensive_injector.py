#!/usr/bin/env python3
"""
OpenAlgo Comprehensive Symbol Injector - Complete Solution

This script integrates OpenAlgo's data access with your complete symbol mapping,
including all futures, equities, and automatic ATM option selection.
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
RELAY_SERVER_URI = "ws://localhost:10102"
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

# Futures suffix for rollover detection
FUTURES_SUFFIX = "-FUT"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_comprehensive_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoComprehensiveInjector")

class OpenAlgoComprehensiveInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.relay_uri = RELAY_SERVER_URI
        self.master_contract_path = MASTER_CONTRACT_PATH
        self.websocket = None
        self.symbol_mapping = COMPLETE_SYMBOL_MAPPING.copy()  # Start with complete mapping
        self.current_bars = {}
        self.previous_vol = {}
        self.last_snapshot_time = {}
        self.daily_atm_symbols_file = None
        
    def get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def refresh_api_key(self) -> bool:
        """Get fresh API key from OpenAlgo dashboard or Fortress"""
        try:
            # First try Fortress API key manager
            fortress_key_file = r"C:\Users\Admin\.fortress\api_keys.enc"
            if os.path.exists(fortress_key_file):
                logger.info("Found Fortress API key file")
                # For now, we'll use the current key - in production, this would decrypt
                return bool(self.api_key)
            
            # If no API key available, guide user to get new one
            if not self.api_key:
                logger.warning("No API key found. Please:")
                logger.warning("1. Login to OpenAlgo at http://127.0.0.1:5000")
                logger.warning("2. Get your API key from the dashboard")
                logger.warning("3. Update the OPENALGO_API_KEY in openalgo_symbol_injector.env")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing API key: {e}")
            return False
    
    async def get_index_ltp(self, index_symbol: str) -> Optional[float]:
        """Get current LTP for an index from OpenAlgo"""
        try:
            url = f"{self.base_url}/api/v1/quotes"
            
            # Parse symbol and exchange
            if ":" in index_symbol:
                exchange, symbol = index_symbol.split(":", 1)
            else:
                exchange = "NSE"
                symbol = index_symbol
            
            payload = {
                "apikey": self.api_key,
                "symbol": symbol,
                "exchange": exchange
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data"):
                    quote_data = data["data"][0]
                    ltp = quote_data.get("last_price")
                    if ltp:
                        logger.info(f"Got {index_symbol} LTP: {ltp}")
                        return float(ltp)
                    else:
                        logger.error(f"No LTP found in quote data for {index_symbol}")
                else:
                    logger.error(f"Quote request failed for {index_symbol}: {data.get('message', 'Unknown error')}")
            elif response.status_code == 403:
                logger.error(f"API key invalid for {index_symbol} - need to refresh")
                await self.refresh_api_key()
            else:
                logger.error(f"HTTP {response.status_code} error getting quotes for {index_symbol}")
                logger.error(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting LTP for {index_symbol}: {e}")
        
        return None
    
    async def get_expiry_dates(self, underlying_symbol: str, instrument_type: str = "OPTIDX") -> Optional[List[str]]:
        """Get expiry dates for F&O instruments from OpenAlgo"""
        try:
            # Parse symbol and exchange
            if ":" in underlying_symbol:
                exchange, symbol = underlying_symbol.split(":", 1)
            else:
                exchange = "NSE"
                symbol = underlying_symbol
            
            url = f"{self.base_url}/api/v1/expiry"
            payload = {
                "apikey": self.api_key,
                "symbol": symbol,
                "exchange": exchange,
                "instrumenttype": instrument_type
            }
            
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data"):
                    expiry_dates = data["data"]
                    logger.info(f"Got {len(expiry_dates)} expiry dates for {underlying_symbol}")
                    return expiry_dates
                else:
                    logger.error(f"Expiry request failed for {underlying_symbol}: {data.get('message', 'Unknown error')}")
            elif response.status_code == 403:
                logger.error(f"API key invalid for expiry - need to refresh")
                await self.refresh_api_key()
            else:
                logger.error(f"HTTP {response.status_code} error getting expiry for {underlying_symbol}")
                logger.error(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting expiry dates for {underlying_symbol}: {e}")
        
        return None
    
    def calculate_atm_strike(self, ltp: float, strike_interval: int) -> int:
        """Calculate ATM strike price"""
        return round(ltp / strike_interval) * strike_interval
    
    def generate_amibroker_symbol(self, underlying: str, expiry_date: str, 
                                 strike: int, option_type: str) -> str:
        """Generate AmiBroker symbol format"""
        # Convert date format from "DD-MM-YYYY" to "DDMonYY"
        try:
            date_obj = datetime.datetime.strptime(expiry_date, "%d-%m-%Y")
            ami_date = date_obj.strftime("%d%b%y").upper()
            return f"{underlying}{ami_date}{int(strike)}{option_type}"
        except ValueError:
            # Fallback to direct format if parsing fails
            return f"{underlying}{expiry_date}{int(strike)}{option_type}"
    
    async def select_and_subscribe_atm_options(self, index_symbol: str, underlying: str, 
                                            strike_interval: int) -> Dict[str, str]:
        """Select ATM options and return symbol mapping"""
        logger.info(f"Selecting ATM options for {underlying}...")
        
        # Get index LTP
        ltp = await self.get_index_ltp(index_symbol)
        if ltp is None:
            logger.error(f"Failed to get LTP for {index_symbol}")
            return {}
        
        # Calculate target ATM strike
        target_atm_strike = self.calculate_atm_strike(ltp, strike_interval)
        logger.info(f"Target ATM strike for {underlying}: {target_atm_strike}")
        
        # Get expiry dates
        expiry_dates = await self.get_expiry_dates(index_symbol, "OPTIDX")
        if not expiry_dates:
            logger.error(f"Failed to get expiry dates for {index_symbol}")
            return {}
        
        # Filter valid expiries (today onwards) and take first 2
        today = datetime.date.today()
        valid_expiries = []
        for expiry_str in expiry_dates:
            try:
                expiry_date = datetime.datetime.strptime(expiry_str, "%d-%m-%Y").date()
                if expiry_date >= today:
                    valid_expiries.append(expiry_str)
            except ValueError:
                continue
        
        if not valid_expiries:
            logger.error(f"No valid expiries found for {underlying}")
            return {}
        
        expiries_to_process = valid_expiries[:2]  # Take nearest 2
        logger.info(f"Expiries to process for {underlying}: {expiries_to_process}")
        
        # Generate symbol mappings with closest available strikes
        symbol_mapping = {}
        
        for expiry_date in expiries_to_process:
            for option_type in ["CE", "PE"]:
                # For now, use the calculated ATM strike directly
                # In a full implementation, you'd get actual available strikes
                atm_strike = target_atm_strike
                
                # Generate AmiBroker symbol
                ami_symbol = self.generate_amibroker_symbol(underlying, expiry_date, atm_strike, option_type)
                
                # Generate Fyers symbol format (placeholder)
                fyers_symbol = f"NFO:{underlying}{expiry_date.replace('-', '')}{int(atm_strike)}{option_type}"
                
                symbol_mapping[fyers_symbol] = ami_symbol
                logger.info(f"Added {underlying} ({expiry_date}): {fyers_symbol} -> {ami_symbol}")
        
        return symbol_mapping
    
    def save_daily_atm_symbols(self, symbols_dict: Dict[str, str]) -> bool:
        """Save daily ATM symbols to file"""
        try:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            file_path = os.path.join(self.master_contract_path, f"daily_atm_symbols_{today_str}.json")
            
            # Load existing data if file exists
            existing_data = {}
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode existing file {file_path}. Overwriting.")
            
            # Update with new symbols
            existing_data.update(symbols_dict)
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=4)
            
            logger.info(f"Saved {len(symbols_dict)} ATM symbols to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving daily ATM symbols: {e}")
            return False
    
    def load_daily_atm_symbols(self) -> Dict[str, str]:
        """Load daily ATM symbols from file"""
        try:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            file_path = os.path.join(self.master_contract_path, f"daily_atm_symbols_{today_str}.json")
            
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    symbols = json.load(f)
                logger.info(f"Loaded {len(symbols)} saved ATM symbols from {file_path}")
                return symbols
            else:
                logger.info(f"No saved ATM symbols file found for today: {file_path}")
                return {}
                
        except Exception as e:
            logger.error(f"Error loading daily ATM symbols: {e}")
            return {}
    
    async def connect_to_relay_server(self) -> bool:
        """Connect to the relay server for AmiBroker communication"""
        try:
            logger.info(f"Connecting to relay server at {self.relay_uri}...")
            self.websocket = await websockets.connect(self.relay_uri, max_size=16*1024*1024)
            
            # Send role message
            await self.websocket.send("rolesend")
            logger.info("Connected to relay server and sent 'rolesend'")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to relay server: {e}")
            return False
    
    async def send_symbol_discovery_to_amibroker(self, ami_symbol: str):
        """Send symbol discovery message to AmiBroker via relay server"""
        try:
            if self.websocket and not self.websocket.closed:
                # Send a dummy bar to make AmiBroker discover the symbol
                now = datetime.datetime.now()
                dummy_bar = [{
                    "n": ami_symbol,
                    "d": int(now.strftime("%Y%m%d")),
                    "t": int(now.strftime("%H%M00")),
                    "o": 0, "h": 0, "l": 0, "c": 0, "v": 0
                }]
                
                await self.websocket.send(json.dumps(dummy_bar, separators=(',', ':')))
                logger.info(f"Sent symbol discovery for {ami_symbol}")
                
        except Exception as e:
            logger.error(f"Error sending symbol discovery for {ami_symbol}: {e}")
    
    async def send_all_symbols_to_amibroker(self):
        """Send all symbols in mapping to AmiBroker for discovery"""
        logger.info(f"Sending {len(self.symbol_mapping)} symbols to AmiBroker for discovery...")
        
        for ami_symbol in self.symbol_mapping.values():
            await self.send_symbol_discovery_to_amibroker(ami_symbol)
            # Small delay to avoid overwhelming the relay server
            await asyncio.sleep(0.1)
        
        logger.info("All symbols sent to AmiBroker for discovery")
    
    async def run_atm_selection(self) -> bool:
        """Run ATM option selection for both Nifty and BankNifty"""
        logger.info("Starting ATM option selection...")
        
        # Ensure API key is available
        if not await self.refresh_api_key():
            logger.error("No API key available")
            return False
        
        all_symbols = {}
        
        # Select Nifty ATM options
        nifty_symbols = await self.select_and_subscribe_atm_options(
            NIFTY_INDEX_SYMBOL, "NIFTY", NIFTY_STRIKE_INTERVAL
        )
        all_symbols.update(nifty_symbols)
        
        # Select BankNifty ATM options  
        banknifty_symbols = await self.select_and_subscribe_atm_options(
            BANKNIFTY_INDEX_SYMBOL, "BANKNIFTY", BANKNIFTY_STRIKE_INTERVAL
        )
        all_symbols.update(banknifty_symbols)
        
        if all_symbols:
            # Update symbol mapping
            self.symbol_mapping.update(all_symbols)
            
            # Save to daily file
            self.save_daily_atm_symbols(all_symbols)
            
            # Connect to relay server and send symbol discoveries
            if await self.connect_to_relay_server():
                await self.send_all_symbols_to_amibroker()
                logger.info(f"ATM selection complete. Added {len(all_symbols)} new symbols.")
                return True
            else:
                logger.error("Failed to connect to relay server")
                return False
        else:
            logger.warning("No new ATM symbols selected")
            return True  # Still success, just no new symbols
    
    async def initialize_complete_system(self) -> bool:
        """Initialize the complete system with all symbols"""
        logger.info("Initializing complete OpenAlgo symbol injection system...")
        
        # Ensure API key is available
        if not await self.refresh_api_key():
            logger.error("Cannot initialize without API key")
            return False
        
        # Load any saved ATM symbols for today
        saved_atm_symbols = self.load_daily_atm_symbols()
        if saved_atm_symbols:
            self.symbol_mapping.update(saved_atm_symbols)
            logger.info(f"Loaded {len(saved_atm_symbols)} saved ATM symbols")
        
        # Connect to relay server
        if not await self.connect_to_relay_server():
            logger.error("Failed to connect to relay server")
            return False
        
        # Send all symbols to AmiBroker for discovery
        await self.send_all_symbols_to_amibroker()
        
        logger.info(f"System initialized with {len(self.symbol_mapping)} total symbols")
        return True
    
    async def run_daily_scheduler(self):
        """Run daily scheduler for ATM selection"""
        logger.info("Starting daily scheduler...")
        
        # Initialize system first
        if not await self.initialize_complete_system():
            logger.error("Failed to initialize system")
            return
        
        while True:
            try:
                now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
                current_time = now.time()
                
                # Parse ATM selection time
                atm_hms = [int(x) for x in ATM_SELECTION_TIME_STR.split(':')]
                atm_run_time = datetime.time(atm_hms[0], atm_hms[1], atm_hms[2])
                
                # Check if it's time to run ATM selection
                if current_time >= atm_run_time:
                    logger.info(f"Time to run ATM selection ({current_time})")
                    await self.run_atm_selection()
                    
                    # Sleep until next day
                    tomorrow = now + datetime.timedelta(days=1)
                    next_run = tomorrow.replace(hour=atm_hms[0], minute=atm_hms[1], second=atm_hms[2], microsecond=0)
                    sleep_seconds = (next_run - now).total_seconds()
                    
                    logger.info(f"Next ATM selection at {next_run}. Sleeping {sleep_seconds} seconds.")
                    await asyncio.sleep(sleep_seconds)
                else:
                    # Sleep until ATM selection time
                    today_run = now.replace(hour=atm_hms[0], minute=atm_hms[1], second=atm_hms[2], microsecond=0)
                    sleep_seconds = (today_run - now).total_seconds()
                    
                    logger.info(f"Next ATM selection at {today_run}. Sleeping {sleep_seconds} seconds.")
                    await asyncio.sleep(max(1, sleep_seconds))
                    
            except Exception as e:
                logger.error(f"Error in daily scheduler: {e}")
                await asyncio.sleep(300)  # Sleep 5 minutes on error

async def main():
    """Main function"""
    logger.info("Starting OpenAlgo Comprehensive Symbol Injector...")
    logger.info(f"Total symbols to manage: {len(COMPLETE_SYMBOL_MAPPING)}")
    
    # Create directories if they don't exist
    os.makedirs(MASTER_CONTRACT_PATH, exist_ok=True)
    os.makedirs(FYERS_LOG_PATH, exist_ok=True)
    
    # Create injector instance
    injector = OpenAlgoComprehensiveInjector()
    
    try:
        # Run the daily scheduler
        await injector.run_daily_scheduler()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
    finally:
        logger.info("OpenAlgo Comprehensive Symbol Injector stopped")

if __name__ == "__main__":
    asyncio.run(main())