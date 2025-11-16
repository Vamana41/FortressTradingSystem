
import numba as nb
import numpy as np
from typing import List, Dict, Any
import orjson
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Numba-optimized functions for high-performance data processing
@nb.njit(cache=True, fastmath=True)
def calculate_moving_average(prices: np.ndarray, window: int) -> np.ndarray:
    """Optimized moving average calculation using Numba"""
    n = len(prices)
    result = np.empty(n - window + 1)
    for i in range(window - 1, n):
        result[i - window + 1] = np.mean(prices[i - window + 1:i + 1])
    return result

@nb.njit(cache=True, fastmath=True)
def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Optimized RSI calculation"""
    n = len(prices)
    rsi = np.empty(n - period)

    for i in range(period, n):
        gains = []
        losses = []

        for j in range(i - period + 1, i + 1):
            change = prices[j] - prices[j - 1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(-change)

        avg_gain = np.mean(np.array(gains)) if gains else 0
        avg_loss = np.mean(np.array(losses)) if losses else 0

        if avg_loss == 0:
            rsi[i - period] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i - period] = 100 - (100 / (1 + rs))

    return rsi

@nb.njit(cache=True, parallel=True)
def batch_calculate_indicators(data: np.ndarray, windows: List[int]) -> Dict[str, np.ndarray]:
    """Batch calculate multiple indicators in parallel"""
    results = {}

    for window in windows:
        # Moving averages
        ma_key = f"ma_{window}"
        results[ma_key] = calculate_moving_average(data, window)

        # RSI for specific windows
        if window in [14, 21]:
            rsi_key = f"rsi_{window}"
            results[rsi_key] = calculate_rsi(data, window)

    return results

class AsyncDataProcessor:
    """High-performance async data processor"""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)

    async def process_market_data_batch(self, data_batch: List[Dict]) -> List[Dict]:
        """Process market data batch asynchronously"""
        loop = asyncio.get_event_loop()

        # Use orjson for fast JSON serialization
        tasks = []
        for data in data_batch:
            task = loop.run_in_executor(
                self.executor,
                self._process_single_data_item,
                orjson.dumps(data)
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return [orjson.loads(result) for result in results]

    def _process_single_data_item(self, data_json: bytes) -> bytes:
        """Process single data item (CPU-bound work)"""
        data = orjson.loads(data_json)

        # Add technical indicators
        if 'price' in data and isinstance(data['price'], (int, float)):
            # Simulate indicator calculation
            data['processed'] = True
            data['timestamp'] = int(time.time() * 1000)

        return orjson.dumps(data)

    def optimize_memory_usage(self):
        """Optimize memory usage for large datasets"""
        import gc
        import psutil

        # Force garbage collection
        gc.collect()

        # Log memory usage
        memory = psutil.virtual_memory()
        self.logger.info(f"Memory usage: {memory.percent}%")

        return memory.percent

class WebSocketOptimizer:
    """Optimize WebSocket connections for high-frequency data"""

    def __init__(self):
        self.connections = {}
        self.message_queue = asyncio.Queue(maxsize=10000)
        self.logger = logging.getLogger(__name__)

    async def create_optimized_connection(self, url: str, headers: Dict = None):
        """Create optimized WebSocket connection"""
        import aiohttp

        connector = aiohttp.TCPConnector(
            limit=100,  # Connection pool limit
            limit_per_host=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30
        )

        session = aiohttp.ClientSession(
            connector=connector,
            json_serialize=orjson.dumps
        )

        ws = await session.ws_connect(
            url,
            headers=headers,
            heartbeat=30,
            autoping=True,
            compress=15,  # Enable compression
            max_msg_size=1024*1024  # 1MB max message size
        )

        self.connections[url] = {
            'session': session,
            'websocket': ws,
            'created_at': time.time()
        }

        return ws

    async def send_optimized_message(self, url: str, message: Dict):
        """Send optimized message through WebSocket"""
        if url in self.connections:
            ws = self.connections[url]['websocket']

            # Use orjson for fast serialization
            await ws.send_bytes(orjson.dumps(message))

    async def close_all_connections(self):
        """Close all WebSocket connections gracefully"""
        for url, conn in self.connections.items():
            try:
                await conn['websocket'].close()
                await conn['session'].close()
                self.logger.info(f"Closed connection to {url}")
            except Exception as e:
                self.logger.error(f"Error closing connection to {url}: {e}")

        self.connections.clear()

# Global instances for easy import
data_processor = AsyncDataProcessor()
ws_optimizer = WebSocketOptimizer()
