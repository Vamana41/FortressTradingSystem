#!/usr/bin/env python3
"""
OpenAlgo Relay Server - Prevents AmiBroker hanging by managing WebSocket connections
Similar to Rtd_Ws_AB_plugin relay server approach
"""

import asyncio
import websockets
import json
import logging
import signal
import sys
import time
from datetime import datetime
import threading
import queue
import requests
from typing import Dict, Set, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OpenAlgoRelayServer:
    """
    Relay server that manages WebSocket connections to prevent AmiBroker hanging.
    Provides a robust, non-blocking interface for the AmiBroker plugin.
    """
    
    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.symbol_subscriptions: Dict[str, Set[websockets.WebSocketServerProtocol]] = {}
        self.quote_cache: Dict[str, dict] = {}
        self.running = True
        self.message_queue = queue.Queue()
        self.openalgo_ws = None
        self.openalgo_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5
        
        # Configuration
        self.openalgo_base_url = os.getenv("OPENALGO_BASE_URL", "http://localhost:5000")
        self.openalgo_ws_url = os.getenv("OPENALGO_WS_URL", "ws://localhost:8765")
        self.relay_port = int(os.getenv("RELAY_PORT", "8766"))
        self.api_key = os.getenv("OPENALGO_API_KEY", "")
        
        # Statistics
        self.messages_processed = 0
        self.connections_handled = 0
        self.start_time = datetime.now()
        
    async def start(self):
        """Start the relay server"""
        logger.info(f"Starting OpenAlgo Relay Server on port {self.relay_port}")
        logger.info(f"Connecting to OpenAlgo at {self.openalgo_base_url}")
        
        # Start background tasks
        asyncio.create_task(self.connect_to_openalgo())
        asyncio.create_task(self.process_message_queue())
        asyncio.create_task(self.health_check_loop())
        
        # Start WebSocket server
        async with websockets.serve(
            self.handle_client,
            "localhost",
            self.relay_port,
            ping_interval=30,
            ping_timeout=10
        ):
            logger.info(f"Relay server listening on ws://localhost:{self.relay_port}")
            await asyncio.Future()  # Run forever
            
    async def handle_client(self, websocket, path=None):
        """Handle incoming client connections (from AmiBroker plugin)"""
        self.clients.add(websocket)
        self.connections_handled += 1
        client_id = f"client_{len(self.clients)}"
        logger.info(f"New client connected: {client_id}")
        
        try:
            # Send initial connection acknowledgment
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "server": "OpenAlgo Relay",
                "version": "1.0"
            }))
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_client_message(websocket, data)
                    self.messages_processed += 1
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from client: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                except Exception as e:
                    logger.error(f"Error handling client message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error with client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            # Clean up subscriptions for this client
            await self.cleanup_client_subscriptions(websocket)
            
    async def handle_client_message(self, websocket, data):
        """Handle messages from AmiBroker plugin clients"""
        msg_type = data.get("type", "")
        
        if msg_type == "subscribe":
            symbol = data.get("symbol", "")
            if symbol:
                await self.handle_subscription(websocket, symbol)
                
        elif msg_type == "unsubscribe":
            symbol = data.get("symbol", "")
            if symbol:
                await self.handle_unsubscription(websocket, symbol)
                
        elif msg_type == "get_quote":
            symbol = data.get("symbol", "")
            if symbol:
                await self.send_cached_quote(websocket, symbol)
                
        elif msg_type == "get_history":
            symbol = data.get("symbol", "")
            interval = data.get("interval", "1m")
            if symbol:
                await self.send_history_data(websocket, symbol, interval)
                
        elif msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
            
        else:
            logger.warning(f"Unknown message type: {msg_type}")
            
    async def handle_subscription(self, websocket, symbol):
        """Handle symbol subscription requests"""
        if symbol not in self.symbol_subscriptions:
            self.symbol_subscriptions[symbol] = set()
        
        self.symbol_subscriptions[symbol].add(websocket)
        logger.info(f"Client subscribed to {symbol}")
        
        # Send current cached data if available
        await self.send_cached_quote(websocket, symbol)
        
        # Forward subscription to OpenAlgo if connected
        if self.openalgo_connected and self.openalgo_ws:
            try:
                await self.openalgo_ws.send(json.dumps({
                    "type": "subscribe",
                    "symbol": symbol
                }))
            except Exception as e:
                logger.error(f"Failed to forward subscription to OpenAlgo: {e}")
                
    async def handle_unsubscription(self, websocket, symbol):
        """Handle symbol unsubscription requests"""
        if symbol in self.symbol_subscriptions:
            self.symbol_subscriptions[symbol].discard(websocket)
            if not self.symbol_subscriptions[symbol]:
                del self.symbol_subscriptions[symbol]
                
                # Forward unsubscription to OpenAlgo if connected
                if self.openalgo_connected and self.openalgo_ws:
                    try:
                        await self.openalgo_ws.send(json.dumps({
                            "type": "unsubscribe",
                            "symbol": symbol
                        }))
                    except Exception as e:
                        logger.error(f"Failed to forward unsubscription to OpenAlgo: {e}")
                        
    async def send_cached_quote(self, websocket, symbol):
        """Send cached quote data to client"""
        if symbol in self.quote_cache:
            quote_data = self.quote_cache[symbol].copy()
            quote_data["type"] = "quote"
            quote_data["cached"] = True
            await websocket.send(json.dumps(quote_data))
            
    async def send_history_data(self, websocket, symbol, interval):
        """Send historical data to client"""
        # For now, return empty history to prevent blocking
        # In production, this would fetch from OpenAlgo HTTP API
        await websocket.send(json.dumps({
            "type": "history",
            "symbol": symbol,
            "interval": interval,
            "data": [],
            "message": "Historical data not implemented in relay"
        }))
        
    async def connect_to_openalgo(self):
        """Maintain connection to OpenAlgo WebSocket server"""
        while self.running:
            try:
                if not self.openalgo_connected:
                    logger.info(f"Connecting to OpenAlgo WebSocket: {self.openalgo_ws_url}")
                    
                    # Try to connect with authentication in URL if needed
                    ws_url = self.openalgo_ws_url
                    if self.api_key:
                        # Add API key as query parameter if not already in URL
                        if '?' not in ws_url:
                            ws_url += f"?api_key={self.api_key}"
                    
                    # Create connection with proper headers
                    headers = []
                    if self.api_key:
                        headers = [("Authorization", f"Bearer {self.api_key}")]
                    
                    async with websockets.connect(
                        ws_url,
                        ping_interval=30,
                        ping_timeout=10,
                        extra_headers=headers if headers else None
                    ) as websocket:
                        self.openalgo_ws = websocket
                        self.openalgo_connected = True
                        self.reconnect_attempts = 0
                        logger.info("Connected to OpenAlgo WebSocket")
                        
                        # Resubscribe to symbols
                        await self.resubscribe_all_symbols()
                        
                        # Handle incoming messages
                        await self.handle_openalgo_messages()
                        
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"OpenAlgo connection error: {e}")
                self.openalgo_connected = False
                self.openalgo_ws = None
                
                # Exponential backoff for reconnection
                self.reconnect_attempts += 1
                if self.reconnect_attempts <= self.max_reconnect_attempts:
                    delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
                    logger.info(f"Reconnecting in {delay} seconds (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max reconnection attempts reached, waiting longer...")
                    await asyncio.sleep(300)  # Wait 5 minutes before trying again
                    
    async def handle_openalgo_messages(self):
        """Handle messages from OpenAlgo WebSocket"""
        try:
            async for message in self.openalgo_ws:
                try:
                    data = json.loads(message)
                    await self.process_openalgo_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from OpenAlgo: {e}")
                except Exception as e:
                    logger.error(f"Error processing OpenAlgo message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("OpenAlgo WebSocket connection closed")
            self.openalgo_connected = False
            self.openalgo_ws = None
        except Exception as e:
            logger.error(f"Error in OpenAlgo message handler: {e}")
            self.openalgo_connected = False
            self.openalgo_ws = None
            
    async def process_openalgo_message(self, data):
        """Process messages received from OpenAlgo"""
        msg_type = data.get("type", "")
        
        if msg_type == "quote":
            symbol = data.get("symbol", "")
            if symbol:
                # Update cache
                self.quote_cache[symbol] = data.copy()
                
                # Forward to subscribed clients
                await self.forward_quote_to_clients(symbol, data)
                
        elif msg_type == "auth":
            if data.get("status") == "success":
                logger.info("Authenticated with OpenAlgo")
            else:
                logger.error(f"OpenAlgo authentication failed: {data.get('message', 'Unknown error')}")
                
        elif msg_type == "error":
            logger.error(f"OpenAlgo error: {data.get('message', 'Unknown error')}")
            
        else:
            logger.debug(f"Received OpenAlgo message: {msg_type}")
            
    async def forward_quote_to_clients(self, symbol, quote_data):
        """Forward quote data to all subscribed clients"""
        if symbol in self.symbol_subscriptions:
            disconnected_clients = []
            
            for client in self.symbol_subscriptions[symbol]:
                try:
                    await client.send(json.dumps(quote_data))
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.append(client)
                except Exception as e:
                    logger.error(f"Failed to forward quote to client: {e}")
                    disconnected_clients.append(client)
                    
            # Clean up disconnected clients
            for client in disconnected_clients:
                self.symbol_subscriptions[symbol].discard(client)
                
            # Remove empty subscription sets
            if not self.symbol_subscriptions[symbol]:
                del self.symbol_subscriptions[symbol]
                
    async def resubscribe_all_symbols(self):
        """Resubscribe to all symbols after reconnection"""
        for symbol in self.symbol_subscriptions:
            try:
                if self.openalgo_ws:
                    await self.openalgo_ws.send(json.dumps({
                        "type": "subscribe",
                        "symbol": symbol
                    }))
            except Exception as e:
                logger.error(f"Failed to resubscribe to {symbol}: {e}")
                
    async def cleanup_client_subscriptions(self, websocket):
        """Clean up all subscriptions for a disconnected client"""
        symbols_to_remove = []
        
        for symbol, clients in self.symbol_subscriptions.items():
            clients.discard(websocket)
            if not clients:
                symbols_to_remove.append(symbol)
                
        for symbol in symbols_to_remove:
            del self.symbol_subscriptions[symbol]
            
            # Unsubscribe from OpenAlgo if connected
            if self.openalgo_connected and self.openalgo_ws:
                try:
                    await self.openalgo_ws.send(json.dumps({
                        "type": "unsubscribe",
                        "symbol": symbol
                    }))
                except Exception as e:
                    logger.error(f"Failed to unsubscribe {symbol} from OpenAlgo: {e}")
                    
    async def process_message_queue(self):
        """Process queued messages (for future extensions)"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=1)
                # Process queued messages
                logger.debug(f"Processing queued message: {message}")
            except queue.Empty:
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing message queue: {e}")
                
    async def health_check_loop(self):
        """Periodic health check and statistics"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                uptime = datetime.now() - self.start_time
                logger.info(f"Health Check - Uptime: {uptime}, "
                          f"Clients: {len(self.clients)}, "
                          f"Symbols: {len(self.symbol_subscriptions)}, "
                          f"Messages: {self.messages_processed}, "
                          f"OpenAlgo Connected: {self.openalgo_connected}")
                          
                # Send heartbeat to all clients
                heartbeat = json.dumps({
                    "type": "heartbeat",
                    "timestamp": int(time.time()),
                    "stats": {
                        "uptime_seconds": uptime.total_seconds(),
                        "clients": len(self.clients),
                        "symbols": len(self.symbol_subscriptions),
                        "messages_processed": self.messages_processed
                    }
                })
                
                disconnected_clients = []
                for client in self.clients:
                    try:
                        await client.send(heartbeat)
                    except websockets.exceptions.ConnectionClosed:
                        disconnected_clients.append(client)
                    except Exception as e:
                        logger.error(f"Failed to send heartbeat: {e}")
                        disconnected_clients.append(client)
                        
                # Clean up disconnected clients
                for client in disconnected_clients:
                    self.clients.discard(client)
                    await self.cleanup_client_subscriptions(client)
                    
            except Exception as e:
                logger.error(f"Health check error: {e}")
                
    def get_statistics(self):
        """Get server statistics"""
        uptime = datetime.now() - self.start_time
        return {
            "uptime_seconds": uptime.total_seconds(),
            "clients_connected": len(self.clients),
            "symbols_subscribed": len(self.symbol_subscriptions),
            "messages_processed": self.messages_processed,
            "connections_handled": self.connections_handled,
            "openalgo_connected": self.openalgo_connected,
            "reconnect_attempts": self.reconnect_attempts
        }

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping server...")
    sys.exit(0)

async def main():
    """Main entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start relay server
    server = OpenAlgoRelayServer()
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        server.running = False
        logger.info("Server shutdown complete")

if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("OPENALGO_API_KEY"):
        logger.warning("OPENALGO_API_KEY not set in environment")
    
    # Run the server
    asyncio.run(main())