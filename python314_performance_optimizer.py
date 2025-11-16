#!/usr/bin/env python3
"""
Python 3.14 Performance Optimizations for Fortress Trading System

This module implements advanced performance optimizations specific to Python 3.14,
including asyncio optimizations, memory allocation improvements, and Rust-level
performance enhancements with Numba compilation.
"""

import asyncio
import gc
import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
import concurrent.futures
from functools import lru_cache, wraps
import tracemalloc
import psutil
import numpy as np
from numba import jit, njit, prange
from numba.typed import List as NumbaList
import redis.asyncio as redis
import aiohttp
import uvloop  # Faster event loop for asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_peak: float = 0.0
    gc_collections: int = 0
    asyncio_tasks: int = 0
    thread_count: int = 0
    response_time: float = 0.0
    throughput: float = 0.0

class Python314Optimizer:
    """Python 3.14 specific performance optimizations"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.config = self.load_optimization_config()
        self.metrics = PerformanceMetrics()
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Apply initial optimizations
        self.apply_python314_optimizations()
        
        logger.info("Python314Optimizer initialized")
    
    def load_optimization_config(self) -> Dict:
        """Load optimization configuration"""
        config_path = self.base_dir / "python314_optimizations.json"
        default_config = {
            "asyncio": {
                "use_uvloop": True,
                "max_workers": 100,
                "task_timeout": 30,
                "connection_pool_size": 50
            },
            "memory": {
                "gc_threshold": [700, 10, 10],
                "gc_generations": 3,
                "memory_limit_mb": 2048,
                "enable_tracemalloc": True
            },
            "numba": {
                "enabled": True,
                "parallel": True,
                "fastmath": True,
                "cache": True
            },
            "redis": {
                "connection_pool_size": 50,
                "socket_keepalive": True,
                "socket_keepalive_options": {
                    "TCP_KEEPIDLE": 1,
                    "TCP_KEEPINTVL": 1,
                    "TCP_KEEPCNT": 3
                }
            },
            "monitoring": {
                "interval_seconds": 5,
                "enable_memory_profiling": True,
                "enable_cpu_profiling": True,
                "log_performance": True
            }
        }
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    for key, value in loaded_config.items():
                        if key in default_config:
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            except Exception as e:
                logger.error(f"Error loading optimization config: {e}")
        
        return default_config
    
    def apply_python314_optimizations(self):
        """Apply Python 3.14 specific optimizations"""
        config = self.config
        
        # 1. Asyncio optimizations
        if config["asyncio"]["use_uvloop"]:
            self.install_uvloop()
        
        # 2. Memory optimizations
        self.optimize_memory_management()
        
        # 3. Garbage collection tuning
        self.optimize_gc()
        
        # 4. Threading optimizations
        self.optimize_threading()
        
        logger.info("Python 3.14 optimizations applied")
    
    def install_uvloop(self):
        """Install uvloop for better asyncio performance"""
        try:
            import uvloop
            uvloop.install()
            logger.info("uvloop installed for better asyncio performance")
        except ImportError:
            logger.warning("uvloop not available, using default asyncio")
    
    def optimize_memory_management(self):
        """Optimize memory allocation and management"""
        config = self.config["memory"]
        
        # Enable tracemalloc for memory profiling
        if config["enable_tracemalloc"]:
            tracemalloc.start()
            logger.info("Memory profiling enabled with tracemalloc")
        
        # Set memory limit (soft)
        memory_limit = config["memory_limit_mb"] * 1024 * 1024
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            logger.info(f"Memory limit set to {config['memory_limit_mb']} MB")
        except (ImportError, AttributeError):
            logger.warning("Resource module not available, memory limit not set")
    
    def optimize_gc(self):
        """Optimize garbage collection for better performance"""
        config = self.config["memory"]
        
        # Set GC thresholds
        thresholds = config["gc_threshold"]
        gc.set_threshold(*thresholds)
        logger.info(f"GC thresholds set to {thresholds}")
        
        # Disable automatic GC during critical operations
        gc.disable()
        logger.info("Automatic GC disabled, will use manual collection")
    
    def optimize_threading(self):
        """Optimize threading configuration"""
        # Set thread stack size
        threading.stack_size(1024 * 1024)  # 1MB stack size
        logger.info("Thread stack size optimized")
    
    @contextmanager
    def performance_monitor(self, operation_name: str):
        """Context manager for performance monitoring"""
        start_time = time.perf_counter()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        start_gc = gc.get_count()
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            end_gc = gc.get_count()
            
            # Update metrics
            self.metrics.response_time = end_time - start_time
            self.metrics.memory_usage = end_memory
            self.metrics.memory_peak = max(self.metrics.memory_peak, end_memory)
            self.metrics.gc_collections = sum(end_gc) - sum(start_gc)
            self.metrics.thread_count = threading.active_count()
            
            if self.config["monitoring"]["log_performance"]:
                logger.info(f"{operation_name}: {self.metrics.response_time:.3f}s, "
                          f"Memory: {self.metrics.memory_usage:.1f}MB, "
                          f"GC: {self.metrics.gc_collections}")
    
    # Numba-accelerated functions for high-performance calculations
    @staticmethod
    @njit(parallel=True, fastmath=True, cache=True)
    def calculate_sma_numba(prices: np.ndarray, period: int) -> np.ndarray:
        """Numba-accelerated Simple Moving Average calculation"""
        n = len(prices)
        sma = np.empty(n - period + 1)
        
        for i in prange(n - period + 1):
            sma[i] = np.mean(prices[i:i + period])
        
        return sma
    
    @staticmethod
    @njit(parallel=True, fastmath=True, cache=True)
    def calculate_ema_numba(prices: np.ndarray, period: int) -> np.ndarray:
        """Numba-accelerated Exponential Moving Average calculation"""
        n = len(prices)
        ema = np.empty(n - period + 1)
        multiplier = 2.0 / (period + 1)
        
        # First EMA is SMA
        ema[0] = np.mean(prices[:period])
        
        for i in prange(1, n - period + 1):
            ema[i] = (prices[i + period - 1] * multiplier) + (ema[i - 1] * (1 - multiplier))
        
        return ema
    
    @staticmethod
    @njit(parallel=True, fastmath=True, cache=True)
    def calculate_rsi_numba(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Numba-accelerated RSI calculation"""
        n = len(prices)
        rsi = np.empty(n - period)
        
        for i in prange(period, n):
            gains = []
            losses = []
            
            for j in range(1, period + 1):
                change = prices[i - j + 1] - prices[i - j]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(-change)
            
            avg_gain = np.mean(np.array(gains)) if gains else 0.0
            avg_loss = np.mean(np.array(losses)) if losses else 0.0
            
            if avg_loss == 0:
                rsi[i - period] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i - period] = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    # High-performance Redis connection pool
    async def create_redis_pool(self) -> redis.ConnectionPool:
        """Create optimized Redis connection pool"""
        config = self.config["redis"]
        
        pool = redis.ConnectionPool(
            host='localhost',
            port=6379,
            db=0,
            max_connections=config["connection_pool_size"],
            socket_keepalive=config["socket_keepalive"],
            socket_keepalive_options=config.get("socket_keepalive_options", {}),
            decode_responses=True
        )
        
        logger.info(f"Redis connection pool created with {config['connection_pool_size']} connections")
        return pool
    
    # Asyncio optimizations
    async def optimized_gather(self, *coroutines, return_exceptions=False):
        """Optimized asyncio.gather with timeout and error handling"""
        timeout = self.config["asyncio"]["task_timeout"]
        
        try:
            return await asyncio.wait_for(
                asyncio.gather(*coroutines, return_exceptions=return_exceptions),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Asyncio operations timed out after {timeout}s")
            raise
    
    # Memory-efficient data processing
    def process_market_data_batch(self, data_batch: List[Dict]) -> Dict:
        """Process market data batch with memory efficiency"""
        with self.performance_monitor("Market data batch processing"):
            if not data_batch:
                return {}
            
            # Convert to numpy arrays for efficient processing
            prices = np.array([item['price'] for item in data_batch], dtype=np.float64)
            volumes = np.array([item['volume'] for item in data_batch], dtype=np.int64)
            
            # Use Numba-accelerated calculations
            if self.config["numba"]["enabled"]:
                sma_20 = self.calculate_sma_numba(prices, 20)
                ema_20 = self.calculate_ema_numba(prices, 20)
                rsi_14 = self.calculate_rsi_numba(prices, 14)
            else:
                # Fallback to standard numpy calculations
                sma_20 = np.convolve(prices, np.ones(20)/20, mode='valid')
                ema_20 = self.standard_ema(prices, 20)
                rsi_14 = self.standard_rsi(prices, 14)
            
            return {
                "sma_20": sma_20[-1] if len(sma_20) > 0 else 0.0,
                "ema_20": ema_20[-1] if len(ema_20) > 0 else 0.0,
                "rsi_14": rsi_14[-1] if len(rsi_14) > 0 else 50.0,
                "total_volume": np.sum(volumes),
                "avg_price": np.mean(prices),
                "price_std": np.std(prices),
                "processed_at": time.time()
            }
    
    def standard_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Standard EMA calculation (fallback)"""
        multiplier = 2.0 / (period + 1)
        ema = np.empty(len(prices) - period + 1)
        ema[0] = np.mean(prices[:period])
        
        for i in range(1, len(ema)):
            ema[i] = (prices[i + period - 1] * multiplier) + (ema[i - 1] * (1 - multiplier))
        
        return ema
    
    def standard_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Standard RSI calculation (fallback)"""
        rsi = np.empty(len(prices) - period)
        
        for i in range(period, len(prices)):
            gains = []
            losses = []
            
            for j in range(1, period + 1):
                change = prices[i - j + 1] - prices[i - j]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(-change)
            
            avg_gain = np.mean(gains) if gains else 0.0
            avg_loss = np.mean(losses) if losses else 0.0
            
            if avg_loss == 0:
                rsi[i - period] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i - period] = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def start_performance_monitoring(self):
        """Start continuous performance monitoring"""
        if self.monitoring_active:
            logger.warning("Performance monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Performance monitoring started")
    
    def stop_performance_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Performance monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        interval = self.config["monitoring"]["interval_seconds"]
        
        while self.monitoring_active:
            try:
                # Update system metrics
                process = psutil.Process()
                self.metrics.cpu_usage = process.cpu_percent()
                self.metrics.memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                self.metrics.memory_peak = max(self.metrics.memory_peak, self.metrics.memory_usage)
                self.metrics.thread_count = threading.active_count()
                
                # Get asyncio task count
                try:
                    loop = asyncio.get_running_loop()
                    self.metrics.asyncio_tasks = len([task for task in asyncio.all_tasks(loop) if not task.done()])
                except RuntimeError:
                    self.metrics.asyncio_tasks = 0
                
                # Log metrics if enabled
                if self.config["monitoring"]["log_performance"]:
                    logger.info(f"Performance: CPU={self.metrics.cpu_usage:.1f}%, "
                              f"Memory={self.metrics.memory_usage:.1f}MB, "
                              f"Threads={self.metrics.thread_count}, "
                              f"Asyncio={self.metrics.asyncio_tasks}")
                
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                time.sleep(interval)
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        return {
            "timestamp": time.time(),
            "metrics": {
                "cpu_usage_percent": self.metrics.cpu_usage,
                "memory_usage_mb": self.metrics.memory_usage,
                "memory_peak_mb": self.metrics.memory_peak,
                "gc_collections": self.metrics.gc_collections,
                "asyncio_tasks": self.metrics.asyncio_tasks,
                "thread_count": self.metrics.thread_count,
                "response_time_avg": self.metrics.response_time
            },
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform,
                "numba_available": self.config["numba"]["enabled"],
                "uvloop_available": self.config["asyncio"]["use_uvloop"]
            },
            "optimization_status": {
                "gc_optimized": not gc.isenabled(),
                "memory_profiling": self.config["memory"]["enable_tracemalloc"],
                "performance_monitoring": self.monitoring_active
            }
        }
    
    def benchmark_calculations(self, data_size: int = 10000) -> Dict:
        """Benchmark calculation performance"""
        logger.info(f"Running benchmark with {data_size} data points...")
        
        # Generate test data
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(data_size) * 0.1) + 100
        
        results = {}
        
        # Benchmark SMA calculation
        start = time.perf_counter()
        sma_result = self.calculate_sma_numba(prices, 20)
        results["sma_numba_time"] = time.perf_counter() - start
        results["sma_numba_result"] = sma_result[-1] if len(sma_result) > 0 else 0
        
        # Benchmark EMA calculation
        start = time.perf_counter()
        ema_result = self.calculate_ema_numba(prices, 20)
        results["ema_numba_time"] = time.perf_counter() - start
        results["ema_numba_result"] = ema_result[-1] if len(ema_result) > 0 else 0
        
        # Benchmark RSI calculation
        start = time.perf_counter()
        rsi_result = self.calculate_rsi_numba(prices, 14)
        results["rsi_numba_time"] = time.perf_counter() - start
        results["rsi_numba_result"] = rsi_result[-1] if len(rsi_result) > 0 else 50
        
        # Benchmark standard calculations for comparison
        start = time.perf_counter()
        sma_std = self.standard_ema(prices, 20)
        results["sma_standard_time"] = time.perf_counter() - start
        
        # Calculate speedups
        results["sma_speedup"] = results["sma_standard_time"] / results["sma_numba_time"]
        
        logger.info(f"Benchmark completed: SMA speedup {results['sma_speedup']:.2f}x")
        
        return results

def main():
    """Main function for testing optimizations"""
    optimizer = Python314Optimizer()
    
    # Start performance monitoring
    optimizer.start_performance_monitoring()
    
    # Run benchmark
    benchmark_results = optimizer.benchmark_calculations()
    
    # Get performance report
    report = optimizer.get_performance_report()
    
    print("\nPerformance Optimization Results:")
    print("="*50)
    print(f"Python Version: {report['system_info']['python_version']}")
    print(f"Numba Available: {report['system_info']['numba_available']}")
    print(f"UVLoop Available: {report['system_info']['uvloop_available']}")
    print(f"SMA Calculation Speedup: {benchmark_results['sma_speedup']:.2f}x")
    print(f"Memory Usage: {report['metrics']['memory_usage_mb']:.1f} MB")
    print(f"CPU Usage: {report['metrics']['cpu_usage_percent']:.1f}%")
    
    # Stop monitoring
    optimizer.stop_performance_monitoring()

if __name__ == "__main__":
    main()