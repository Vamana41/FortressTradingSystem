'''
//      #####   Modified sample_Server.py (Relay - v6 - Corrected Cleanup) #####
//
// Acts as a WebSaocket Relay Server.
// Fixes AttributeError in handler cleanup by using try/except around close().
//
///////////////////////////////////////////////////////////////////////
// Original Author: NSM51
// Modifications for Relay & Fixes: Included based on user request
'''

import asyncio
import websockets
import datetime
import json
import random
import sys
# import pandas as pd # Not used
# import copy # Not used
import logging

# Configure logging for the relay
logging.basicConfig(level=logging.INFO, format='%(asctime)s - RELAY - %(levelname)s - %(message)s')
logger = logging.getLogger("RelayServer")

''' Settings '''
wsport = 10102
USE_FAKE_DATA_GENERATOR = False # Set to True to enable fake data for testing
WEBSOCKET_RELAY_MAX_SIZE = 16 * 1024 * 1024 # e.g., 16 MiB

''' Globals '''
senders = set() # Stores connected client websockets (e.g., fyers_client)
receivers = set() # Stores connected plugin websockets (e.g., AmiBroker)
# subscribed_symbols_by_receiver = {} # Not actively used

async def route_message(websocket, message):
    """ Routes messages based on sender's role and message type """
    sender_role = "Unknown"
    if websocket in senders: sender_role = "Sender"
    elif websocket in receivers: sender_role = "Receiver"

    try:
        # 1. RTD data from SENDER? -> Forward to all RECEIVERS
        if websocket in senders and isinstance(message, str) and message.startswith(R'[{') and message.endswith(R']'):
            disconnected_receivers = set(); current_receivers = list(receivers)
            if not current_receivers: return
            # logger.debug(f"Routing RTD Sender->Receivers: {message[:100]}...") # Verbose
            for receiver in current_receivers:
                try: await receiver.send(message)
                except websockets.ConnectionClosed: disconnected_receivers.add(receiver); logger.warning(f"Receiver {receiver.remote_address} DC mid-RTD.")
                except Exception as e: logger.error(f"Error RTD->Receiver {receiver.remote_address}: {e}")
            if disconnected_receivers: receivers.difference_update(disconnected_receivers); logger.info(f"Cleaned {len(disconnected_receivers)} receivers. Left: {len(receivers)}")

        # 2. Command from RECEIVER? -> Forward to all SENDERS
        elif websocket in receivers and isinstance(message, str) and message.startswith(R'{"cmd"'):
            try:
                jo = json.loads(message); cmd = jo.get("cmd"); arg = jo.get("arg")
                logger.info(f"CMD '{cmd}' from Plugin {websocket.remote_address}: {arg}")
                if cmd in ["bfauto", "bffull", "bfsym", "bfall", "addsym", "remsym", "cping"]:
                    disconnected_senders = set(); current_senders = list(senders)
                    if not current_senders:
                        if cmd != "cping": err_resp = {"cmd": cmd, "code": 404, "arg": f"No sender for '{cmd}'"}; await websocket.send(json.dumps(err_resp, separators=(',', ':'))); logger.warning(f"No Senders for '{cmd}'. Error sent.")
                        else: logger.warning(f"No Senders for '{cmd}'.")
                        return
                    # logger.debug(f"Routing CMD Plugin->Senders: {message}") # Verbose
                    for sender in current_senders:
                        try: await sender.send(message)
                        except websockets.ConnectionClosed: disconnected_senders.add(sender); logger.warning(f"Sender {sender.remote_address} DC mid-CMD.")
                        except Exception as e: logger.error(f"Error CMD->Sender {sender.remote_address}: {e}")
                    if disconnected_senders: senders.difference_update(disconnected_senders); logger.info(f"Cleaned {len(disconnected_senders)} senders. Left: {len(senders)}")
                else: logger.warning(f"Unknown Plugin CMD '{cmd}'.")
            except json.JSONDecodeError: logger.error(f"Bad JSON CMD Plugin {websocket.remote_address}: {message}")
            except Exception as e: logger.error(f"Error process Plugin CMD {websocket.remote_address}: {e}", exc_info=True)

        # 3. Hist/Response from SENDER? -> Forward to all RECEIVERS
        elif websocket in senders and isinstance(message, str) and (message.startswith(R'{"hist"') or (message.startswith(R'{"cmd"') and '"code"' in message)):
             logger.info(f"Received Hist/Resp Sender {websocket.remote_address}: {message[:150]}...")
             disconnected_receivers = set(); current_receivers = list(receivers)
             if not current_receivers: logger.warning(f"Hist/Resp from Sender, but no Receivers."); return
             # logger.debug(f"Routing Hist/Resp Sender->Receivers...") # Verbose
             for receiver in current_receivers:
                 try: await receiver.send(message)
                 except websockets.ConnectionClosed: disconnected_receivers.add(receiver); logger.warning(f"Receiver {receiver.remote_address} DC mid-Hist/Resp.")
                 except Exception as e: logger.error(f"Error Hist/Resp->Receiver {receiver.remote_address}: {e}")
             if disconnected_receivers: receivers.difference_update(disconnected_receivers); logger.info(f"Cleaned {len(disconnected_receivers)} receivers. Left: {len(receivers)}")

        # 4. ACK from RECEIVER? -> Log only
        elif websocket in receivers and isinstance(message, str) and message.startswith(R'{"ack"'):
             logger.info(f"ACK Plugin {websocket.remote_address}: {message}")

        # 5. Unknown
        else: logger.warning(f"Unknown msg {sender_role} {websocket.remote_address}: {message[:150]}...")
    except websockets.ConnectionClosed: logger.warning(f"Conn closed {sender_role} {websocket.remote_address} mid-route.")
    except Exception as e: logger.error(f"Routing error {sender_role} {websocket.remote_address}: {e}", exc_info=True)


async def handler(websocket):
    """ Handles new connections, assigns roles, and manages the message loop """
    role = None
    remote_addr = websocket.remote_address
    logger.info(f"Client connecting from {remote_addr}")

    try:
        # Role Identification
        try: first_msg = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        except asyncio.TimeoutError: logger.error(f"Timeout role ID {remote_addr}. Closing."); await websocket.close(code=1008); return
        except websockets.ConnectionClosed as cc: logger.warning(f"Closed before role ID {remote_addr}. Code: {cc.code}"); return
        except Exception as e: logger.error(f"Error recv first msg {remote_addr}: {e}"); await websocket.close(code=1011); return

        if first_msg == "rolesend": role = "Sender"; senders.add(websocket); logger.info(f"Registered {remote_addr} as {role}. Senders: {len(senders)}")
        elif first_msg == "rolerecv": role = "Receiver"; receivers.add(websocket); logger.info(f"Registered {remote_addr} as {role}. Receivers: {len(receivers)}")
        else: logger.error(f"Unknown first msg ('{first_msg}') {remote_addr}. Closing."); await websocket.close(code=1002); return

        # Message Loop
        async for message in websocket:
            if isinstance(message, bytes):
                try: message = message.decode('utf-8')
                except UnicodeDecodeError: logger.error(f"Non-UTF8 bytes {role} {remote_addr}. Ignore."); continue
            await route_message(websocket, message)

    except websockets.ConnectionClosed as cc:
        if cc.code in [1000, 1001]: logger.info(f"Client {remote_addr} ({role}) disconnected normally. Code: {cc.code}")
        else: logger.warning(f"Client {remote_addr} ({role}) disconnected abnormally. Code: {cc.code}, Reason: {cc.reason}")
    except Exception as e: logger.error(f"Handler error {remote_addr} ({role}): {e}", exc_info=True)
    finally:
        # --- Cleanup ---
        logger.info(f"Cleaning up connection for {remote_addr} ({role})")
        if role == "Sender": senders.discard(websocket); logger.info(f"Unreg sender {remote_addr}. Senders: {len(senders)}")
        elif role == "Receiver": receivers.discard(websocket); logger.info(f"Unreg receiver {remote_addr}. Receivers: {len(receivers)}")

        # --- CORRECTED Cleanup Close ---
        # Attempt to close the connection if the object exists
        if websocket:
             try:
                 # Don't need to check if closed, just attempt close
                 await websocket.close()
                 logger.debug(f"Attempted final WebSocket close for {remote_addr}")
             except websockets.ConnectionClosed:
                 # Ignore if it was already closed
                 logger.debug(f"WebSocket was already closed for {remote_addr} during final cleanup.")
             except RuntimeError as rt_err:
                 # Handle cases where the event loop might be closing
                 if "Event loop is closed" in str(rt_err):
                     logger.warning(f"Could not close socket for {remote_addr}: Event loop closed.")
                 else:
                     logger.error(f"Runtime error during final WebSocket close for {remote_addr}: {rt_err}")
             except Exception as close_err:
                 # Log other potential errors during close
                 logger.error(f"Error during final WebSocket close for {remote_addr}: {close_err}")
        # --- End Corrected Cleanup Close ---

# --- [ Fake Data Generator remains the same ] ---
async def broadcast_messages_count():
    """Generates and broadcasts fake tick data (if enabled)."""
    if not USE_FAKE_DATA_GENERATOR: logger.info("Fake data generator DISABLED."); await asyncio.Future(); return
    logger.warning("--- FAKE data generator RUNNING ---"); tf=1; sleepT=0.9; pTm=0; s1=s2=s3=0
    def r(l=1,u=9): return round(random.uniform(l,u),2)
    try:
        while True:
            await asyncio.sleep(sleepT); dt=datetime.datetime.now(); t=dt.hour*10000+int(dt.minute/tf)*tf*100; d=int(dt.strftime('%Y%m%d'))
            if pTm != t: v1=v2=v3=0; pTm = t
            else: v1=random.randint(1,5); v2=random.randint(1,3); v3=random.randint(1,2) # Use bar volume directly
            s1+=v1; s2+=v2; s3+=v3 # Cumulative still calculated but not used in default fake data
            data = [{"n":"FAKE1","d":d,"t":t,"o":r(10,11),"h":r(11,12),"l":r(9,10),"c":r(10,11),"v":v1},{"n":"FAKE2","d":d,"t":t,"o":r(20,21),"h":r(21,22),"l":r(19,20),"c":r(20,21),"v":v2},{"n":"FAKE3","d":d,"t":t,"o":r(30,31),"h":r(31,32),"l":r(29,30),"c":r(30,31),"v":v3}]
            fake_data_json = json.dumps(data, separators=(',', ':'))
            disconnected = set(); current = list(receivers)
            for rc in current:
                try: await rc.send(fake_data_json)
                except websockets.ConnectionClosed: disconnected.add(rc); logger.warning(f"FAKE_GEN: Receiver {rc.remote_address} DC.")
                except Exception as e: logger.error(f"FAKE_GEN: Error->Receiver {rc.remote_address}: {e}")
            if disconnected: receivers.difference_update(disconnected)
    except asyncio.CancelledError: logger.info("Fake data generator task cancelled.")
    except Exception as e: logger.error(f"Fake data loop error: {e}", exc_info=True)

# --- [ Server Start/Manage remains the same ] ---
async def start_ws_server(aport):
    """ Starts the WebSocket server and manages tasks """
    server_instance = None; main_server_wait_task = None; fake_data_task = None
    try:
        server_instance = await websockets.serve(handler, "localhost", aport,max_size=WEBSOCKET_RELAY_MAX_SIZE, ping_interval=20, ping_timeout=20)
        logger.info(f"Relay Server started on ws://localhost:{aport} with max_size={WEBSOCKET_RELAY_MAX_SIZE}")
        main_server_wait_task = asyncio.create_task(server_instance.wait_closed(), name="ServerWaitClosed")
        tasks = [main_server_wait_task]
        if USE_FAKE_DATA_GENERATOR: logger.warning("Relay FAKE data ENABLED."); fake_data_task = asyncio.create_task(broadcast_messages_count(), name="FakeDataGen"); tasks.append(fake_data_task)
        else: logger.info("Relay RELAY-ONLY mode.")
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
             try: task.result(); logger.info(f"Task {task.get_name()} finished.")
             except asyncio.CancelledError: logger.info(f"Task {task.get_name()} cancelled.")
             except Exception as task_ex: logger.error(f"Task {task.get_name()} failed: {task_ex}", exc_info=True)
    except OSError as e: logger.critical(f"Failed start server port {aport}. In use? {e}")
    except asyncio.CancelledError: logger.info("Server startup/main task cancelled.")
    except Exception as e: logger.critical(f"Server failed: {e}", exc_info=True)
    finally:
        logger.info("Server shutdown complete.")
        tasks_to_cancel = [t for t in [main_server_wait_task, fake_data_task] if t and not t.done()]
        if tasks_to_cancel: logger.info(f"Cancelling {len(tasks_to_cancel)} pending tasks..."); [task.cancel() for task in tasks_to_cancel]; await asyncio.gather(*tasks_to_cancel, return_exceptions=True); logger.info("Pending tasks cancelled.")
        if server_instance and server_instance.is_serving():
            logger.info("Closing server instance..."); server_instance.close();
            try: await asyncio.wait_for(server_instance.wait_closed(), timeout=5.0); logger.info("Server instance closed.")
            except asyncio.TimeoutError: logger.warning("Timeout waiting for server close.")
            except Exception as close_err: logger.error(f"Error wait server close: {close_err}")
        logger.info("Server shutdown complete.")

async def main(): await start_ws_server(wsport)

if __name__ == "__main__":
    try:
        print("\n"+"="*40)
        print(f"  Starting WebSocket Relay Server (v6 - Corrected Cleanup)") # Version Bump
        print(f"  Listening on Port: {wsport}")
        print(f"  Max Message Size: {WEBSOCKET_RELAY_MAX_SIZE / (1024*1024):.1f} MiB") # Show limit
        print(f"  Fake Data Generation: {'ENABLED' if USE_FAKE_DATA_GENERATOR else 'DISABLED'}")
        print( "  Press Ctrl+C to exit")
        print("="*40+"\n")
        asyncio.run(main())
        logger.info("Main execution finished."); print("Server stopped.")
    except KeyboardInterrupt: logger.info("Ctrl+C received..."); print("\nShutdown signal...")
    except Exception as e: logger.critical(f"Critical main error: {e}", exc_info=True); print(f"ERROR: {e}")
    finally: logger.info("Relay server process finished.")
