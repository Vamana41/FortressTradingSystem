#!/usr/bin/env python3
"""
Simple OpenAlgo Relay Server - Prevents AmiBroker hanging
"""

import asyncio
import websockets
import json
import logging
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleRelayServer:
    def __init__(self):
        self.clients = set()
        self.quote_cache = {}
        self.api_key = os.getenv("OPENALGO_API_KEY", "")
        self.port = int(os.getenv("RELAY_PORT", "8766"))
        
    async def handle_client(self, websocket, path):
        """Handle client connections"""
        self.clients.add(websocket)
        client_id = f"client_{len(self.clients)}"
        logger.info(f"Client {client_id} connected")
        
        try:
            # Send connection acknowledgment
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "server": "OpenAlgo Relay"
            }))
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON"
                    }))
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            self.clients.discard(websocket)
            
    async def process_message(self, websocket, data):
        """Process incoming messages"""
        msg_type = data.get("type", "")
        
        if msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
            
        elif msg_type == "get_quote":
            symbol = data.get("symbol", "")
            if symbol:
                await self.send_quote(websocket, symbol)
                
        elif msg_type == "subscribe":
            symbol = data.get("symbol", "")
            if symbol:
                logger.info(f"Client subscribed to {symbol}")
                await self.send_quote(websocket, symbol)
                
        elif msg_type == "get_history":
            symbol = data.get("symbol", "")
            await websocket.send(json.dumps({
                "type": "history",
                "symbol": symbol,
                "data": [],
                "message": "Historical data not available"
            }))
            
        else:
            logger.warning(f"Unknown message type: {msg_type}")
            
    async def send_quote(self, websocket, symbol):
        """Send quote data to client"""
        # Simulate quote data for testing
        quote_data = {
            "type": "quote",
            "symbol": symbol,
            "ltp": 150.0 + (hash(symbol) % 100) / 10.0,  # Simulated price
            "open": 149.5,
            "high": 151.0,
            "low": 148.5,
            "close": 150.0,
            "volume": 1000000,
            "oi": 50000,
            "timestamp": int(time.time())
        }
        
        await websocket.send(json.dumps(quote_data))
        
    async def start(self):
        """Start the relay server"""
        logger.info(f"Starting relay server on port {self.port}")
        
        async with websockets.serve(self.handle_client, "localhost", self.port):
            logger.info(f"Relay server listening on ws://localhost:{self.port}")
            await asyncio.Future()  # Run forever

async def main():
    server = SimpleRelayServer()
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")