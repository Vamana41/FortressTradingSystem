#!/usr/bin/env python3
"""
OpenAlgo Symbol Injector - Integrates OpenAlgo data with automatic symbol injection

This script bridges OpenAlgo's data access with your existing automatic symbol injection
system for AmiBroker. It uses OpenAlgo's API for data while maintaining your
automatic ATM option selection and relay server communication.
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
load_dotenv()

# Configuration
OPENALGO_API_KEY = os.getenv("OPENALGO_API_KEY", "")  # Will be set from Fortress API key manager
OPENALGO_BASE_URL = "http://127.0.0.1:5000"  # OpenAlgo runs on port 5000
RELAY_SERVER_URI = "ws://localhost:10102"  # Your existing relay server
MASTER_CONTRACT_PATH = r"C:\AmiPyScripts\fyers_contracts"  # Your existing path
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"  # Your existing log path

# ATM Selection Settings (from your existing system)
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
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_symbol_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoSymbolInjector")

class OpenAlgoSymbolInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.relay_uri = RELAY_SERVER_URI
        self.master_contract_path = MASTER_CONTRACT_PATH
        self.websocket = None
        self.symbol_mapping = {}  # Will be populated with ATM symbols
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
    
    async def get_api_key_from_fortress(self) -> bool:
        """Get API key from Fortress API key manager"""
        try:
            # Try to read from Fortress API key manager location
            fortress_key_file = r"C:\Users\Admin\.fortress\api_keys.enc"
            if os.path.exists(fortress_key_file):
                # For now, we'll use a placeholder - in production, this would decrypt the key
                logger.info("Found Fortress API key file, using provided API key")
                return True
            else:
                logger.warning("Fortress API key file not found, using environment variable")
                return bool(self.api_key)
        except Exception as e:
            logger.error(f"Error accessing Fortress API key: {e}")
            return bool(self.api_key)
    
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
            else:
                logger.error(f"HTTP {response.status_code} error getting quotes for {index_symbol}")
                logger.error(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting LTP for {index_symbol}: {e}")
        
        return None
    
    async def get_option_chain(self, underlying_symbol: str) -> Optional[Dict]:
        """Get option chain data from OpenAlgo"""
        try:
            # Parse symbol and exchange
            if ":" in underlying_symbol:
                exchange, symbol = underlying_symbol.split(":", 1)
            else:
                exchange = "NSE"
                symbol = underlying_symbol
            
            # Get expiry dates first
            url = f"{self.base_url}/api/v1/expiry"
            payload = {
                "apikey": self.api_key,
                "symbol": symbol,
                "exchange": exchange,
                "instrumenttype": "OPTIDX"
            }
            
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data"):
                    logger.info(f"Got expiry dates for {underlying_symbol}")
                    
                    # For now, return a mock option chain structure
                    # In a real implementation, you'd get the actual option chain
                    expiry_dates = data.get("data", [])
                    
                    # Mock option chain data structure
                    option_chain = {
                        "expiryData": [{"date": expiry} for expiry in expiry_dates[:2]],
                        "optionsChain": []
                    }
                    
                    # Add some mock strikes based on typical values
                    if underlying_symbol == "NSE:NIFTY50-INDEX":
                        base_strike = 19500
                        strikes = [base_strike - 200, base_strike - 100, base_strike, base_strike + 100, base_strike + 200]
                    elif underlying_symbol == "NSE:NIFTYBANK-INDEX":
                        base_strike = 44000
                        strikes = [base_strike - 400, base_strike - 200, base_strike, base_strike + 200, base_strike + 400]
                    else:
                        strikes = [10000, 10100, 10200, 10300, 10400]
                    
                    for strike in strikes:
                        option_chain["optionsChain"].append({"strike_price": strike})
                    
                    return option_chain
                else:
                    logger.error(f"Expiry request failed for {underlying_symbol}: {data.get('message', 'Unknown error')}")
            else:
                logger.error(f"HTTP {response.status_code} error getting expiry for {underlying_symbol}")
                logger.error(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting option chain for {underlying_symbol}: {e}")
        
        return None
    
    def calculate_atm_strike(self, ltp: float, strike_interval: int) -> int:
        """Calculate ATM strike price"""
        return round(ltp / strike_interval) * strike_interval
    
    def get_expiries_to_process(self, option_chain_data: Dict) -> List[Tuple[datetime.date, str]]:
        """Get sorted list of valid expiries to process"""
        expiries = []
        
        if 'expiryData' in option_chain_data:
            today = datetime.date.today()
            
            for expiry_info in option_chain_data['expiryData']:
                expiry_date_str = expiry_info.get('date')
                if expiry_date_str:
                    try:
                        expiry_date = datetime.datetime.strptime(expiry_date_str, "%d-%m-%Y").date()
                        if expiry_date >= today:
                            expiries.append((expiry_date, expiry_date_str))
                    except ValueError:
                        logger.warning(f"Invalid expiry date format: {expiry_date_str}")
            
            # Sort by date and take first two
            expiries.sort(key=lambda x: x[0])
            
        return expiries[:2]  # Return nearest and next expiry
    
    def get_closest_strike_from_chain(self, option_chain_data: Dict, target_strike: int) -> Optional[int]:
        """Get the closest available strike from option chain"""
        closest_strike = None
        min_diff = float('inf')
        
        if 'optionsChain' in option_chain_data:
            for entry in option_chain_data['optionsChain']:
                strike = entry.get('strike_price')
                if strike is not None:
                    diff = abs(strike - target_strike)
                    if diff < min_diff:
                        min_diff = diff
                        closest_strike = strike
        
        return closest_strike
    
    def generate_amibroker_symbol(self, underlying: str, expiry_date: datetime.date, 
                                 strike: int, option_type: str) -> str:
        """Generate AmiBroker symbol format"""
        ami_date = expiry_date.strftime("%d%b%y").upper()
        return f"{underlying}{ami_date}{int(strike)}{option_type}"
    
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
        
        # Get option chain
        option_chain_data = await self.get_option_chain(index_symbol)
        if not option_chain_data:
            logger.error(f"Failed to get option chain for {index_symbol}")
            return {}
        
        # Get closest available strike
        actual_atm_strike = self.get_closest_strike_from_chain(option_chain_data, target_atm_strike)
        if actual_atm_strike is None:
            logger.error(f"Could not find ATM strike near {target_atm_strike}")
            return {}
        
        logger.info(f"Actual ATM strike for {underlying}: {actual_atm_strike}")
        
        # Get expiries to process
        expiries_to_process = self.get_expiries_to_process(option_chain_data)
        if not expiries_to_process:
            logger.error(f"No valid expiries found for {underlying}")
            return {}
        
        logger.info(f"Expiries to process for {underlying}: {[d[1] for d in expiries_to_process]}")
        
        # Generate symbol mappings
        symbol_mapping = {}
        
        for expiry_date, expiry_date_str in expiries_to_process:
            for option_type in ["CE", "PE"]:
                # Generate AmiBroker symbol
                ami_symbol = self.generate_amibroker_symbol(underlying, expiry_date, actual_atm_strike, option_type)
                
                # For now, we'll use a placeholder Fyers symbol format
                # In a real implementation, you'd map this to actual broker symbols
                fyers_symbol = f"NFO:{underlying}{expiry_date.strftime('%y%b').upper()}{int(actual_atm_strike)}{option_type}"
                
                symbol_mapping[fyers_symbol] = ami_symbol
                logger.info(f"Added {underlying} ({expiry_date_str}): {fyers_symbol} -> {ami_symbol}")
        
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
    
    async def connect_to_relay_server(self):
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
    
    async def run_atm_selection(self):
        """Run ATM option selection for both Nifty and BankNifty"""
        logger.info("Starting ATM option selection...")
        
        # Ensure API key is available
        if not await self.get_api_key_from_fortress():
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
                for ami_symbol in all_symbols.values():
                    await self.send_symbol_discovery_to_amibroker(ami_symbol)
                
                logger.info(f"ATM selection complete. Added {len(all_symbols)} symbols.")
                return True
            else:
                logger.error("Failed to connect to relay server")
                return False
        else:
            logger.warning("No symbols selected")
            return False
    
    async def run_daily_scheduler(self):
        """Run daily scheduler for ATM selection"""
        logger.info("Starting daily scheduler...")
        
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
    logger.info("Starting OpenAlgo Symbol Injector...")
    
    # Create directories if they don't exist
    os.makedirs(MASTER_CONTRACT_PATH, exist_ok=True)
    os.makedirs(FYERS_LOG_PATH, exist_ok=True)
    
    # Create injector instance
    injector = OpenAlgoSymbolInjector()
    
    try:
        # Run the daily scheduler
        await injector.run_daily_scheduler()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
    finally:
        logger.info("OpenAlgo Symbol Injector stopped")

if __name__ == "__main__":
    asyncio.run(main())