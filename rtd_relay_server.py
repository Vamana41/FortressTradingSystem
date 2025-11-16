#!/usr/bin/env python3
"""
RTD Relay Server for AmiBroker - Handles raw RTD data format
This server forwards real-time data directly to AmiBroker without modification
"""

import asyncio
import websockets
import json
import logging
import time
from datetime import datetime
import os
from typing import Dict, Set, Optional
import signal
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv("relay_server.env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rtd_relay.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RTDRelayServer:
    """
    RTD Relay Server that forwards real-time data directly to AmiBroker
    Handles the raw RTD format: [{"n": "SBIN", "d": 20251116, "t": 134500, "o": 967.85, "h": 969.05, "l": 952.0, "c": 967.85, "v": 11032927}]
    """

    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.running = True
        self.messages_processed = 0
        self.start_time = datetime.now()
        self.port = int(os.getenv("RELAY_PORT", "8766"))

        # Configuration
        self.host = os.getenv("RELAY_HOST", "localhost")

        # Statistics
        self.rtd_messages_forwarded = 0
        self.clients_connected = 0

    async def start(self):
        """Start the RTD relay server"""
        logger.info(f"Starting RTD Relay Server on {self.host}:{self.port}")
        logger.info("This server forwards RTD data directly to AmiBroker")

        # Start WebSocket server
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        ):
            logger.info(f"RTD Relay server listening on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

    async def handle_client(self, websocket, path=None):
        """Handle incoming client connections (from data injectors)"""
        self.clients.add(websocket)
        self.clients_connected += 1
        client_id = f"client_{len(self.clients)}"
        logger.info(f"New RTD client connected: {client_id} (Total clients: {len(self.clients)})")

        try:
            # Send initial connection acknowledgment
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "server": "RTD Relay Server",
                "version": "1.0",
                "message": "Ready to forward RTD data to AmiBroker"
            }))

            async for message in websocket:
                try:
                    # Try to parse as RTD data array first
                    data = json.loads(message)

                    if isinstance(data, list) and len(data) > 0:
                        # This is RTD data format - forward directly to AmiBroker clients
                        await self.forward_rtd_data(data)
                        self.messages_processed += 1

                        # Log the RTD data for debugging
                        if len(data) > 0:
                            first_item = data[0]
                            symbol = first_item.get('n', 'Unknown')
                            ltp = first_item.get('c', 0)
                            logger.info(f"RTD FORWARDED: {symbol} LTP: {ltp}")

                    elif isinstance(data, dict) and data.get("type"):
                        # This is a structured message - handle accordingly
                        await self.handle_structured_message(websocket, data)

                    else:
                        logger.warning(f"Unknown message format from client: {type(data)}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from client: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                except Exception as e:
                    logger.error(f"Error processing client message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"RTD client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error with RTD client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"RTD client {client_id} removed. Total clients: {len(self.clients)}")

    async def forward_rtd_data(self, rtd_data):
        """Forward RTD data to all connected clients (AmiBroker)"""
        if not self.clients:
            logger.warning("No clients connected to forward RTD data")
            return

        disconnected_clients = []

        # Forward the RTD data to all connected clients
        for client in self.clients:
            try:
                await client.send(json.dumps(rtd_data, separators=(',', ':')))
                self.rtd_messages_forwarded += 1
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(client)
            except Exception as e:
                logger.error(f"Failed to forward RTD data to client: {e}")
                disconnected_clients.append(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            self.clients.discard(client)

    async def handle_structured_message(self, websocket, data):
        """Handle structured messages with type field"""
        msg_type = data.get("type", "")

        if msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))

        elif msg_type == "subscribe":
            symbol = data.get("symbol", "")
            if symbol:
                logger.info(f"Client subscribed to {symbol}")
                await websocket.send(json.dumps({
                    "type": "subscription_confirmed",
                    "symbol": symbol,
                    "message": f"Subscribed to {symbol}"
                }))

        elif msg_type == "get_stats":
            stats = self.get_statistics()
            await websocket.send(json.dumps({
                "type": "statistics",
                "data": stats
            }))

        else:
            logger.debug(f"Received structured message: {msg_type}")

    def get_statistics(self):
        """Get server statistics"""
        uptime = datetime.now() - self.start_time
        return {
            "uptime_seconds": uptime.total_seconds(),
            "clients_connected": len(self.clients),
            "messages_processed": self.messages_processed,
            "rtd_messages_forwarded": self.rtd_messages_forwarded,
            "clients_total": self.clients_connected,
            "server_status": "running" if self.running else "stopped"
        }

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping RTD relay server...")
    sys.exit(0)

async def main():
    """Main entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and start RTD relay server
    server = RTDRelayServer()

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("RTD Relay server stopped by user")
    except Exception as e:
        logger.error(f"RTD Relay server error: {e}")
        raise
    finally:
        server.running = False
        logger.info("RTD Relay server shutdown complete")

if __name__ == "__main__":
    logger.info("Starting RTD Relay Server for AmiBroker integration...")
    asyncio.run(main())
