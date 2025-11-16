# ======================================================================================
# ==  AmiBroker Watcher Sentinel (v2.1 - Complete)                                    ==
# ======================================================================================
# This sentinel's sole duty is to watch the AmiBroker signal directory.
# Upon detecting a new signal file, it parses it and publishes a standardized
# "events.signal.amibroker" event onto the core ZMQ bus.
# ======================================================================================

import zmq
import time
import logging
import os
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Optional, Any

# --- Configuration ---
# !!! IMPORTANT: UPDATE THIS PATH TO YOUR REAL AMIBROKER SIGNAL FOLDER !!!
AMI_SIGNAL_DIR = "C:\\AmiBroker\\Signals"

ZMQ_PUB_URL = "tcp://127.0.0.1:5555" # The port components PUBLISH to

# --- Path Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    filename=os.path.join(LOGS_DIR, 'sentinel_watcher.log'),
                    filemode='a',
                    format='%(asctime)s - SENTINEL - %(levelname)s - %(message)s')
logger = logging.getLogger("AmiWatcher")

class SignalFileHandler(FileSystemEventHandler):
    """Handles file creation events from AmiBroker."""
    def __init__(self, zmq_socket: zmq.Socket):
        self.socket = zmq_socket

    def on_created(self, event: Any) -> None:
        """Called when a new file is created in the directory."""
        if event.is_directory or not event.src_path.endswith('.csv'):
            return

        logger.info(f"New signal file detected: {event.src_path}")
        time.sleep(0.1) # Brief pause to ensure file is fully written and closed

        try:
            with open(event.src_path, 'r') as f:
                # Assuming a simple CSV format: SYMBOL,ACTION,PRICE
                # Example: NIFTY24DECFUT,BUY,24500.50
                line = f.readline().strip()
                if not line:
                    logger.warning(f"Signal file is empty: {event.src_path}")
                    return

                parts = line.split(',')
                if len(parts) == 3:
                    symbol, action, price_str = parts

                    try:
                        price = float(price_str)
                    except ValueError:
                        logger.error(f"Could not parse price '{price_str}' from file: {event.src_path}")
                        return

                    event_payload = {
                        "source": "AmiBroker",
                        "symbol": symbol,
                        "action": action.upper(),
                        "price": price
                    }

                    topic = "events.signal.amibroker"
                    self.socket.send_string(f"{topic} {json.dumps(event_payload)}")
                    logger.info(f"Published to ZMQ -> Topic: {topic}, Payload: {event_payload}")

                else:
                    logger.warning(f"Could not parse signal file (expected 3 parts, got {len(parts)}): {event.src_path}")

            # Clean up the file after processing
            os.remove(event.src_path)

        except PermissionError:
            logger.warning(f"Permission denied for {event.src_path}. AmiBroker may still hold the lock. Will retry.")
        except Exception as e:
            logger.error(f"Error processing signal file {event.src_path}: {e}", exc_info=True)

def main() -> None:
    """Main function to start the watcher and ZMQ publisher."""
    context = zmq.Context()
    socket = context.socket(zmq.PUB)

    try:
        socket.connect(ZMQ_PUB_URL)
        logger.info(f"Sentinel connected to ZMQ Publisher at {ZMQ_PUB_URL}")
    except Exception as e:
        logger.critical(f"Could not connect to ZMQ socket at {ZMQ_PUB_URL}: {e}")
        return

    if not os.path.isdir(AMI_SIGNAL_DIR):
        logger.critical(f"CRITICAL: Signal directory not found: {AMI_SIGNAL_DIR}")
        logger.critical("Please update the AMI_SIGNAL_DIR variable in this script.")
        return

    event_handler = SignalFileHandler(socket)
    observer = Observer()
    observer.schedule(event_handler, AMI_SIGNAL_DIR, recursive=False)

    try:
        observer.start()
        logger.info(f"Sentinel is now watching for signals in: {AMI_SIGNAL_DIR}")
        while True:
            time.sleep(60) # Keep the main thread alive
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Stopping observer.")
    except Exception as e:
        logger.error(f"Watcher observer failed: {e}", exc_info=True)
    finally:
        observer.stop()
        observer.join()
        socket.close()
        context.term()
        logger.info("Sentinel has shut down.")

if __name__ == "__main__":
    main()
