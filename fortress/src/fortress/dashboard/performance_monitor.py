import asyncio
import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from fortress.core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class PerformanceMetric:
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    disk_gb: float
    network_sent_mb: float
    network_recv_mb: float
    open_files: int
    thread_count: int
    process_count: int

@dataclass
class TradingMetric:
    timestamp: datetime
    signals_per_second: float
    orders_per_second: float
    latency_ms: float
    throughput: float
    error_rate: float
    success_rate: float

@dataclass
class BenchmarkResult:
    name: str
    timestamp: datetime
    duration_seconds: float
    operations_count: int
    operations_per_second: float
    average_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    memory_peak_mb: float
    cpu_percent: float

class PerformanceMonitor:
    """System performance monitoring and benchmarking"""

    def __init__(self, data_dir: str = "data/performance"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.performance_history: List[PerformanceMetric] = []
        self.trading_metrics: List[TradingMetric] = []
        self.benchmark_results: List[BenchmarkResult] = []

        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Performance thresholds
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'latency_ms': 100.0,
            'error_rate': 5.0,
            'signals_per_second': 10.0
        }

        # Trading performance counters
        self.signal_count = 0
        self.order_count = 0
        self.error_count = 0
        self.total_latency = 0.0
        self.latency_count = 0

        self.start_time = datetime.now()

    async def start_monitoring(self, interval_seconds: int = 30):
        """Start performance monitoring"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitor_loop(interval_seconds))
        logger.info("Performance monitoring started", interval=interval_seconds)

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Performance monitoring stopped")

    async def _monitor_loop(self, interval_seconds: int):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                await self._collect_metrics()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error("Error in performance monitoring loop", error=str(e))
                await asyncio.sleep(interval_seconds)

    async def _collect_metrics(self):
        """Collect system performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()

            # Process metrics
            process = psutil.Process()
            open_files = len(process.open_files())
            thread_count = process.num_threads()

            # Network metrics (convert to MB)
            network_sent_mb = network.bytes_sent / (1024 * 1024)
            network_recv_mb = network.bytes_recv / (1024 * 1024)

            metric = PerformanceMetric(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_mb=memory.used / (1024 * 1024),
                disk_percent=disk.percent,
                disk_gb=disk.used / (1024 * 1024 * 1024),
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                open_files=open_files,
                thread_count=thread_count,
                process_count=len(psutil.pids())
            )

            self.performance_history.append(metric)

            # Keep only last 24 hours of data
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.performance_history = [
                m for m in self.performance_history
                if m.timestamp > cutoff_time
            ]

            # Check thresholds and log warnings
            await self._check_thresholds(metric)

            logger.debug("Performance metrics collected",
                        cpu=cpu_percent, memory=memory.percent, disk=disk.percent)

        except Exception as e:
            logger.error("Failed to collect performance metrics", error=str(e))

    async def _check_thresholds(self, metric: PerformanceMetric):
        """Check if metrics exceed thresholds"""
        warnings = []

        if metric.cpu_percent > self.thresholds['cpu_percent']:
            warnings.append(f"High CPU usage: {metric.cpu_percent:.1f}%")

        if metric.memory_percent > self.thresholds['memory_percent']:
            warnings.append(f"High memory usage: {metric.memory_percent:.1f}%")

        if metric.disk_percent > self.thresholds['disk_percent']:
            warnings.append(f"High disk usage: {metric.disk_percent:.1f}%")

        if warnings:
            logger.warning("Performance thresholds exceeded", warnings=warnings)

    def record_trading_metric(self, latency_ms: float, success: bool = True):
        """Record trading performance metric"""
        if success:
            self.signal_count += 1
            self.total_latency += latency_ms
            self.latency_count += 1
        else:
            self.error_count += 1

    def record_order_metric(self, success: bool = True):
        """Record order execution metric"""
        if success:
            self.order_count += 1
        else:
            self.error_count += 1

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        if not self.performance_history:
            return {}

        latest = self.performance_history[-1]
        uptime = datetime.now() - self.start_time

        # Calculate trading metrics
        total_operations = self.signal_count + self.order_count
        avg_latency = self.total_latency / max(self.latency_count, 1)
        error_rate = (self.error_count / max(total_operations, 1)) * 100
        success_rate = 100 - error_rate

        trading_metric = TradingMetric(
            timestamp=datetime.now(),
            signals_per_second=self.signal_count / max(uptime.total_seconds(), 1),
            orders_per_second=self.order_count / max(uptime.total_seconds(), 1),
            latency_ms=avg_latency,
            throughput=total_operations / max(uptime.total_seconds(), 1),
            error_rate=error_rate,
            success_rate=success_rate
        )

        return {
            "system": asdict(latest),
            "trading": asdict(trading_metric),
            "uptime_seconds": uptime.total_seconds(),
            "signal_count": self.signal_count,
            "order_count": self.order_count,
            "error_count": self.error_count
        }

    def get_performance_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get performance history for specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.performance_history
            if m.timestamp > cutoff_time
        ]
        return [asdict(m) for m in recent_metrics]

    async def run_benchmark(self, name: str, benchmark_func, iterations: int = 1000) -> BenchmarkResult:
        """Run a performance benchmark"""
        logger.info("Starting benchmark", name=name, iterations=iterations)

        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        start_cpu = psutil.cpu_percent()

        latencies = []

        for i in range(iterations):
            iter_start = time.time()
            try:
                await benchmark_func()
                iter_end = time.time()
                latencies.append((iter_end - iter_start) * 1000)  # Convert to ms
            except Exception as e:
                logger.error("Benchmark iteration failed", iteration=i, error=str(e))
                latencies.append(float('inf'))

        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        end_cpu = psutil.cpu_percent()

        # Calculate statistics
        valid_latencies = [l for l in latencies if l != float('inf')]
        avg_latency = sum(valid_latencies) / max(len(valid_latencies), 1)
        min_latency = min(valid_latencies) if valid_latencies else 0
        max_latency = max(valid_latencies) if valid_latencies else 0

        result = BenchmarkResult(
            name=name,
            timestamp=datetime.now(),
            duration_seconds=end_time - start_time,
            operations_count=iterations,
            operations_per_second=iterations / max(end_time - start_time, 0.001),
            average_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            memory_peak_mb=max(start_memory, end_memory),
            cpu_percent=(start_cpu + end_cpu) / 2
        )

        self.benchmark_results.append(result)

        logger.info("Benchmark completed",
                   name=name,
                   ops_per_second=result.operations_per_second,
                   avg_latency_ms=avg_latency)

        return result

    def get_benchmark_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent benchmark results"""
        recent_results = self.benchmark_results[-limit:]
        return [asdict(r) for r in recent_results]

    def save_metrics(self, filename: Optional[str] = None):
        """Save performance metrics to file"""
        if not filename:
            filename = f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.data_dir / filename

        data = {
            "timestamp": datetime.now().isoformat(),
            "performance_history": [asdict(m) for m in self.performance_history[-100:]],
            "trading_metrics": [asdict(m) for m in self.trading_metrics[-100:]],
            "benchmark_results": [asdict(r) for r in self.benchmark_results[-10:]],
            "current_metrics": self.get_current_metrics()
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info("Performance metrics saved", filepath=str(filepath))
        except Exception as e:
            logger.error("Failed to save performance metrics", error=str(e))

    def load_metrics(self, filename: str):
        """Load performance metrics from file"""
        filepath = self.data_dir / filename

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # TODO: Implement loading logic if needed
            logger.info("Performance metrics loaded", filepath=str(filepath))

        except Exception as e:
            logger.error("Failed to load performance metrics", error=str(e))

# Global performance monitor instance
performance_monitor = PerformanceMonitor()
