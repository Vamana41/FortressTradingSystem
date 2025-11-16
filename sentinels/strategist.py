# ======================================================================================
# ==  The Strategist - Fortress Sentinel Brain (v3.0 - Nexus)                         ==
# ======================================================================================
# This is the "pure brain" of the Sentinel Architecture. It has NO API keys.
# 1. It subscribes to "events.signal.amibroker" from the Watcher.
# 2. It makes HTTP requests to the Conductor (app.py) for margin/instrument data.
# 3. It publishes a "request.execute_order" event for the Conductor to execute.
# ======================================================================================

import zmq
import json
import logging
import os
import time
import math
import requests # We use requests to talk to our Conductor
from typing import Dict, Any, Optional

# --- Configuration & Path Setup ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Prefer the package-local `sentinels/logs` directory. Allow overriding via env var for flexibility.
DEFAULT_LOGS = os.path.join(os.path.dirname(__file__), "logs")
LOGS_DIR = os.environ.get("SENTINEL_LOG_DIR", DEFAULT_LOGS)
os.makedirs(LOGS_DIR, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    filename=os.path.join(LOGS_DIR, 'strategist.log'),
                    filemode='a',
                    format='%(asctime)s - STRATEGIST - %(levelname)s - %(message)s')
logger = logging.getLogger("Strategist")

# --- ZMQ Configuration ---
ZMQ_SUB_URL = "tcp://127.0.0.1:5556" # The port components SUBSCRIBE to
ZMQ_PUB_URL = "tcp://127.0.0.1:5555" # The port components PUBLISH to

# --- Conductor (OpenAlgo) API Endpoints ---
# We are querying our *own* app.py
CONDUCTOR_BASE_URL = "http://127.0.0.1" # Default OpenAlgo port is 80
CONDUCTOR_MARGIN_API = f"{CONDUCTOR_BASE_URL}/api/v1/margin"
CONDUCTOR_INSTRUMENTS_API = f"{CONDUCTOR_BASE_URL}/api/v1/instruments"

# --- Trading Rules ---
CAPITAL_ALLOCATION_PERCENT: float = 0.50

def get_instrument_data(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetches instrument data (like lot size) from the Conductor's API."""
    try:
        # We assume the OpenAlgo API key is not needed for local requests
        # If it is, headers would be added here.
        params = {"symbol": symbol}
        response = requests.get(CONDUCTOR_INSTRUMENTS_API, params=params, timeout=5)
        response.raise_for_status() # Raise error for 4xx/5xx
        data = response.json()
        
        if data.get("success") and data.get("data"):
            # Assuming data is a list of instruments
            for inst in data["data"]:
                if inst.get("symbol") == symbol:
                    logger.info(f"Instrument data found for {symbol}")
                    return inst
        logger.warning(f"Could not find instrument data for {symbol} in API response.")
        return None
    except Exception as e:
        logger.error(f"Error fetching instrument data for {symbol}: {e}", exc_info=True)
        return None

def get_margin_requirements(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Performs the Margin Inquisition via the Conductor's API."""
    try:
        payload = {"orders": [order]}
        response = requests.post(CONDUCTOR_MARGIN_API, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success") and data.get("data"):
            logger.info(f"Margin data received: {data['data']}")
            return data['data']
        
        logger.error(f"Margin API call failed: {data.get('error')}")
        return None
    except Exception as e:
        logger.error(f"Error during Margin Inquisition: {e}", exc_info=True)
        return None

def handle_signal_event(signal: Dict[str, Any], pub_socket: zmq.Socket) -> None:
    """The core logic: receive signal, check margin, publish order."""
    
    symbol = signal.get("symbol")
    action = signal.get("action")
    price = signal.get("price")
    
    if not all([symbol, action, price]):
        logger.warning(f"Malformed signal received and ignored: {signal}")
        return

    logger.info(f"Strategist processing signal: {action} {symbol} @ {price}")
    
    # --- Get Lot Size (from new Instruments API) ---
    inst_data = get_instrument_data(symbol)
    if not inst_data or "lot_size" not in inst_data:
        logger.error(f"Could not get lot size for {symbol}. Aborting trade.")
        return
    lot_size = inst_data["lot_size"]

    # --- The Margin Inquisition (via HTTP Request) ---
    proposed_order = {
        "symbol": symbol,
        "side": 1 if action == "BUY" else -1,
        "quantity": lot_size, # Calculate margin for a single lot
        "product": "MIS"
    }
    
    margin_data = get_margin_requirements(proposed_order)
    if not margin_data:
        return

    # --- Intelligent Sizing ---
    available_margin = margin_data.get("available_margin", 0.0)
    required_per_lot = margin_data.get("required_margin", 0.0)
    
    if required_per_lot <= 0:
        logger.error(f"Margin API returned invalid required_margin: {required_per_lot}")
        return
        
    available_for_trade = available_margin * CAPITAL_ALLOCATION_PERCENT
    max_lots = math.floor(available_for_trade / required_per_lot)
    
    if max_lots == 0:
        logger.warning(f"Margin Inquisition Failed: Insufficient funds for {symbol}. Available: {available_margin}, Required: {required_per_lot}")
        return
        
    final_quantity = max_lots * lot_size
    logger.info(f"Margin Inquisition Passed: Max lots: {max_lots}, Final Qty: {final_quantity}")

    # --- Final Approval & Publication (to ZMQ) ---
    order_event = {
        "symbol": symbol,
        "action": action,
        "quantity": final_quantity,
        "order_type": "MARKET",
        "source": "StrategistV3.0"
    }
    
    topic = "request.execute_order" # This is a request for the Conductor
    pub_socket.send_string(f"{topic} {json.dumps(order_event)}")
    logger.warning(f"PUBLISHED Execution Request: {topic} {order_event}")


def main() -> None:
    """Main loop for the Strategist."""
    context = zmq.Context()
    
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(ZMQ_SUB_URL)
    sub_socket.subscribe("events.signal.amibroker")
    
    pub_socket = context.socket(zmq.PUB)
    pub_socket.connect(ZMQ_PUB_URL)
    
    logger.info(f"Strategist is online. Subscribed to signals on {ZMQ_SUB_URL}. Publishing requests to {ZMQ_PUB_URL}.")
    logger.info(f"Conductor API endpoint set to: {CONDUCTOR_BASE_URL}")

    try:
        while True:
            string = sub_socket.recv_string()
            topic, message = string.split(' ', 1)
            
            if topic == "events.signal.amibroker":
                logger.info(f"Received signal on topic: {topic}")
                signal_data = json.loads(message)
                handle_signal_event(signal_data, pub_socket)

    except KeyboardInterrupt:
        logger.info("Strategist shutting down.")
    finally:
        sub_socket.close()
        pub_socket.close()
        context.term()

if __name__ == "__main__":
    main()