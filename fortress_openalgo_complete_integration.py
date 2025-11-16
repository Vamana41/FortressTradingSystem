#!/usr/bin/env python3
"""
Complete OpenAlgo API Integration for Fortress Trading System

This module provides comprehensive integration with all OpenAlgo API endpoints,
including real-time data feeds, order management, portfolio tracking, and
advanced trading features.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class APIResponse:
    """Standard API response wrapper"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class OpenAlgoCompleteIntegration:
    """Complete integration with all OpenAlgo API endpoints"""

    def __init__(self, api_key: str, base_url: str = "http://localhost:5000"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
        self.websocket_session = None
        self.websocket_connected = False
        self.subscriptions = set()
        self.data_cache = {}
        self.cache_timeout = timedelta(minutes=5)

        # API endpoints mapping
        self.endpoints = {
            # Core Trading APIs
            'funds': '/api/v1/funds',
            'orderbook': '/api/v1/orderbook',
            'positionbook': '/api/v1/positionbook',
            'tradebook': '/api/v1/tradebook',
            'holdings': '/api/v1/holdings',
            'place_order': '/api/v1/placeorder',
            'modify_order': '/api/v1/modifyorder',
            'cancel_order': '/api/v1/cancelorder',
            'order_status': '/api/v1/orderstatus',
            'close_position': '/api/v1/closeposition',
            'open_position': '/api/v1/openposition',

            # Market Data APIs
            'quotes': '/api/v1/quotes',
            'depth': '/api/v1/depth',
            'history': '/api/v1/history',
            'intervals': '/api/v1/intervals',
            'expiry': '/api/v1/expiry',
            'search': '/api/v1/search',
            'symbol_master': '/api/v1/symbols',

            # Advanced Order APIs
            'basket_order': '/api/v1/basketorder',
            'split_order': '/api/v1/splitorder',
            'bracket_order': '/api/v1/bracketorder',
            'cover_order': '/api/v1/coverorder',
            'amo_order': '/api/v1/amorder',  # After Market Order

            # Portfolio & Risk Management
            'portfolio': '/api/v1/portfolio',
            'risk_limits': '/api/v1/limits',
            'margin_calculator': '/api/v1/margin',
            'pnl_analysis': '/api/v1/pnl',

            # Real-time Data
            'ticker': '/api/v1/ticker',
            'websocket': '/ws',

            # System & Utility
            'ping': '/api/v1/ping',
            'status': '/api/v1/status',
            'broker_info': '/api/v1/broker',
            'user_profile': '/api/v1/profile',

            # Analytics & Reports
            'analytics': '/api/v1/analytics',
            'reports': '/api/v1/reports',
            'trade_analysis': '/api/v1/tradeanalysis',
            'performance': '/api/v1/performance',

            # Strategy & Automation
            'strategies': '/api/v1/strategies',
            'alerts': '/api/v1/alerts',
            'notifications': '/api/v1/notifications',

            # Market Utilities
            'market_status': '/api/v1/marketstatus',
            'market_holidays': '/api/v1/holidays',
            'corporate_actions': '/api/v1/corporateactions',
            'option_chain': '/api/v1/optionchain',
            'oi_analysis': '/api/v1/oi',

            # Multi-broker Support
            'broker_switch': '/api/v1/switchbroker',
            'multi_broker': '/api/v1/multibroker',

            # Backup & Sync
            'backup': '/api/v1/backup',
            'sync': '/api/v1/sync',
            'export': '/api/v1/export',
            'import': '/api/v1/import'
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()

    async def connect(self):
        """Establish session connection"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'FortressTradingSystem/1.0'
                },
                timeout=aiohttp.ClientTimeout(total=30)
            )
            logger.info("OpenAlgo API session connected")

    async def disconnect(self):
        """Close session connection"""
        if self.websocket_session and not self.websocket_session.closed:
            await self.websocket_session.close()
            self.websocket_connected = False

        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("OpenAlgo API session disconnected")

    def _get_cache_key(self, endpoint: str, params: Dict = None) -> str:
        """Generate cache key for request"""
        key = endpoint
        if params:
            key += f"_{json.dumps(params, sort_keys=True)}"
        return key

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid"""
        if cache_key not in self.data_cache:
            return False

        cache_time, _ = self.data_cache[cache_key]
        return datetime.now() - cache_time < self.cache_timeout

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if valid"""
        if self._is_cache_valid(cache_key):
            _, data = self.data_cache[cache_key]
            return data
        return None

    def _set_cache(self, cache_key: str, data: Any):
        """Set data in cache"""
        self.data_cache[cache_key] = (datetime.now(), data)

    async def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None, use_cache: bool = True) -> APIResponse:
        """Make HTTP request to OpenAlgo API"""
        if not self.session:
            await self.connect()

        # Check cache first
        cache_key = self._get_cache_key(endpoint, params)
        if method == 'GET' and use_cache and self._is_cache_valid(cache_key):
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return APIResponse(success=True, data=cached_data, status_code=200)

        url = urljoin(self.base_url, endpoint)

        try:
            async with self.session.request(method, url, json=data, params=params) as response:
                response_data = await response.json()

                if response.status == 200:
                    if method == 'GET' and use_cache:
                        self._set_cache(cache_key, response_data)
                    return APIResponse(success=True, data=response_data, status_code=response.status)
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    return APIResponse(success=False, error=error_msg, status_code=response.status)

        except Exception as e:
            logger.error(f"Request failed: {e}")
            return APIResponse(success=False, error=str(e))

    # Core Trading APIs
    async def get_funds(self) -> APIResponse:
        """Get account funds and limits"""
        return await self._make_request('GET', self.endpoints['funds'])

    async def get_orderbook(self, status: str = None, symbol: str = None) -> APIResponse:
        """Get order book with optional filtering"""
        params = {}
        if status:
            params['status'] = status
        if symbol:
            params['symbol'] = symbol
        return await self._make_request('GET', self.endpoints['orderbook'], params=params)

    async def get_positionbook(self, symbol: str = None) -> APIResponse:
        """Get position book"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self._make_request('GET', self.endpoints['positionbook'], params=params)

    async def get_tradebook(self, from_date: str = None, to_date: str = None) -> APIResponse:
        """Get trade book with date filtering"""
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        return await self._make_request('GET', self.endpoints['tradebook'], params=params)

    async def get_holdings(self, segment: str = None) -> APIResponse:
        """Get holdings"""
        params = {}
        if segment:
            params['segment'] = segment
        return await self._make_request('GET', self.endpoints['holdings'], params=params)

    async def place_order(self, symbol: str, quantity: int, order_type: str, price: float = None,
                         side: str = 'buy', product: str = 'MIS', validity: str = 'DAY',
                         disclosed_quantity: int = None, trigger_price: float = None,
                         tag: str = None) -> APIResponse:
        """Place a new order"""
        order_data = {
            'symbol': symbol,
            'quantity': quantity,
            'order_type': order_type,
            'side': side,
            'product': product,
            'validity': validity
        }

        if price is not None:
            order_data['price'] = price
        if disclosed_quantity is not None:
            order_data['disclosed_quantity'] = disclosed_quantity
        if trigger_price is not None:
            order_data['trigger_price'] = trigger_price
        if tag:
            order_data['tag'] = tag

        return await self._make_request('POST', self.endpoints['place_order'], data=order_data)

    async def modify_order(self, order_id: str, quantity: int = None, price: float = None,
                          order_type: str = None, trigger_price: float = None) -> APIResponse:
        """Modify an existing order"""
        modify_data = {'order_id': order_id}

        if quantity is not None:
            modify_data['quantity'] = quantity
        if price is not None:
            modify_data['price'] = price
        if order_type is not None:
            modify_data['order_type'] = order_type
        if trigger_price is not None:
            modify_data['trigger_price'] = trigger_price

        return await self._make_request('PUT', self.endpoints['modify_order'], data=modify_data)

    async def cancel_order(self, order_id: str) -> APIResponse:
        """Cancel an order"""
        return await self._make_request('DELETE', self.endpoints['cancel_order'], data={'order_id': order_id})

    async def get_order_status(self, order_id: str) -> APIResponse:
        """Get order status"""
        return await self._make_request('GET', f"{self.endpoints['order_status']}/{order_id}")

    # Market Data APIs
    async def get_quotes(self, symbols: Union[str, List[str]]) -> APIResponse:
        """Get real-time quotes"""
        if isinstance(symbols, list):
            symbols = ','.join(symbols)
        params = {'symbols': symbols}
        return await self._make_request('GET', self.endpoints['quotes'], params=params)

    async def get_depth(self, symbol: str) -> APIResponse:
        """Get market depth for a symbol"""
        params = {'symbol': symbol}
        return await self._make_request('GET', self.endpoints['depth'], params=params)

    async def get_history(self, symbol: str, interval: str, from_date: str = None, to_date: str = None,
                         continuous: bool = False) -> APIResponse:
        """Get historical data"""
        params = {
            'symbol': symbol,
            'interval': interval
        }
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if continuous:
            params['continuous'] = 'true'

        return await self._make_request('GET', self.endpoints['history'], params=params)

    async def get_intervals(self) -> APIResponse:
        """Get available intervals"""
        return await self._make_request('GET', self.endpoints['intervals'])

    async def get_expiry(self, symbol: str, instrument: str = 'OPT') -> APIResponse:
        """Get expiry dates"""
        params = {'symbol': symbol, 'instrument': instrument}
        return await self._make_request('GET', self.endpoints['expiry'], params=params)

    async def search_symbols(self, query: str, segment: str = None, exchange: str = None) -> APIResponse:
        """Search for symbols"""
        params = {'query': query}
        if segment:
            params['segment'] = segment
        if exchange:
            params['exchange'] = exchange
        return await self._make_request('GET', self.endpoints['search'], params=params)

    # Advanced Order APIs
    async def place_basket_order(self, orders: List[Dict]) -> APIResponse:
        """Place multiple orders in a basket"""
        return await self._make_request('POST', self.endpoints['basket_order'], data={'orders': orders})

    async def split_order(self, symbol: str, total_quantity: int, split_count: int, **kwargs) -> APIResponse:
        """Split a large order into multiple smaller orders"""
        split_data = {
            'symbol': symbol,
            'total_quantity': total_quantity,
            'split_count': split_count
        }
        split_data.update(kwargs)
        return await self._make_request('POST', self.endpoints['split_order'], data=split_data)

    async def place_bracket_order(self, symbol: str, quantity: int, entry_price: float,
                                 target_price: float, stoploss_price: float, **kwargs) -> APIResponse:
        """Place a bracket order"""
        bo_data = {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': entry_price,
            'target_price': target_price,
            'stoploss_price': stoploss_price
        }
        bo_data.update(kwargs)
        return await self._make_request('POST', self.endpoints['bracket_order'], data=bo_data)

    async def place_cover_order(self, symbol: str, quantity: int, price: float,
                               trigger_price: float, **kwargs) -> APIResponse:
        """Place a cover order"""
        co_data = {
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'trigger_price': trigger_price
        }
        co_data.update(kwargs)
        return await self._make_request('POST', self.endpoints['cover_order'], data=co_data)

    async def place_amo_order(self, symbol: str, quantity: int, order_type: str,
                             price: float = None, **kwargs) -> APIResponse:
        """Place an After Market Order"""
        amo_data = {
            'symbol': symbol,
            'quantity': quantity,
            'order_type': order_type
        }
        if price is not None:
            amo_data['price'] = price
        amo_data.update(kwargs)
        return await self._make_request('POST', self.endpoints['amo_order'], data=amo_data)

    # Portfolio & Risk Management
    async def get_portfolio(self, detailed: bool = False) -> APIResponse:
        """Get portfolio summary"""
        params = {'detailed': 'true'} if detailed else {}
        return await self._make_request('GET', self.endpoints['portfolio'], params=params)

    async def get_risk_limits(self) -> APIResponse:
        """Get risk limits"""
        return await self._make_request('GET', self.endpoints['risk_limits'])

    async def calculate_margin(self, orders: List[Dict]) -> APIResponse:
        """Calculate margin requirement for orders"""
        return await self._make_request('POST', self.endpoints['margin_calculator'], data={'orders': orders})

    async def get_pnl_analysis(self, from_date: str = None, to_date: str = None,
                              segment: str = None) -> APIResponse:
        """Get P&L analysis"""
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if segment:
            params['segment'] = segment
        return await self._make_request('GET', self.endpoints['pnl_analysis'], params=params)

    # Real-time Data & WebSocket
    async def connect_websocket(self, symbols: List[str] = None):
        """Connect to WebSocket for real-time data"""
        try:
            ws_url = urljoin(self.base_url.replace('http', 'ws'), self.endpoints['websocket'])

            # Add authentication
            ws_url += f"?token={self.api_key}"
            if symbols:
                ws_url += f"&symbols={','.join(symbols)}"

            self.websocket_session = await aiohttp.ClientSession().ws_connect(ws_url)
            self.websocket_connected = True

            logger.info("WebSocket connected for real-time data")

            # Start listening for messages
            asyncio.create_task(self._websocket_listener())

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.websocket_connected = False

    async def _websocket_listener(self):
        """Listen for WebSocket messages"""
        try:
            async for msg in self.websocket_session:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_websocket_message(data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {msg.data}")
                    break
        except Exception as e:
            logger.error(f"WebSocket listener error: {e}")
        finally:
            self.websocket_connected = False

    async def _handle_websocket_message(self, data: Dict):
        """Handle incoming WebSocket messages"""
        try:
            # Update cache with real-time data
            symbol = data.get('symbol')
            if symbol:
                cache_key = f"ticker_{symbol}"
                self._set_cache(cache_key, data)

                # Notify subscribers
                for callback in self.subscriptions:
                    await callback(data)

        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

    def subscribe_websocket(self, callback):
        """Subscribe to WebSocket data"""
        self.subscriptions.add(callback)

    def unsubscribe_websocket(self, callback):
        """Unsubscribe from WebSocket data"""
        self.subscriptions.discard(callback)

    async def get_ticker(self, symbols: Union[str, List[str]]) -> APIResponse:
        """Get real-time ticker data"""
        if isinstance(symbols, list):
            symbols = ','.join(symbols)
        params = {'symbols': symbols}
        return await self._make_request('GET', self.endpoints['ticker'], params=params)

    # System & Utility
    async def ping(self) -> APIResponse:
        """Ping the API server"""
        return await self._make_request('GET', self.endpoints['ping'])

    async def get_status(self) -> APIResponse:
        """Get system status"""
        return await self._make_request('GET', self.endpoints['status'])

    async def get_broker_info(self) -> APIResponse:
        """Get broker information"""
        return await self._make_request('GET', self.endpoints['broker_info'])

    async def get_user_profile(self) -> APIResponse:
        """Get user profile"""
        return await self._make_request('GET', self.endpoints['user_profile'])

    # Analytics & Reports
    async def get_analytics(self, type: str = 'trading', period: str = '1M') -> APIResponse:
        """Get analytics data"""
        params = {'type': type, 'period': period}
        return await self._make_request('GET', self.endpoints['analytics'], params=params)

    async def get_reports(self, report_type: str, from_date: str = None, to_date: str = None) -> APIResponse:
        """Get reports"""
        params = {'type': report_type}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        return await self._make_request('GET', self.endpoints['reports'], params=params)

    async def get_trade_analysis(self, symbol: str = None, from_date: str = None, to_date: str = None) -> APIResponse:
        """Get trade analysis"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        return await self._make_request('GET', self.endpoints['trade_analysis'], params=params)

    async def get_performance(self, period: str = '1M', benchmark: str = None) -> APIResponse:
        """Get performance metrics"""
        params = {'period': period}
        if benchmark:
            params['benchmark'] = benchmark
        return await self._make_request('GET', self.endpoints['performance'], params=params)

    # Strategy & Automation
    async def get_strategies(self, active_only: bool = True) -> APIResponse:
        """Get available strategies"""
        params = {'active': 'true'} if active_only else {}
        return await self._make_request('GET', self.endpoints['strategies'], params=params)

    async def get_alerts(self, type: str = None, status: str = None) -> APIResponse:
        """Get alerts"""
        params = {}
        if type:
            params['type'] = type
        if status:
            params['status'] = status
        return await self._make_request('GET', self.endpoints['alerts'], params=params)

    async def get_notifications(self, unread_only: bool = False) -> APIResponse:
        """Get notifications"""
        params = {'unread': 'true'} if unread_only else {}
        return await self._make_request('GET', self.endpoints['notifications'], params=params)

    # Market Utilities
    async def get_market_status(self, exchange: str = None) -> APIResponse:
        """Get market status"""
        params = {}
        if exchange:
            params['exchange'] = exchange
        return await self._make_request('GET', self.endpoints['market_status'], params=params)

    async def get_market_holidays(self, year: int = None) -> APIResponse:
        """Get market holidays"""
        params = {}
        if year:
            params['year'] = year
        return await self._make_request('GET', self.endpoints['market_holidays'], params=params)

    async def get_corporate_actions(self, symbol: str = None, from_date: str = None, to_date: str = None) -> APIResponse:
        """Get corporate actions"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        return await self._make_request('GET', self.endpoints['corporate_actions'], params=params)

    async def get_option_chain(self, symbol: str, expiry: str = None) -> APIResponse:
        """Get option chain data"""
        params = {'symbol': symbol}
        if expiry:
            params['expiry'] = expiry
        return await self._make_request('GET', self.endpoints['option_chain'], params=params)

    async def get_oi_analysis(self, symbol: str, expiry: str = None) -> APIResponse:
        """Get Open Interest analysis"""
        params = {'symbol': symbol}
        if expiry:
            params['expiry'] = expiry
        return await self._make_request('GET', self.endpoints['oi_analysis'], params=params)

    # Multi-broker Support
    async def switch_broker(self, broker: str) -> APIResponse:
        """Switch to different broker"""
        return await self._make_request('POST', self.endpoints['broker_switch'], data={'broker': broker})

    async def get_multi_broker_status(self) -> APIResponse:
        """Get status of all connected brokers"""
        return await self._make_request('GET', self.endpoints['multi_broker'])

    # Backup & Sync
    async def create_backup(self, backup_type: str = 'full') -> APIResponse:
        """Create backup"""
        return await self._make_request('POST', self.endpoints['backup'], data={'type': backup_type})

    async def sync_data(self, sync_type: str = 'all') -> APIResponse:
        """Sync data"""
        return await self._make_request('POST', self.endpoints['sync'], data={'type': sync_type})

    async def export_data(self, export_type: str, format: str = 'json') -> APIResponse:
        """Export data"""
        return await self._make_request('POST', self.endpoints['export'], data={'type': export_type, 'format': format})

    async def import_data(self, import_type: str, data: Dict) -> APIResponse:
        """Import data"""
        return await self._make_request('POST', self.endpoints['import'], data={'type': import_type, 'data': data})

class FortressOpenAlgoIntegration:
    """Integration layer between Fortress Trading System and OpenAlgo"""

    def __init__(self, api_key: str, base_url: str = "http://localhost:5000"):
        self.api_key = api_key
        self.base_url = base_url
        self.integration = OpenAlgoCompleteIntegration(api_key, base_url)
        self.connected = False

    async def connect(self):
        """Connect to OpenAlgo"""
        await self.integration.connect()

        # Test connection
        response = await self.integration.ping()
        if response.success:
            self.connected = True
            logger.info("Fortress-OpenAlgo integration connected")
        else:
            logger.error(f"Failed to connect to OpenAlgo: {response.error}")

        return self.connected

    async def disconnect(self):
        """Disconnect from OpenAlgo"""
        await self.integration.disconnect()
        self.connected = False
        logger.info("Fortress-OpenAlgo integration disconnected")

    async def get_account_summary(self) -> Dict:
        """Get complete account summary"""
        summary = {}

        # Get funds
        funds_response = await self.integration.get_funds()
        if funds_response.success:
            summary['funds'] = funds_response.data

        # Get holdings
        holdings_response = await self.integration.get_holdings()
        if holdings_response.success:
            summary['holdings'] = holdings_response.data

        # Get positions
        positions_response = await self.integration.get_positionbook()
        if positions_response.success:
            summary['positions'] = positions_response.data

        # Get orders
        orders_response = await self.integration.get_orderbook()
        if orders_response.success:
            summary['orders'] = orders_response.data

        return summary

    async def execute_strategy_order(self, signal: Dict) -> APIResponse:
        """Execute order based on strategy signal"""
        try:
            # Validate signal
            required_fields = ['symbol', 'side', 'quantity', 'order_type']
            if not all(field in signal for field in required_fields):
                return APIResponse(success=False, error="Missing required fields in signal")

            # Place order
            response = await self.integration.place_order(
                symbol=signal['symbol'],
                side=signal['side'],
                quantity=signal['quantity'],
                order_type=signal['order_type'],
                price=signal.get('price'),
                product=signal.get('product', 'MIS'),
                validity=signal.get('validity', 'DAY'),
                tag=signal.get('strategy', 'fortress')
            )

            return response

        except Exception as e:
            logger.error(f"Strategy order execution failed: {e}")
            return APIResponse(success=False, error=str(e))

    async def get_real_time_data(self, symbols: List[str]) -> Dict:
        """Get real-time market data for symbols"""
        data = {}

        # Get quotes
        quotes_response = await self.integration.get_quotes(symbols)
        if quotes_response.success:
            data['quotes'] = quotes_response.data

        # Get depth for each symbol
        for symbol in symbols:
            depth_response = await self.integration.get_depth(symbol)
            if depth_response.success:
                if 'depth' not in data:
                    data['depth'] = {}
                data['depth'][symbol] = depth_response.data

        return data

    async def get_market_scanner_data(self, filters: Dict) -> List[Dict]:
        """Get market scanner data with filters"""
        scanner_data = []

        # Search symbols based on filters
        if 'query' in filters:
            search_response = await self.integration.search_symbols(
                query=filters['query'],
                segment=filters.get('segment'),
                exchange=filters.get('exchange')
            )

            if search_response.success:
                symbols = search_response.data.get('symbols', [])

                # Get detailed data for each symbol
                for symbol_info in symbols:
                    symbol = symbol_info['symbol']

                    # Get quotes
                    quotes_response = await self.integration.get_quotes(symbol)
                    if quotes_response.success:
                        symbol_data = {
                            'symbol': symbol,
                            'info': symbol_info,
                            'quote': quotes_response.data
                        }
                        scanner_data.append(symbol_data)

        return scanner_data

# Test function
async def test_complete_integration():
    """Test the complete integration"""
    import os

    # Get API key from environment or secure storage
    api_key = os.getenv('OPENALGO_API_KEY', 'your_api_key_here')

    async with FortressOpenAlgoIntegration(api_key) as integration:
        # Test connection
        connected = await integration.connect()
        print(f"Connected: {connected}")

        if connected:
            # Test account summary
            summary = await integration.get_account_summary()
            print(f"Account summary keys: {list(summary.keys())}")

            # Test market data
            test_symbols = ['NSE:RELIANCE', 'NSE:TCS']
            market_data = await integration.get_real_time_data(test_symbols)
            print(f"Market data for {len(test_symbols)} symbols retrieved")

            # Test scanner
            scanner_data = await integration.get_market_scanner_data({'query': 'RELIANCE'})
            print(f"Scanner found {len(scanner_data)} results")

if __name__ == "__main__":
    asyncio.run(test_complete_integration())
