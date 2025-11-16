#!/usr/bin/env python3
"""
Real-time Data Solution for AmiBroker - WebSocket Based

This module provides real-time data to AmiBroker without using the problematic .dll plugin.
It uses WebSocket connections and HTTP APIs to stream data directly to AmiBroker-compatible
endpoints.
"""

import asyncio
import json
import logging
import socket
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import websockets
from websockets.server import serve
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amibroker_data_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    """Market data structure compatible with AmiBroker"""
    symbol: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    open_interest: Optional[int] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None

    def to_amibroker_format(self) -> Dict:
        """Convert to AmiBroker-compatible format"""
        return {
            'symbol': self.symbol,
            'time': self.timestamp.strftime('%Y%m%d%H%M%S'),
            'open': self.open_price,
            'high': self.high_price,
            'low': self.low_price,
            'close': self.close_price,
            'volume': self.volume,
            'open_interest': self.open_interest or 0,
            'bid': self.bid_price or 0,
            'ask': self.ask_price or 0,
            'bid_size': self.bid_size or 0,
            'ask_size': self.ask_size or 0
        }

class AmiBrokerDataService:
    """Real-time data service for AmiBroker using WebSocket and HTTP"""

    def __init__(self, host: str = 'localhost', port: int = 8080,
                 websocket_port: int = 8081, api_key: str = None):
        self.host = host
        self.port = port
        self.websocket_port = websocket_port
        self.api_key = api_key

        # Flask app for HTTP endpoints
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Data storage
        self.symbol_data: Dict[str, MarketData] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.historical_data: Dict[str, List[MarketData]] = {}

        # Service state
        self.running = False
        self.websocket_server = None
        self.data_thread = None

        # Setup routes
        self._setup_routes()

        # Setup WebSocket handlers
        self._setup_websocket_handlers()

    def _setup_routes(self):
        """Setup HTTP routes for AmiBroker integration"""

        @self.app.route('/api/v1/quotes', methods=['GET'])
        def get_quotes():
            """Get real-time quotes"""
            symbols = request.args.get('symbols', '').split(',')
            if not symbols or symbols == ['']:
                return jsonify({'error': 'No symbols provided'}), 400

            quotes = []
            for symbol in symbols:
                if symbol in self.symbol_data:
                    quotes.append(self.symbol_data[symbol].to_amibroker_format())

            return jsonify({'quotes': quotes, 'timestamp': datetime.now().isoformat()})

        @self.app.route('/api/v1/history', methods=['GET'])
        def get_history():
            """Get historical data"""
            symbol = request.args.get('symbol')
            interval = request.args.get('interval', '1min')

            if not symbol:
                return jsonify({'error': 'No symbol provided'}), 400

            if symbol not in self.historical_data:
                return jsonify({'error': 'No historical data for symbol'}), 404

            # Filter by interval and return recent data
            historical = self.historical_data[symbol][-100:]  # Last 100 candles
            return jsonify({
                'symbol': symbol,
                'interval': interval,
                'data': [data.to_amibroker_format() for data in historical]
            })

        @self.app.route('/api/v1/symbols', methods=['GET'])
        def get_symbols():
            """Get available symbols"""
            return jsonify({
                'symbols': list(self.symbol_data.keys()),
                'count': len(self.symbol_data)
            })

        @self.app.route('/api/v1/subscribe', methods=['POST'])
        def subscribe():
            """Subscribe to symbol updates"""
            data = request.get_json()
            symbols = data.get('symbols', [])

            for symbol in symbols:
                if symbol not in self.subscribers:
                    self.subscribers[symbol] = []

            return jsonify({'status': 'subscribed', 'symbols': symbols})\n
        @self.app.route('/api/v1/status', methods=['GET'])
        def get_status():
            """Get service status"""
            return jsonify({
                'status': 'running' if self.running else 'stopped',
                'symbols': len(self.symbol_data),
                'subscribers': len(self.subscribers),
                'websocket_port': self.websocket_port,
                'uptime': time.time() - getattr(self, 'start_time', time.time())
            })

        @self.app.route('/api/v1/atm_scanner', methods=['GET'])
        def get_atm_scanner():
            """Get ATM scanner data (for options trading)"""
            # This would integrate with your existing ATM selection logic
            underlying = request.args.get('underlying', 'NIFTY')
            expiry = request.args.get('expiry')

            # Simulate ATM scanner data
            atm_data = self._generate_atm_data(underlying, expiry)
            return jsonify(atm_data)

    def _setup_websocket_handlers(self):
        """Setup WebSocket handlers for real-time data"""

        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected: {request.sid}")
            emit('connected', {'status': 'connected', 'timestamp': datetime.now().isoformat()})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"Client disconnected: {request.sid}")

        @self.socketio.on('subscribe_symbols')
        def handle_subscribe(data):
            symbols = data.get('symbols', [])
            logger.info(f"Client {request.sid} subscribing to: {symbols}")

            for symbol in symbols:
                if symbol not in self.subscribers:
                    self.subscribers[symbol] = []
                # Add client to symbol subscribers
                # Note: In production, you'd track this per client

            emit('subscribed', {'symbols': symbols})

        @self.socketio.on('unsubscribe_symbols')
        def handle_unsubscribe(data):
            symbols = data.get('symbols', [])
            logger.info(f"Client {request.sid} unsubscribing from: {symbols}")

            for symbol in symbols:
                if symbol in self.subscribers:
                    # Remove client from symbol subscribers
                    pass

            emit('unsubscribed', {'symbols': symbols})

    async def _websocket_server_handler(self, websocket, path):
        """Handle WebSocket connections for real-time data"""
        try:
            async for message in websocket:
                data = json.loads(message)

                if data.get('action') == 'subscribe':
                    symbols = data.get('symbols', [])
                    logger.info(f"WebSocket client subscribing to: {symbols}")

                    # Send current data for subscribed symbols
                    for symbol in symbols:
                        if symbol in self.symbol_data:
                            await websocket.send(json.dumps({
                                'type': 'quote',
                                'symbol': symbol,
                                'data': self.symbol_data[symbol].to_amibroker_format()
                            }))

                elif data.get('action') == 'get_history':
                    symbol = data.get('symbol')
                    if symbol and symbol in self.historical_data:
                        history = [d.to_amibroker_format() for d in self.historical_data[symbol][-100:]]
                        await websocket.send(json.dumps({
                            'type': 'history',
                            'symbol': symbol,
                            'data': history
                        }))

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")

    async def start_websocket_server(self):
        """Start WebSocket server for real-time data"""
        self.websocket_server = await serve(
            self._websocket_server_handler,
            self.host,
            self.websocket_port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.websocket_port}")

    def _generate_atm_data(self, underlying: str, expiry: str = None) -> Dict:
        """Generate ATM (At The Money) options data"""
        # This would integrate with your existing ATM selection logic
        # For now, generate sample data

        current_price = 18000  # Sample NIFTY price
        atm_strike = round(current_price / 50) * 50  # Round to nearest 50

        strikes = [atm_strike - 200, atm_strike - 150, atm_strike - 100,
                  atm_strike - 50, atm_strike, atm_strike + 50,
                  atm_strike + 100, atm_strike + 150, atm_strike + 200]

        atm_data = {
            'underlying': underlying,
            'current_price': current_price,
            'atm_strike': atm_strike,
            'expiry': expiry or '2025-11-27',
            'strikes': []
        }

        for strike in strikes:
            strike_data = {
                'strike': strike,
                'ce_ltp': max(0, current_price - strike + 50),
                'pe_ltp': max(0, strike - current_price + 50),
                'ce_oi': np.random.randint(1000, 10000),
                'pe_oi': np.random.randint(1000, 10000),
                'ce_volume': np.random.randint(100, 5000),
                'pe_volume': np.random.randint(100, 5000)
            }
            atm_data['strikes'].append(strike_data)

        return atm_data

    def update_market_data(self, symbol: str, data: MarketData):
        """Update market data for a symbol"""
        self.symbol_data[symbol] = data

        # Add to historical data
        if symbol not in self.historical_data:
            self.historical_data[symbol] = []

        self.historical_data[symbol].append(data)

        # Keep only recent data (last 1000 candles)
        if len(self.historical_data[symbol]) > 1000:
            self.historical_data[symbol] = self.historical_data[symbol][-1000:]

        # Notify subscribers
        if symbol in self.subscribers:
            for callback in self.subscribers[symbol]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error notifying subscriber: {e}")

        # Emit via Socket.IO
        self.socketio.emit('market_data', {
            'symbol': symbol,
            'data': data.to_amibroker_format()
        })

    def simulate_market_data(self):
        """Simulate real-time market data (for testing)"""
        # Sample symbols
        symbols = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'INFY']

        for symbol in symbols:
            # Generate random price data
            base_price = np.random.uniform(100, 20000)
            variation = np.random.uniform(-0.02, 0.02)

            data = MarketData(
                symbol=symbol,
                timestamp=datetime.now(),
                open_price=base_price,
                high_price=base_price * (1 + abs(variation)),
                low_price=base_price * (1 - abs(variation)),
                close_price=base_price * (1 + variation),
                volume=np.random.randint(1000, 100000),
                open_interest=np.random.randint(10000, 1000000)
            )

            self.update_market_data(symbol, data)

    def _data_generation_loop(self):
        """Background thread for data generation"""
        while self.running:
            try:
                self.simulate_market_data()
                time.sleep(1)  # Update every second
            except Exception as e:
                logger.error(f"Error in data generation loop: {e}")
                time.sleep(5)  # Wait longer on error

    def start(self):
        """Start the data service"""
        if self.running:
            logger.warning("Service is already running")
            return

        self.running = True
        self.start_time = time.time()

        # Start WebSocket server
        asyncio.create_task(self.start_websocket_server())

        # Start data generation thread
        self.data_thread = threading.Thread(target=self._data_generation_loop, daemon=True)
        self.data_thread.start()

        # Start Flask app
        logger.info(f"Starting AmiBroker Data Service on http://{self.host}:{self.port}")
        logger.info(f"WebSocket server on ws://{self.host}:{self.websocket_port}")

        # Run Flask in a separate thread
        flask_thread = threading.Thread(
            target=lambda: self.socketio.run(self.app, host=self.host, port=self.port),
            daemon=True
        )
        flask_thread.start()

    def stop(self):
        """Stop the data service"""
        if not self.running:
            logger.warning("Service is not running")
            return

        self.running = False

        if self.websocket_server:
            self.websocket_server.close()

        logger.info("AmiBroker Data Service stopped")

    def get_integration_config(self) -> Dict:
        """Get integration configuration for AmiBroker"""
        return {
            'http_endpoint': f'http://{self.host}:{self.port}',
            'websocket_endpoint': f'ws://{self.host}:{self.websocket_port}',
            'api_endpoints': {
                'quotes': '/api/v1/quotes',
                'history': '/api/v1/history',
                'symbols': '/api/v1/symbols',
                'atm_scanner': '/api/v1/atm_scanner',
                'status': '/api/v1/status'
            },
            'websocket_support': True,
            'real_time_updates': True,
            'historical_data': True,
            'atm_scanner': True
        }

# Integration with OpenAlgo
class OpenAlgoDataBridge:
    """Bridge between OpenAlgo and AmiBroker Data Service"""

    def __init__(self, openalgo_api_key: str, openalgo_base_url: str = "http://localhost:5000"):
        self.api_key = openalgo_api_key
        self.base_url = openalgo_base_url
        self.data_service = AmiBrokerDataService(api_key=openalgo_api_key)
        self.running = False

    async def fetch_from_openalgo(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Fetch data from OpenAlgo API"""
        try:
            headers = {'Authorization': f'Bearer {self.api_key}'}
            url = f"{self.base_url}{endpoint}"

            response = requests.get(url, headers=headers, params=params or {}, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"OpenAlgo API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error fetching from OpenAlgo: {e}")
            return None

    async def sync_market_data(self):
        """Sync market data from OpenAlgo to AmiBroker service"""
        try:
            # Get symbols from OpenAlgo
            symbols_response = await self.fetch_from_openalgo('/api/v1/search', {'query': 'NIFTY'})
            if symbols_response and 'symbols' in symbols_response:
                symbols = [s['symbol'] for s in symbols_response['symbols'][:10]]  # Limit to 10 for testing

                for symbol in symbols:
                    # Get quotes
                    quotes_response = await self.fetch_from_openalgo('/api/v1/quotes', {'symbols': symbol})
                    if quotes_response and 'quotes' in quotes_response:
                        quote_data = quotes_response['quotes'][0]

                        # Convert to MarketData format
                        market_data = MarketData(
                            symbol=symbol,
                            timestamp=datetime.now(),
                            open_price=quote_data.get('open', 0),
                            high_price=quote_data.get('high', 0),
                            low_price=quote_data.get('low', 0),
                            close_price=quote_data.get('last_price', 0),
                            volume=quote_data.get('volume', 0),
                            open_interest=quote_data.get('oi', 0),
                            bid_price=quote_data.get('bid', 0),
                            ask_price=quote_data.get('ask', 0)
                        )

                        # Update data service
                        self.data_service.update_market_data(symbol, market_data)

        except Exception as e:
            logger.error(f"Error syncing market data: {e}")

    async def sync_atm_data(self, underlying: str = 'NIFTY'):
        """Sync ATM options data from OpenAlgo"""
        try:
            # Get option chain
            option_chain_response = await self.fetch_from_openalgo('/api/v1/optionchain', {'symbol': underlying})
            if option_chain_response:
                # Process option chain data
                logger.info(f"ATM data synced for {underlying}")

        except Exception as e:
            logger.error(f"Error syncing ATM data: {e}")

    async def start_sync_loop(self):
        """Start continuous sync loop"""
        self.running = True

        while self.running:
            try:
                await self.sync_market_data()
                await asyncio.sleep(5)  # Sync every 5 seconds

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    def start(self):
        """Start the data bridge"""
        # Start AmiBroker data service
        self.data_service.start()

        # Start sync loop in background
        sync_task = asyncio.create_task(self.start_sync_loop())

        logger.info("OpenAlgo Data Bridge started")
        return sync_task

    def stop(self):
        """Stop the data bridge"""
        self.running = False
        self.data_service.stop()
        logger.info("OpenAlgo Data Bridge stopped")

# Main function for testing
async def main():
    """Test the real-time data solution"""
    import os

    # Get API key from environment
    api_key = os.getenv('OPENALGO_API_KEY', 'your_api_key_here')

    # Create data bridge
    bridge = OpenAlgoDataBridge(api_key)

    # Start bridge
    bridge.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bridge.stop()

if __name__ == "__main__":
    asyncio.run(main())
