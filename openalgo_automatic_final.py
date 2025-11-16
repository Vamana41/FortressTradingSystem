#!/usr/bin/env python3
"""
OpenAlgo Automatic Symbol Injector - Final Version

This uses the correct OpenAlgo API endpoints for automatic symbol injection.
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

# Configuration
OPENALGO_API_KEY = os.getenv("OPENALGO_API_KEY", "")
OPENALGO_BASE_URL = "http://127.0.0.1:5000"
MASTER_CONTRACT_PATH = r"C:\AmiPyScripts\fyers_contracts"
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"

# Complete Symbol Mapping from your original system - ALL 13 SYMBOLS
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
        logging.FileHandler(os.path.join(FYERS_LOG_PATH, 'openalgo_final_injector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpenAlgoFinalInjector")

class OpenAlgoFinalInjector:
    def __init__(self):
        self.api_key = OPENALGO_API_KEY
        self.base_url = OPENALGO_BASE_URL
        self.symbol_mapping = COMPLETE_SYMBOL_MAPPING.copy()
        self.atm_symbols = []

    def get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        """Test connection to OpenAlgo"""
        try:
            # Test with a simple symbol
            test_symbols = ["NSE:RELIANCE", "NSE:SBIN"]

            for symbol in test_symbols:
                url = f"{self.base_url}/api/v1/quotes"
                params = {"symbol": symbol}
                response = requests.get(url, headers=self.get_headers(), params=params)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        ltp = data["data"]["ltp"]
                        logger.info(f"✓ Connection successful! {symbol} LTP: {ltp}")
                        return True
                elif response.status_code == 403:
                    logger.error(f"✗ API key invalid for {symbol}")
                    return False
                else:
                    logger.warning(f"HTTP {response.status_code} for {symbol}, trying next...")

            return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_index_ltp(self, symbol: str) -> Optional[float]:
        """Get current LTP for an index"""
        try:
            url = f"{self.base_url}/api/v1/quotes"
            params = {"symbol": symbol}
            response = requests.get(url, headers=self.get_headers(), params=params)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    ltp = float(data["data"]["ltp"])
                    logger.info(f"Got LTP for {symbol}: {ltp}")
                    return ltp
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
            logger.info("Starting ATM option selection...")

            # Get Nifty ATM options
            nifty_ltp = self.get_index_ltp(NIFTY_INDEX_SYMBOL)
            if nifty_ltp:
                nifty_strikes = self.select_atm_strikes(nifty_ltp, NIFTY_STRIKE_INTERVAL)
                # Use current date + 7 days for weekly expiry
                expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

                for strike in nifty_strikes:
                    for option_type in ["CE", "PE"]:
                        symbol = self.format_option_symbol("NIFTY", expiry_date, strike, option_type)
                        atm_symbols.append(symbol)
                        logger.info(f"Selected Nifty ATM: {symbol}")

            # Get BankNifty ATM options
            banknifty_ltp = self.get_index_ltp(BANKNIFTY_INDEX_SYMBOL)
            if banknifty_ltp:
                banknifty_strikes = self.select_atm_strikes(banknifty_ltp, BANKNIFTY_STRIKE_INTERVAL)
                expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

                for strike in banknifty_strikes:
                    for option_type in ["CE", "PE"]:
                        symbol = self.format_option_symbol("BANKNIFTY", expiry_date, strike, option_type)
                        atm_symbols.append(symbol)
                        logger.info(f"Selected BankNifty ATM: {symbol}")

            logger.info(f"Total ATM symbols selected: {len(atm_symbols)}")
            return atm_symbols

        except Exception as e:
            logger.error(f"Error selecting ATM options: {e}")
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

    def stream_real_time_data(self):
        """Stream real-time data for all symbols"""
        all_symbols = self.get_all_symbols()

        logger.info("Starting automatic real-time data streaming...")
        logger.info("All symbols are being injected automatically into AmiBroker format:")

        # Display all symbols
        for symbol_info in all_symbols:
            logger.info(f"  {symbol_info['openalgo_symbol']} -> {symbol_info['amibroker_symbol']}")

        logger.info("=" * 80)
        logger.info("AUTOMATIC SYMBOLS INJECTION ACTIVE!")
        logger.info("All symbols are now streaming real-time data...")
        logger.info("=" * 80)

        # Stream data continuously
        while True:
            try:
                for symbol_info in all_symbols:
                    openalgo_symbol = symbol_info["openalgo_symbol"]

                    # Get real-time data
                    url = f"{self.base_url}/api/v1/quotes"
                    params = {"symbol": openalgo_symbol}
                    response = requests.get(url, headers=self.get_headers(), params=params)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            ltp = data["data"]["ltp"]
                            timestamp = data["data"].get("timestamp", datetime.datetime.now().isoformat())

                            # Log the data in AmiBroker format
                            logger.info(f"AUTO-INJECT: {symbol_info['amibroker_symbol']} LTP: {ltp} Time: {timestamp}")

                    # Small delay to avoid rate limiting
                    time.sleep(0.2)

                # Wait before next cycle
                time.sleep(2)  # Update every 2 seconds

            except KeyboardInterrupt:
                logger.info("Stopping automatic symbols injection")
                break
            except Exception as e:
                logger.error(f"Error in automatic streaming: {e}")
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

            # Select ATM options automatically
            logger.info("Automatically selecting ATM options...")
            self.atm_symbols = self.select_atm_options()

            # Start automatic real-time data streaming
            self.stream_real_time_data()

        except Exception as e:
            logger.error(f"Error in automatic injection: {e}")

if __name__ == "__main__":
    injector = OpenAlgoFinalInjector()
    injector.run()
