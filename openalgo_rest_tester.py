#!/usr/bin/env python3
"""
OpenAlgo REST-Only Symbol Injector - Verifies symbols work via REST API first
This checks if symbols are accessible before attempting WebSocket connection
"""

import requests
import json
import logging
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OpenAlgoRESTInjector")

# Configuration
OPENALGO_API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
OPENALGO_BASE_URL = "http://127.0.0.1:5000/api/v1"

# All symbols from your original system
ALL_SYMBOLS = [
    # NSE Cash
    {"symbol": "SBIN", "exchange": "NSE"},
    {"symbol": "RELIANCE", "exchange": "NSE"},
    {"symbol": "TCS", "exchange": "NSE"},
    {"symbol": "INFY", "exchange": "NSE"},
    {"symbol": "ITC", "exchange": "NSE"},

    # Nifty and BankNifty for ATM options
    {"symbol": "NIFTY", "exchange": "NSE"},
    {"symbol": "BANKNIFTY", "exchange": "NSE"},

    # MCX Commodities
    {"symbol": "CRUDEOIL", "exchange": "MCX"},
    {"symbol": "GOLD", "exchange": "MCX"},
    {"symbol": "SILVER", "exchange": "MCX"},
    {"symbol": "COPPER", "exchange": "MCX"},
    {"symbol": "NATURALGAS", "exchange": "MCX"}
]

def test_symbol_via_rest(symbol_info: Dict[str, str]) -> bool:
    """Test if a symbol works via REST API"""
    symbol = symbol_info["symbol"]
    exchange = symbol_info["exchange"]

    try:
        url = f"{OPENALGO_BASE_URL}/quotes"
        payload = {
            "apikey": OPENALGO_API_KEY,
            "exchange": exchange,
            "symbol": symbol
        }

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                quote_data = data.get("data", {})
                ltp = quote_data.get("ltp", 0)
                ami_format = f"{symbol}-{exchange}"
                logger.info(f"✅ {ami_format}: LTP {ltp}")
                return True
            else:
                logger.warning(f"⚠️  API error for {symbol}: {data}")
                return False
        else:
            logger.error(f"❌ HTTP error for {symbol}: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to test {symbol}: {e}")
        return False

def main():
    """Main function - test all symbols via REST API"""
    logger.info("=" * 70)
    logger.info("🔍 OPENALGO REST SYMBOL TESTER")
    logger.info("=" * 70)
    logger.info("Testing all symbols via OpenAlgo REST API")
    logger.info("This will show which symbols are actually working")
    logger.info("=" * 70)

    working_symbols = []
    failed_symbols = []

    logger.info(f"Testing {len(ALL_SYMBOLS)} symbols...")
    logger.info("")

    for symbol_info in ALL_SYMBOLS:
        if test_symbol_via_rest(symbol_info):
            working_symbols.append(symbol_info)
        else:
            failed_symbols.append(symbol_info)

        # Small delay to avoid overwhelming the API
        import time
        time.sleep(0.5)

    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 TEST RESULTS:")
    logger.info("=" * 70)
    logger.info(f"✅ Working symbols: {len(working_symbols)}")
    logger.info(f"❌ Failed symbols: {len(failed_symbols)}")
    logger.info("")

    if working_symbols:
        logger.info("🎯 WORKING SYMBOLS (these should appear in AmiBroker):")
        for symbol_info in working_symbols:
            ami_format = f"{symbol_info['symbol']}-{symbol_info['exchange']}"
            logger.info(f"   ✓ {ami_format}")

    if failed_symbols:
        logger.info("")
        logger.info("⚠️  FAILED SYMBOLS:")
        for symbol_info in failed_symbols:
            ami_format = f"{symbol_info['symbol']}-{symbol_info['exchange']}"
            logger.info(f"   ✗ {ami_format}")

    logger.info("")
    logger.info("=" * 70)
    logger.info("💡 NEXT STEPS:")
    logger.info("=" * 70)
    logger.info("1. Check if these working symbols appear in AmiBroker")
    logger.info("2. If they do, then OpenAlgo is working correctly")
    logger.info("3. If they don't, then we need to check the AmiBroker plugin connection")
    logger.info("4. The WebSocket issue might be separate from the basic symbol injection")

if __name__ == "__main__":
    main()
