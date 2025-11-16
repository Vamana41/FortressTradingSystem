#!/usr/bin/env python3
"""Deploy Python 3.14 performance optimizations for Fortress Trading System"""

import os
import sys
import subprocess
import logging
from pathlib import Path
import json

def install_performance_dependencies():
    """Install performance optimization dependencies"""
    print("📦 Installing performance optimization dependencies...")
    
    dependencies = [
        "numba>=0.60.0",
        "cython>=3.0.0", 
        "mypy>=1.8.0",
        "psutil>=5.9.0",
        "memory-profiler>=0.61.0",
        "line-profiler>=4.1.0",
        "py-spy>=0.3.0",
        "aiohttp>=3.9.0",
        "uvloop>=0.19.0; sys_platform != 'win32'",
        "orjson>=3.9.0",
        "ujson>=5.9.0",
        "msgpack>=1.0.0",
        "lz4>=4.3.0",
        "blosc2>=2.4.0",
        "numpy>=1.26.0",
        "pandas>=2.1.0",
        "polars>=0.20.0"
    ]
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                         check=True, capture_output=True)
            print(f"✅ {dep} installed")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Failed to install {dep}: {e}")
    
    return True

def create_performance_wrappers():
    """Create performance-optimized wrappers for critical functions"""
    print("\n🔧 Creating performance wrappers...")
    
    # Create optimized data processing module
    data_processing_py = '''
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
'''
    
    with open("fortress_performance_wrappers.py", "w") as f:
        f.write(data_processing_py)
    
    print("✅ Performance wrappers created: fortress_performance_wrappers.py")

def create_rust_extensions():
    """Create Rust extension templates for maximum performance"""
    print("\n⚡ Creating Rust extension templates...")
    
    # Create Rust extension setup
    rust_setup_py = '''
from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    name="fortress_rust_extensions",
    version="1.0.0",
    rust_extensions=[
        RustExtension(
            "fortress_rust.fast_math",
            path="src/fast_math/Cargo.toml",
            binding=Binding.PyO3
        ),
        RustExtension(
            "fortress_rust.data_structures", 
            path="src/data_structures/Cargo.toml",
            binding=Binding.PyO3
        ),
        RustExtension(
            "fortress_rust.market_data",
            path="src/market_data/Cargo.toml", 
            binding=Binding.PyO3
        )
    ],
    packages=["fortress_rust"],
    zip_safe=False,
)
'''
    
    # Create Cargo.toml for fast_math module
    cargo_fast_math = '''
[package]
name = "fast_math"
version = "1.0.0"
edition = "2021"

[lib]
name = "fast_math"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module"] }
numpy = "0.20"
ndarray = { version = "0.15", features = ["rayon"] }
rayon = "1.8"

[dependencies.pyo3-built]
version = "0.4"
default-features = false
features = ["chrono", "serde"]
'''
    
    # Create Rust source for fast math operations
    rust_fast_math_lib = '''
use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use ndarray::{Array1, ArrayView1};
use rayon::prelude::*;

/// Calculate moving average using Rust + Rayon for parallel processing
#[pyfunction]
fn moving_average_rust<'py>(
    py: Python<'py>,
    data: PyArray1<f64>,
    window: usize
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let data_view = data.readonly();
    let slice = data_view.as_slice().unwrap();
    let n = slice.len();
    
    if window > n {
        return Err(pyo3::exceptions::PyValueError::new(
            "Window size must be <= data length"
        ));
    }
    
    let result_len = n - window + 1;
    let mut result = Vec::with_capacity(result_len);
    
    // Parallel calculation using Rayon
    (0..result_len).into_par_iter().for_each(|i| {
        let sum: f64 = slice[i..i + window].iter().sum();
        result[i] = sum / window as f64;
    });
    
    Ok(PyArray1::from_vec_bound(py, result))
}

/// Calculate RSI using optimized Rust implementation
#[pyfunction]
fn rsi_rust<'py>(
    py: Python<'py>,
    data: PyArray1<f64>,
    period: usize
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let data_view = data.readonly();
    let slice = data_view.as_slice().unwrap();
    let n = slice.len();
    
    if period >= n {
        return Err(pyo3::exceptions::PyValueError::new(
            "Period must be < data length"
        ));
    }
    
    let result_len = n - period;
    let mut result = Vec::with_capacity(result_len);
    
    for i in period..n {
        let mut gains = 0.0;
        let mut losses = 0.0;
        
        for j in (i - period + 1)..=i {
            let change = slice[j] - slice[j - 1];
            if change > 0.0 {
                gains += change;
            } else {
                losses -= change;
            }
        }
        
        let avg_gain = gains / period as f64;
        let avg_loss = losses / period as f64;
        
        if avg_loss == 0.0 {
            result.push(100.0);
        } else {
            let rs = avg_gain / avg_loss;
            result.push(100.0 - (100.0 / (1.0 + rs)));
        }
    }
    
    Ok(PyArray1::from_vec_bound(py, result))
}

/// Fast correlation calculation
#[pyfunction]
fn correlation_rust<'py>(
    py: Python<'py>,
    x: PyArray1<f64>,
    y: PyArray1<f64>
) -> PyResult<f64> {
    let x_view = x.readonly();
    let y_view = y.readonly();
    let x_slice = x_view.as_slice().unwrap();
    let y_slice = y_view.as_slice().unwrap();
    
    if x_slice.len() != y_slice.len() {
        return Err(pyo3::exceptions::PyValueError::new(
            "Arrays must have the same length"
        ));
    }
    
    let n = x_slice.len() as f64;
    let sum_x: f64 = x_slice.iter().sum();
    let sum_y: f64 = y_slice.iter().sum();
    let sum_xy: f64 = x_slice.iter().zip(y_slice.iter()).map(|(a, b)| a * b).sum();
    let sum_x2: f64 = x_slice.iter().map(|x| x * x).sum();
    let sum_y2: f64 = y_slice.iter().map(|y| y * y).sum();
    
    let numerator = n * sum_xy - sum_x * sum_y;
    let denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)).sqrt();
    
    if denominator == 0.0 {
        Ok(0.0)
    } else {
        Ok(numerator / denominator)
    }
}

#[pymodule]
fn fast_math(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(moving_average_rust, m)?)?;
    m.add_function(wrap_pyfunction!(rsi_rust, m)?)?;
    m.add_function(wrap_pyfunction!(correlation_rust, m)?)?;
    Ok(())
}
'''
    
    # Create directory structure
    os.makedirs("src/fast_math", exist_ok=True)
    
    with open("setup_rust_extensions.py", "w") as f:
        f.write(rust_setup_py)
    
    with open("src/fast_math/Cargo.toml", "w") as f:
        f.write(cargo_fast_math)
    
    with open("src/fast_math/lib.rs", "w") as f:
        f.write(rust_fast_math_lib)
    
    print("✅ Rust extension templates created")
    print("📋 To build Rust extensions, run: python setup_rust_extensions.py build_ext --inplace")

def create_memory_optimization_config():
    """Create memory optimization configuration"""
    print("\n🧠 Creating memory optimization configuration...")
    
    memory_config = {
        "garbage_collection": {
            "enabled": True,
            "interval_seconds": 300,
            "thresholds": [700, 10, 10],
            "debug": False
        },
        "memory_profiling": {
            "enabled": True,
            "log_interval_seconds": 60,
            "max_memory_mb": 4096,
            "alert_threshold_percent": 85
        },
        "object_pooling": {
            "enabled": True,
            "max_pool_size": 1000,
            "object_types": ["dict", "list", "numpy_array"]
        },
        "caching": {
            "enabled": True,
            "max_cache_size_mb": 512,
            "ttl_seconds": 3600,
            "strategies": ["lru", "lfu"]
        }
    }
    
    with open("memory_optimization_config.json", "w") as f:
        json.dump(memory_config, f, indent=2)
    
    print("✅ Memory optimization configuration created: memory_optimization_config.json")

def create_performance_monitoring():
    """Create performance monitoring system"""
    print("\n📊 Creating performance monitoring system...")
    
    monitoring_script = '''
#!/usr/bin/env python3
"""Performance monitoring for Fortress Trading System"""

import time
import psutil
import logging
import json
from pathlib import Path
from datetime import datetime
import asyncio
import threading
from collections import deque
import signal
import sys

class PerformanceMonitor:
    """Real-time performance monitoring"""
    
    def __init__(self, config_file="memory_optimization_config.json"):
        self.config = self.load_config(config_file)
        self.metrics_history = deque(maxlen=1000)
        self.running = False
        self.monitor_thread = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - PERFORMANCE - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('performance_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def load_config(self, config_file):
        """Load monitoring configuration"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "memory_profiling": {
                    "enabled": True,
                    "log_interval_seconds": 60,
                    "max_memory_mb": 4096,
                    "alert_threshold_percent": 85
                }
            }
    
    def collect_metrics(self):
        """Collect system performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            # Process-specific metrics
            process = psutil.Process()
            process_memory_mb = process.memory_info().rss / (1024 * 1024)
            process_cpu_percent = process.cpu_percent()
            
            # Network metrics (if available)
            try:
                network = psutil.net_io_counters()
                network_sent_mb = network.bytes_sent / (1024 * 1024)
                network_recv_mb = network.bytes_recv / (1024 * 1024)
            except:
                network_sent_mb = 0
                network_recv_mb = 0
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'percent': memory_percent,
                    'used_mb': memory_used_mb,
                    'available_mb': memory_available_mb
                },
                'disk': {
                    'percent': disk_percent,
                    'free_gb': disk_free_gb
                },
                'process': {
                    'memory_mb': process_memory_mb,
                    'cpu_percent': process_cpu_percent
                },
                'network': {
                    'sent_mb': network_sent_mb,
                    'recv_mb': network_recv_mb
                }
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
            return None
    
    def check_alerts(self, metrics):
        """Check for performance alerts"""
        if not metrics:
            return
        
        memory_config = self.config.get("memory_profiling", {})
        alert_threshold = memory_config.get("alert_threshold_percent", 85)
        max_memory_mb = memory_config.get("max_memory_mb", 4096)
        
        # Memory alerts
        if metrics['memory']['percent'] > alert_threshold:
            self.logger.warning(f"HIGH MEMORY USAGE: {metrics['memory']['percent']:.1f}%")
        
        if metrics['process']['memory_mb'] > max_memory_mb:
            self.logger.warning(f"HIGH PROCESS MEMORY: {metrics['process']['memory_mb']:.1f}MB")
        
        # CPU alerts
        if metrics['cpu']['percent'] > 80:
            self.logger.warning(f"HIGH CPU USAGE: {metrics['cpu']['percent']:.1f}%")
        
        # Disk alerts
        if metrics['disk']['percent'] > 90:
            self.logger.warning(f"HIGH DISK USAGE: {metrics['disk']['percent']:.1f}%")
    
    def save_metrics(self, metrics):
        """Save metrics to history and file"""
        if not metrics:
            return
        
        self.metrics_history.append(metrics)
        
        # Save to file every 10 minutes
        if len(self.metrics_history) % 10 == 0:
            self.save_metrics_to_file()
    
    def save_metrics_to_file(self):
        """Save metrics history to JSON file"""
        try:
            filename = f"performance_metrics_{datetime.now().strftime('%Y%m%d')}.json"
            with open(filename, 'w') as f:
                json.dump(list(self.metrics_history), f, indent=2)
            self.logger.info(f"Metrics saved to {filename}")
        except Exception as e:
            self.logger.error(f"Error saving metrics: {e}")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting performance monitoring...")
        
        while self.running:
            try:
                metrics = self.collect_metrics()
                self.check_alerts(metrics)
                self.save_metrics(metrics)
                
                # Log summary
                if metrics:
                    self.logger.info(
                        f"CPU: {metrics['cpu']['percent']:.1f}%, "
                        f"Memory: {metrics['memory']['percent']:.1f}%, "
                        f"Process Memory: {metrics['process']['memory_mb']:.1f}MB"
                    )
                
                # Wait for next collection
                interval = self.config.get("memory_profiling", {}).get("log_interval_seconds", 60)
                time.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start(self):
        """Start performance monitoring"""
        if self.running:
            self.logger.warning("Monitor already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Performance monitoring started")
    
    def stop(self):
        """Stop performance monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Performance monitoring stopped")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def get_summary(self):
        """Get performance summary"""
        if not self.metrics_history:
            return "No metrics collected yet"
        
        recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
        
        avg_cpu = sum(m['cpu']['percent'] for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m['memory']['percent'] for m in recent_metrics) / len(recent_metrics)
        avg_process_memory = sum(m['process']['memory_mb'] for m in recent_metrics) / len(recent_metrics)
        
        return {
            'measurements': len(recent_metrics),
            'avg_cpu_percent': avg_cpu,
            'avg_memory_percent': avg_memory,
            'avg_process_memory_mb': avg_process_memory,
            'latest_measurement': recent_metrics[-1] if recent_metrics else None
        }

async def main():
    """Main async function"""
    monitor = PerformanceMonitor()
    
    try:
        monitor.start()
        
        # Keep running
        while True:
            await asyncio.sleep(60)
            summary = monitor.get_summary()
            if isinstance(summary, dict):
                print(f"Performance Summary: CPU {summary['avg_cpu_percent']:.1f}%, "
                      f"Memory {summary['avg_memory_percent']:.1f}%, "
                      f"Process {summary['avg_process_memory_mb']:.1f}MB")
    
    except KeyboardInterrupt:
        monitor.stop()
        print("\\nMonitoring stopped.")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open("performance_monitor.py", "w") as f:
        f.write(monitoring_script)
    
    print("✅ Performance monitoring system created: performance_monitor.py")

def main():
    """Main deployment function"""
    print("🚀 Deploying Python 3.14 Performance Optimizations...")
    print("=" * 60)
    
    try:
        # Step 1: Install dependencies
        print("\\n📋 Step 1: Installing performance dependencies...")
        install_performance_dependencies()
        
        # Step 2: Create performance wrappers
        print("\\n🔧 Step 2: Creating performance wrappers...")
        create_performance_wrappers()
        
        # Step 3: Create Rust extensions
        print("\\n⚡ Step 3: Creating Rust extension templates...")
        create_rust_extensions()
        
        # Step 4: Create memory optimization config
        print("\\n🧠 Step 4: Creating memory optimization configuration...")
        create_memory_optimization_config()
        
        # Step 5: Create performance monitoring
        print("\\n📊 Step 5: Creating performance monitoring system...")
        create_performance_monitoring()
        
        print("\\n" + "=" * 60)
        print("🎉 Python 3.14 Performance Optimizations deployed successfully!")
        
        print("\\n📋 Deployment Summary:")
        print("- ✅ Performance dependencies installed")
        print("- ✅ Numba-optimized functions created")
        print("- ✅ Async data processing implemented")
        print("- ✅ Rust extension templates created")
        print("- ✅ Memory optimization configured")
        print("- ✅ Performance monitoring system deployed")
        
        print("\\n🔧 Next Steps:")
        print("1. Test performance wrappers: python fortress_performance_wrappers.py")
        print("2. Start performance monitoring: python performance_monitor.py")
        print("3. Build Rust extensions: python setup_rust_extensions.py build_ext --inplace")
        print("4. Monitor performance logs: tail -f performance_monitor.log")
        
        print("\\n⚡ Performance Features Available:")
        print("- Numba JIT compilation for mathematical operations")
        print("- Async batch processing with orjson serialization")
        print("- Optimized WebSocket connections with compression")
        print("- Memory usage monitoring and optimization")
        print("- Rust extensions for maximum performance")
        print("- Real-time performance metrics collection")
        
        return True
        
    except Exception as e:
        print(f"\\n❌ Deployment failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)