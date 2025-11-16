
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
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    asyncio.run(main())
