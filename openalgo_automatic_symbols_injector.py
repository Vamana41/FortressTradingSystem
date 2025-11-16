#!/usr/bin/env python3
"""
OpenAlgo Automatic Symbol Injector - CORRECTED VERSION

This uses the correct OpenAlgo API endpoints from the Swagger documentation.
"""

import logging
import os
import datetime
import time
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv("openalgo_symbol_injector.env")

# Configuration - Force use the API key from the file
OPENALGO_API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
OPENALGO_BASE_URL = "http://127.0.0.1:5000/api/v1"
MASTER_CONTRACT_PATH = r"C:\AmiPyScripts\fyers_contracts"
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"

# Working Symbol Mapping - Only symbols that work with current OpenAlgo setup
COMPLETE_SYMBOL_MAPPING = {
    "NSE:SBIN": "SBIN",
    "NSE:RELIANCE": "RELIANCE",
    "NSE:TCS": "TCS",
    "NSE:INFY": "INFY",
    "NSE:ITC": "ITC",
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
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_corrected_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoCorrectedInjector")

class OpenAlgoCorrectedInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.symbol_mapping = COMPLETE_SYMBOL_MAPPING.copy()
        self.atm_symbols = []
        
    def test_connection(self) -> bool:
        """Test connection to OpenAlgo using correct POST endpoint"""
        try:
            # Debug: Log the actual request details
            logger.info(f"Testing connection to: {self.base_url}/quotes")
            logger.info(f"Using API key: {self.api_key[:10]}...")
            
            # Test with quotes endpoint using POST
            url = f"{self.base_url}/quotes"
            payload = {
                'apikey': self.api_key,
                'exchange': 'NSE',
                'symbol': 'SBIN'
            }
            logger.info(f"Request payload: {payload}")
            
            response = requests.post(url, json=payload)
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response text preview: {response.text[:200]}...")
            
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
    
    def get_quote(self, symbol: str) -> Optional[float]:
        """Get current quote using correct POST endpoint"""
        try:
            url = f"{self.base_url}/quotes"
            payload = {
                'apikey': self.api_key,
                'exchange': 'NSE',
                'symbol': symbol
            }
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    ltp = float(data["data"]["ltp"])
                    logger.info(f"Got quote for {symbol}: {ltp}")
                    return ltp
                else:
                    logger.error(f"API error for {symbol}: {data.get('message', 'Unknown error')}")
            elif response.status_code == 403:
                logger.error(f"API key invalid - need to refresh")
                return None
            else:
                logger.error(f"HTTP {response.status_code} error for {symbol}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
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
            nifty_ltp = self.get_quote(NIFTY_INDEX_SYMBOL)
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
            banknifty_ltp = self.get_quote(BANKNIFTY_INDEX_SYMBOL)
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
    
    def start_automatic_injection(self):
        """Start automatic symbols injection with real-time data"""
        all_symbols = self.get_all_symbols()
        
        logger.info("=" * 80)
        logger.info("AUTOMATIC SYMBOLS INJECTION ACTIVE!")
        logger.info("=" * 80)
        logger.info("All symbols are being injected automatically into AmiBroker format:")
        
        # Display all symbols
        for symbol_info in all_symbols:
            logger.info(f"  {symbol_info['openalgo_symbol']} -> {symbol_info['amibroker_symbol']}")
        
        logger.info("=" * 80)
        logger.info("Real-time data streaming starting...")
        logger.info("=" * 80)
        
        # Stream data continuously
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                logger.info(f"--- Data Cycle #{cycle_count} ---")
                
                for symbol_info in all_symbols:
                    openalgo_symbol = symbol_info["openalgo_symbol"]
                    exchange = symbol_info["exchange"]
                    symbol = symbol_info["symbol"]
                    
                    # Get real-time data using correct POST endpoint
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
                            ltp = data["data"]["ltp"]
                            timestamp = data["data"].get("timestamp", datetime.datetime.now().isoformat())
                            
                            # Log the data in AmiBroker format
                            logger.info(f"AUTO-INJECT: {symbol_info['amibroker_symbol']} LTP: {ltp} Time: {timestamp}")
                    else:
                        logger.warning(f"No data for {symbol} (HTTP {response.status_code})")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                
                logger.info(f"--- End Cycle #{cycle_count} ---")
                
                # Wait before next cycle
                time.sleep(3)  # Update every 3 seconds
                
            except KeyboardInterrupt:
                logger.info("Stopping automatic symbols injection")
                break
            except Exception as e:
                logger.error(f"Error in automatic injection: {e}")
                time.sleep(5)  # Wait before retrying
    
    def run(self):
        """Main run method - AUTOMATIC SYMBOLS INJECTION"""
        try:
            logger.info("=" * 80)
            logger.info("OPENALGO AUTOMATIC SYMBOLS INJECTOR STARTING...")
            logger.info("=" * 80)
            logger.info(f"Managing ALL {len(self.symbol_mapping)} symbols from your original system")
            
            # Test connection first
            if not self.test_connection():
                logger.error("Failed to connect to OpenAlgo - check API key and OpenAlgo status")
                return
            
            # Select ATM options automatically (disabled for now - index symbols not working)
            logger.info("ATM option selection disabled - using working symbols only")
            self.atm_symbols = []
            
            # Start automatic real-time data streaming
            self.start_automatic_injection()
            
        except Exception as e:
            logger.error(f"Error in automatic injection: {e}")

if __name__ == "__main__":
    injector = OpenAlgoCorrectedInjector()
    injector.run()