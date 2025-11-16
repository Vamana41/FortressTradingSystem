#!/usr/bin/env python3
"""Comprehensive system performance benchmarking for Fortress Trading System"""

import time
import json
import psutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import sys
import os
from typing import Dict, List, Any
import threading
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - BENCHMARK - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('benchmark_results.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemBenchmark:
    """Comprehensive system performance benchmark"""

    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
        self.baseline_metrics = None

    def collect_system_info(self) -> Dict[str, Any]:
        """Collect comprehensive system information"""
        try:
            # CPU information
            cpu_info = {
                'physical_cores': psutil.cpu_count(logical=False),
                'logical_cores': psutil.cpu_count(logical=True),
                'max_frequency_mhz': psutil.cpu_freq().max if psutil.cpu_freq() else None,
                'current_frequency_mhz': psutil.cpu_freq().current if psutil.cpu_freq() else None
            }

            # Memory information
            memory = psutil.virtual_memory()
            memory_info = {
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'percent_used': memory.percent
            }

            # Disk information
            disk_info = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info[partition.mountpoint] = {
                        'total_gb': usage.total / (1024**3),
                        'free_gb': usage.free / (1024**3),
                        'percent_used': usage.percent
                    }
                except:
                    continue

            # Python version
            python_info = {
                'version': sys.version,
                'executable': sys.executable,
                'path': sys.path[:3]  # First 3 paths only
            }

            return {
                'timestamp': datetime.now().isoformat(),
                'cpu': cpu_info,
                'memory': memory_info,
                'disk': disk_info,
                'python': python_info
            }

        except Exception as e:
            logger.error(f"Error collecting system info: {e}")
            return {}

    def benchmark_cpu_performance(self, duration_seconds: int = 10) -> Dict[str, Any]:
        """Benchmark CPU performance"""
        logger.info(f"Starting CPU benchmark for {duration_seconds} seconds...")

        start_time = time.time()
        cpu_percentages = []

        # CPU-intensive calculation
        def fibonacci(n):
            if n <= 1:
                return n
            return fibonacci(n-1) + fibonacci(n-2)

        # Monitor CPU during calculation
        while time.time() - start_time < duration_seconds:
            # Perform CPU-intensive work
            result = fibonacci(25)  # Adjust based on system speed

            # Collect CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_percentages.append(cpu_percent)

            time.sleep(0.1)

        # Calculate statistics
        if cpu_percentages:
            avg_cpu = sum(cpu_percentages) / len(cpu_percentages)
            max_cpu = max(cpu_percentages)
            min_cpu = min(cpu_percentages)
        else:
            avg_cpu = max_cpu = min_cpu = 0

        return {
            'duration_seconds': duration_seconds,
            'average_cpu_percent': avg_cpu,
            'max_cpu_percent': max_cpu,
            'min_cpu_percent': min_cpu,
            'samples': len(cpu_percentages)
        }

    def benchmark_memory_performance(self, test_size_mb: int = 100) -> Dict[str, Any]:
        """Benchmark memory performance"""
        logger.info(f"Starting memory benchmark with {test_size_mb}MB test data...")

        # Get baseline memory usage
        baseline = psutil.virtual_memory()

        # Create test data
        test_data = []
        chunk_size = 1024 * 1024  # 1MB chunks

        start_time = time.time()

        # Allocate memory in chunks
        for i in range(test_size_mb):
            chunk = bytearray(chunk_size)
            test_data.append(chunk)

            if i % 10 == 0:  # Log progress every 10MB
                logger.info(f"Allocated {i}MB...")

        allocation_time = time.time() - start_time

        # Measure memory usage after allocation
        after_allocation = psutil.virtual_memory()

        # Clean up
        test_data.clear()

        # Measure memory usage after cleanup
        time.sleep(1)  # Give garbage collector time
        after_cleanup = psutil.virtual_memory()

        return {
            'test_size_mb': test_size_mb,
            'allocation_time_seconds': allocation_time,
            'memory_before_mb': baseline.used / (1024**2),
            'memory_after_allocation_mb': after_allocation.used / (1024**2),
            'memory_after_cleanup_mb': after_cleanup.used / (1024**2),
            'memory_increase_mb': (after_allocation.used - baseline.used) / (1024**2)
        }

    def benchmark_disk_performance(self, test_file_size_mb: int = 50) -> Dict[str, Any]:
        """Benchmark disk I/O performance"""
        logger.info(f"Starting disk benchmark with {test_file_size_mb}MB test file...")

        test_file = Path("benchmark_test_file.dat")

        try:
            # Create test data
            test_data = os.urandom(test_file_size_mb * 1024 * 1024)

            # Write benchmark
            start_time = time.time()
            with open(test_file, 'wb') as f:
                f.write(test_data)
            write_time = time.time() - start_time

            # Read benchmark
            start_time = time.time()
            with open(test_file, 'rb') as f:
                read_data = f.read()
            read_time = time.time() - start_time

            # Verify data integrity
            data_valid = read_data == test_data

            # Calculate speeds
            file_size_mb = test_file_size_mb
            write_speed_mbps = file_size_mb / write_time
            read_speed_mbps = file_size_mb / read_time

            return {
                'test_file_size_mb': file_size_mb,
                'write_time_seconds': write_time,
                'read_time_seconds': read_time,
                'write_speed_mbps': write_speed_mbps,
                'read_speed_mbps': read_speed_mbps,
                'data_integrity_valid': data_valid
            }

        finally:
            # Clean up test file
            if test_file.exists():
                test_file.unlink()

    def benchmark_python_performance(self) -> Dict[str, Any]:
        """Benchmark Python-specific performance"""
        logger.info("Starting Python performance benchmark...")

        # JSON serialization/deserialization
        test_data = {
            'numbers': list(range(10000)),
            'strings': [f"string_{i}" for i in range(10000)],
            'nested': {'level1': {'level2': {'level3': 'deep_value'}}}
        }

        # JSON benchmark
        start_time = time.time()
        for _ in range(100):
            json_str = json.dumps(test_data)
            json.loads(json_str)
        json_time = time.time() - start_time

        # List operations
        test_list = list(range(10000))

        start_time = time.time()
        for _ in range(1000):
            test_list.append(len(test_list))
            test_list.sort()
            test_list.pop(0)
        list_time = time.time() - start_time

        # String operations
        test_string = "benchmark_test_string" * 100

        start_time = time.time()
        for _ in range(10000):
            test_string.upper()
            test_string.lower()
            test_string.replace("test", "TEST")
        string_time = time.time() - start_time

        return {
            'json_operations_time_seconds': json_time,
            'list_operations_time_seconds': list_time,
            'string_operations_time_seconds': string_time,
            'operations_per_second': {
                'json': 200 / json_time,  # 200 operations (100 serialize + 100 deserialize)
                'list': 3000 / list_time,  # 3000 operations (1000 * 3 operations)
                'string': 30000 / string_time  # 30000 operations (10000 * 3 operations)
            }
        }

    def benchmark_network_performance(self) -> Dict[str, Any]:
        """Benchmark network performance (basic connectivity test)"""
        logger.info("Starting network performance benchmark...")

        # Test basic connectivity
        test_urls = [
            'http://localhost:5000/api/v1/ping',  # OpenAlgo
            'http://httpbin.org/delay/1',  # External test
        ]

        results = {}

        for url in test_urls:
            try:
                import requests
                start_time = time.time()
                response = requests.get(url, timeout=10)
                response_time = time.time() - start_time

                results[url] = {
                    'response_time_seconds': response_time,
                    'status_code': response.status_code,
                    'success': response.status_code == 200
                }

            except Exception as e:
                results[url] = {
                    'response_time_seconds': None,
                    'status_code': None,
                    'success': False,
                    'error': str(e)
                }

        return results

    def benchmark_fortress_specific(self) -> Dict[str, Any]:
        """Benchmark Fortress Trading System specific operations"""
        logger.info("Starting Fortress-specific benchmark...")

        results = {}

        # Test OpenAlgo integration
        try:
            start_time = time.time()
            # Test if OpenAlgo is accessible
            import requests
            response = requests.get('http://localhost:5000/api/v1/ping', timeout=5)
            openalgo_response_time = time.time() - start_time

            results['openalgo_ping'] = {
                'response_time_seconds': openalgo_response_time,
                'status_code': response.status_code,
                'available': response.status_code == 200
            }
        except Exception as e:
            results['openalgo_ping'] = {
                'response_time_seconds': None,
                'status_code': None,
                'available': False,
                'error': str(e)
            }

        # Test configuration files
        config_files = [
            'rtd_ws_config.json',
            'upgrade_config.json',
            'memory_optimization_config.json'
        ]

        config_results = {}
        for config_file in config_files:
            config_path = Path(config_file)
            if config_path.exists():
                try:
                    start_time = time.time()
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    load_time = time.time() - start_time

                    config_results[config_file] = {
                        'load_time_seconds': load_time,
                        'file_size_kb': config_path.stat().st_size / 1024,
                        'valid_json': True
                    }
                except Exception as e:
                    config_results[config_file] = {
                        'load_time_seconds': None,
                        'file_size_kb': config_path.stat().st_size / 1024 if config_path.exists() else 0,
                        'valid_json': False,
                        'error': str(e)
                    }
            else:
                config_results[config_file] = {
                    'load_time_seconds': None,
                    'file_size_kb': 0,
                    'valid_json': False,
                    'error': 'File not found'
                }

        results['config_files'] = config_results

        return results

    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive system benchmark"""
        logger.info("Starting comprehensive system benchmark...")
        self.start_time = datetime.now()

        # Collect system information
        system_info = self.collect_system_info()

        # Run all benchmarks
        benchmarks = {
            'system_info': system_info,
            'cpu_performance': self.benchmark_cpu_performance(),
            'memory_performance': self.benchmark_memory_performance(),
            'disk_performance': self.benchmark_disk_performance(),
            'python_performance': self.benchmark_python_performance(),
            'network_performance': self.benchmark_network_performance(),
            'fortress_specific': self.benchmark_fortress_specific()
        }

        self.end_time = datetime.now()

        # Calculate overall performance score
        performance_score = self.calculate_performance_score(benchmarks)

        results = {
            'benchmark_id': f"fortress_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_minutes': (self.end_time - self.start_time).total_seconds() / 60,
            'performance_score': performance_score,
            'benchmarks': benchmarks
        }

        return results

    def calculate_performance_score(self, benchmarks: Dict) -> float:
        """Calculate overall performance score (0-100)"""
        score = 0.0
        max_score = 100.0

        # CPU performance (25% weight)
        if 'cpu_performance' in benchmarks:
            cpu_data = benchmarks['cpu_performance']
            if 'average_cpu_percent' in cpu_data:
                # Lower CPU usage during benchmark is better
                cpu_score = max(0, 100 - cpu_data['average_cpu_percent'])
                score += cpu_score * 0.25

        # Memory performance (25% weight)
        if 'memory_performance' in benchmarks:
            mem_data = benchmarks['memory_performance']
            if 'allocation_time_seconds' in mem_data:
                # Faster allocation is better (normalize to 0-100)
                allocation_time = mem_data['allocation_time_seconds']
                mem_score = max(0, 100 - (allocation_time * 10))  # Scale appropriately
                score += mem_score * 0.25

        # Disk performance (20% weight)
        if 'disk_performance' in benchmarks:
            disk_data = benchmarks['disk_performance']
            if 'read_speed_mbps' in disk_data and 'write_speed_mbps' in disk_data:
                # Higher speeds are better
                read_score = min(100, disk_data['read_speed_mbps'] * 2)  # Scale appropriately
                write_score = min(100, disk_data['write_speed_mbps'] * 2)
                disk_score = (read_score + write_score) / 2
                score += disk_score * 0.20

        # Python performance (15% weight)
        if 'python_performance' in benchmarks:
            py_data = benchmarks['python_performance']
            if 'operations_per_second' in py_data:
                # Higher operations per second are better
                ops_score = min(100, (py_data['operations_per_second']['json'] +
                                    py_data['operations_per_second']['list'] +
                                    py_data['operations_per_second']['string']) / 3)
                score += ops_score * 0.15

        # Network performance (10% weight)
        if 'network_performance' in benchmarks:
            net_data = benchmarks['network_performance']
            if 'http://localhost:5000/api/v1/ping' in net_data:
                local_ping = net_data['http://localhost:5000/api/v1/ping']
                if local_ping['success'] and local_ping['response_time_seconds']:
                    # Lower response time is better
                    response_time = local_ping['response_time_seconds']
                    net_score = max(0, 100 - (response_time * 50))  # Scale appropriately
                    score += net_score * 0.10

        # Fortress-specific (5% weight)
        if 'fortress_specific' in benchmarks:
            fortress_data = benchmarks['fortress_specific']
            if 'openalgo_ping' in fortress_data:
                openalgo_ping = fortress_data['openalgo_ping']
                if openalgo_ping['available']:
                    score += 5.0  # Full score if OpenAlgo is available

        return round(score, 2)

    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save benchmark results to file"""
        if not filename:
            filename = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)

            logger.info(f"Benchmark results saved to {filename}")
            return filename

        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return None

    def print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("🏁 FORTRESS TRADING SYSTEM - PERFORMANCE BENCHMARK")
        print("="*60)

        print(f"\n📊 Benchmark ID: {results['benchmark_id']}")
        print(f"⏱️  Duration: {results['duration_minutes']:.1f} minutes")
        print(f"🎯 Overall Performance Score: {results['performance_score']}/100")

        benchmarks = results['benchmarks']

        # System Information
        if 'system_info' in benchmarks and benchmarks['system_info']:
            sys_info = benchmarks['system_info']
            print(f"\n💻 System Information:")
            if 'cpu' in sys_info:
                cpu = sys_info['cpu']
                print(f"   CPU: {cpu['physical_cores']} physical, {cpu['logical_cores']} logical cores")
                if cpu['max_frequency_mhz']:
                    print(f"   Frequency: {cpu['max_frequency_mhz']:.0f} MHz max")

            if 'memory' in sys_info:
                mem = sys_info['memory']
                print(f"   Memory: {mem['total_gb']:.1f} GB total, {mem['available_gb']:.1f} GB available")

        # Performance Results
        print(f"\n📈 Performance Results:")

        if 'cpu_performance' in benchmarks:
            cpu = benchmarks['cpu_performance']
            print(f"   CPU: {cpu['average_cpu_percent']:.1f}% avg usage during benchmark")

        if 'memory_performance' in benchmarks:
            mem = benchmarks['memory_performance']
            print(f"   Memory: {mem['allocation_time_seconds']:.2f}s to allocate {mem['test_size_mb']}MB")

        if 'disk_performance' in benchmarks:
            disk = benchmarks['disk_performance']
            print(f"   Disk: {disk['read_speed_mbps']:.1f} MB/s read, {disk['write_speed_mbps']:.1f} MB/s write")

        if 'python_performance' in benchmarks:
            py = benchmarks['python_performance']
            print(f"   Python: {py['operations_per_second']['json']:.0f} JSON ops/sec")

        if 'network_performance' in benchmarks:
            net = benchmarks['network_performance']
            if 'http://localhost:5000/api/v1/ping' in net:
                ping = net['http://localhost:5000/api/v1/ping']
                if ping['success']:
                    print(f"   OpenAlgo: Available ({ping['response_time_seconds']:.3f}s response)")
                else:
                    print(f"   OpenAlgo: Not available")

        if 'fortress_specific' in benchmarks:
            fortress = benchmarks['fortress_specific']
            if 'config_files' in fortress:
                config_files = fortress['config_files']
                valid_configs = sum(1 for cf in config_files.values() if cf.get('valid_json', False))
                total_configs = len(config_files)
                print(f"   Config Files: {valid_configs}/{total_configs} valid")

        # Performance Rating
        score = results['performance_score']
        if score >= 90:
            rating = "🟢 Excellent"
        elif score >= 75:
            rating = "🟡 Good"
        elif score >= 60:
            rating = "🟠 Fair"
        else:
            rating = "🔴 Needs Improvement"

        print(f"\n🎯 Performance Rating: {rating}")
        print("="*60)

def main():
    """Main benchmark function"""
    print("🚀 Starting Fortress Trading System Performance Benchmark...")

    benchmark = SystemBenchmark()

    try:
        # Run comprehensive benchmark
        results = benchmark.run_comprehensive_benchmark()

        # Save results
        filename = benchmark.save_results(results)

        # Print summary
        benchmark.print_summary(results)

        print(f"\n✅ Benchmark completed successfully!")
        if filename:
            print(f"📁 Results saved to: {filename}")

        return 0

    except KeyboardInterrupt:
        print("\n❌ Benchmark interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
