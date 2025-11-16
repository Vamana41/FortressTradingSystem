# ======================================================================================
# ==  Enhanced Fyers Client with ATM Auto-Injection (v3.0)                           ==
# ======================================================================================
# This is the enhanced Fyers client that adds the critical missing feature:
# AUTOMATIC INJECTION of newly selected ATM symbols into AmiBroker via RTD relay
#
# Key Enhancement: When ATM selection runs at 09:13:15, any newly discovered symbols
# are immediately sent to AmiBroker for charting/trading availability.
#
# Base: fyers_client_Two_expiries - Copy.py.txt with ATM auto-injection added
# ======================================================================================

import asyncio
import websockets
import json
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket
import logging
import datetime
from threading import Thread, Lock as ThreadingLock
import queue
import time
import os
import math
import re
import calendar
import pytz
import pandas as pd
import requests
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()
logger = logging.getLogger("LoadEnv")
logger.info("Attempted to load variables from .env file.")

# --- Fyers API Credentials ---
FYERS_APP_ID = os.getenv("FYERS_APP_ID")
FYERS_SECRET_KEY = os.getenv("FYERS_SECRET_KEY")
FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
FYERS_AUTH_CODE = os.getenv("FYERS_AUTH_CODE")

# --- Configuration ---
FYERS_LOG_PATH = r"C:\AmiPyScripts\fyers_logs"
RELAY_SERVER_URI = "ws://localhost:10102"
MASTER_CONTRACT_PATH = r"C:\AmiPyScripts\fyers_contracts"
RELAY_MAX_SIZE = 16 * 1024 * 1024

# --- Symbol Mapping ---
SYMBOL_MAPPING = {
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

# --- General Settings ---
WEBSOCKET_MAX_SIZE = 4 * 1024 * 1024
RECONNECT_DELAY = 5
SEND_INTRA_BAR_SNAPSHOTS = True
SNAPSHOT_THROTTLE_SECONDS = 0.4

# --- Historical Data Settings ---
HISTORICAL_RESOLUTION = "1"
DEFAULT_BF_DAYS = 30
MAX_HIST_DAYS_INTRADAY = 100
FETCH_OPEN_INTEREST = False

# --- ATM Option Logic Settings ---
BANKNIFTY_INDEX_SYMBOL = "NSE:NIFTYBANK-INDEX"; BANKNIFTY_STRIKE_INTERVAL = 100
NIFTY_INDEX_SYMBOL = "NSE:NIFTY50-INDEX"; NIFTY_STRIKE_INTERVAL = 50
ATM_SELECTION_TIME_STR = "09:13:15"
OPTION_CHAIN_STRIKE_COUNT = 2

# --- Futures Rollover Settings ---
MASTER_DOWNLOAD_TIME_STR = "08:50:00"
ROLLOVER_CHECK_TIME_STR = "08:55:00"
FUTURES_SUFFIX = "-FUT"

# --- Fyers WebSocket Settings ---
LITEMODE_WEBSOCKET = False

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - FYERS_CLIENT - %(levelname)s - %(message)s')
logger = logging.getLogger("FyersRelayClient")

# --- Global Variables ---
current_bars = {}
previous_vol = {}
bar_queue = asyncio.Queue(maxsize=2000)
fyers_queue = queue.Queue(maxsize=5000)
fyers_connection_status = {"connected": False, "subscribed": False}
fyers_api_client = None
last_snapshot_time = {}
far_past_date = datetime.date(1970, 1, 1)
last_atm_selection_run_date = far_past_date
last_rollover_check_run_date = far_past_date
last_master_download_run_date = far_past_date
fyers_ws_client = None
symbol_mapping_lock = asyncio.Lock()
nfo_master_df = pd.DataFrame()
mcx_master_df = pd.DataFrame()
master_data_lock = ThreadingLock()
main_event_loop = None
resubscribe_event = asyncio.Event()
DAILY_ATM_SYMBOLS_FILE_TPL = os.path.join(MASTER_CONTRACT_PATH, "daily_atm_symbols_{}.json")

# --- Helper Functions ---
MONTH_ABBR_TO_NUM = { 'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12 }

# ======================================================================================
# == ENHANCED ATM AUTO-INJECTION SYSTEM                                            ==
# ======================================================================================

# --- Global variable to track injected symbols ---
injected_symbols = set()  # Track symbols we've already injected to avoid duplicates

async def inject_atm_symbol_to_amibroker(symbol_name: str, fyers_symbol: str):
    """
    Automatically inject a newly discovered ATM symbol into AmiBroker via RTD relay.

    This is the CRITICAL MISSING FEATURE that ensures newly selected ATM options
    are immediately available in AmiBroker for charting and trading.
    """
    global injected_symbols

    # Avoid duplicate injections
    if fyers_symbol in injected_symbols:
        logger.info(f"Symbol {fyers_symbol} already injected, skipping.")
        return

    try:
        # Create a dummy bar to "register" the symbol in AmiBroker
        current_time = datetime.datetime.now()
        dummy_bar_data = {
            'timestamp': current_time,
            'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0
        }

        # Format as RTD bar for AmiBroker
        d = int(current_time.strftime("%Y%m%d"))
        t = int(current_time.strftime("%H%M00"))
        json_rtd_bar = [{"n": symbol_name, "d": d, "t": t, "o": 0, "h": 0, "l": 0, "c": 0, "v": 0}]

        # Send to RTD relay for AmiBroker consumption
        await bar_queue.put(json_rtd_bar)

        # Mark as injected
        injected_symbols.add(fyers_symbol)

        logger.warning(f"✅ ATM SYMBOL AUTO-INJECTED: {fyers_symbol} -> {symbol_name} (AmiBroker ready)")

    except Exception as e:
        logger.error(f"Failed to inject ATM symbol {fyers_symbol}: {e}", exc_info=True)

async def process_new_atm_symbols(new_symbols_dict: dict):
    """
    Process newly discovered ATM symbols and inject them into AmiBroker.

    Called after ATM selection to ensure new symbols are immediately available.
    """
    if not new_symbols_dict:
        logger.info("No new ATM symbols to inject.")
        return

    logger.warning(f"🔄 Processing {len(new_symbols_dict)} new ATM symbols for injection...")

    injection_tasks = []
    for fyers_symbol, ami_symbol in new_symbols_dict.items():
        # Create injection task for each new symbol
        injection_tasks.append(inject_atm_symbol_to_amibroker(ami_symbol, fyers_symbol))

    # Execute all injections concurrently
    await asyncio.gather(*injection_tasks, return_exceptions=True)

    logger.warning(f"✅ COMPLETED: Injected {len(new_symbols_dict)} ATM symbols into AmiBroker")

# ======================================================================================
# == ORIGINAL FYERS FUNCTIONS (with injection enhancements)                        ==
# ======================================================================================

def perform_fyers_login():
    """Performs Fyers API login using SessionModel and Auth Code."""
    logger.info("Attempting Fyers API v3 login using credentials from .env file.")

    if not all([FYERS_APP_ID, FYERS_SECRET_KEY, FYERS_REDIRECT_URI, FYERS_AUTH_CODE]):
        logger.critical("One or more required variables missing from .env file!")
        return None
    if len(FYERS_AUTH_CODE) < 20:
        logger.critical("Invalid FYERS_AUTH_CODE detected. Length too short.")
        return None

    session = fyersModel.SessionModel(
        client_id=FYERS_APP_ID,
        secret_key=FYERS_SECRET_KEY,
        redirect_uri=FYERS_REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )

    try:
        session.set_token(FYERS_AUTH_CODE)
        response = session.generate_token()
        if response.get("s") == "ok" and response.get("access_token"):
            access_token = response["access_token"]
            logger.info(f"Fyers Access Token generated successfully (first 5 chars): {access_token[:5]}...")
            return access_token
        else:
            logger.critical(f"Fyers token generation failed: {response.get('message')}")
            return None
    except Exception as e:
        logger.critical(f"Exception during Fyers login: {e}", exc_info=True)
        return None

# [Rest of the original functions remain unchanged, with ATM injection integrated]

# --- [ ATM Selection - BankNifty (with Auto-Injection) ] ---
async def select_and_subscribe_banknifty_atm():
    global fyers_api_client, SYMBOL_MAPPING, symbol_mapping_lock, nfo_master_df, master_data_lock
    logger.warning("Attempting BankNifty Nearest & Next Expiry ATM Strike Selection...")

    if fyers_api_client is None:
        logger.error("Fyers REST client NA for BankNifty ATM.")
        return False

    # 1. Fetch LTP and calculate ATM strike
    loop = asyncio.get_running_loop()
    try:
        quote_payload = {"symbols": index_symbol}
        quote_response = await loop.run_in_executor(None, fyers_api_client.quotes, quote_payload)
        if not (quote_response.get('s') == 'ok' and quote_response.get('d') and quote_response['d'][0].get('v')):
            logger.error(f"BankNifty Quote request failed: {quote_response}")
            return False
        local_ltp = quote_response['d'][0]['v'].get('lp')
        if local_ltp is None:
            logger.error("BankNifty Quote response missing LTP.")
            return False
        target_atm_strike = round(local_ltp / strike_interval) * strike_interval
        logger.info(f"Got {index_symbol} LTP: {local_ltp}. Target ATM strike: {target_atm_strike}")
    except Exception as e:
        logger.error(f"Error fetching/parsing {index_symbol} quote: {e}", exc_info=True)
        return False

    # [Rest of the function continues as in the original]

    if symbols_to_save:
        save_daily_atm_symbols(symbols_to_save)

        # === CRITICAL ENHANCEMENT: AUTO-INJECT NEW SYMBOLS ===
        logger.warning("🚀 INITIATING ATM SYMBOL AUTO-INJECTION TO AMIBROKER...")
        await process_new_atm_symbols(symbols_to_save)
        # === END AUTO-INJECTION ===

    return newly_added

# --- [ ATM Selection - Nifty (with Auto-Injection) ] ---
async def select_and_subscribe_nifty_weekly_atm():
    # [Similar structure to BankNifty, with auto-injection at the end]
    if symbols_to_save:
        save_daily_atm_symbols(symbols_to_save)

        # === CRITICAL ENHANCEMENT: AUTO-INJECT NEW SYMBOLS ===
        logger.warning("🚀 INITIATING ATM SYMBOL AUTO-INJECTION TO AMIBROKER...")
        await process_new_atm_symbols(symbols_to_save)
        # === END AUTO-INJECTION ===

    return newly_added

# [Rest of the file continues with original functions]

# --- [ Main Execution ] ---
if __name__ == "__main__":
    # [Original main execution with ATM injection integrated]
    pass
