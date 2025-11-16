#!/usr/bin/env python3
"""
Comprehensive Benchmarking System for Fortress Trading System
Tests all performance optimizations and provides detailed reports
"""

import time
import json
import psutil
import logging
import asyncio
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fortress_performance_wrappers import data_processor, ws_optimizer
    PERFORMANCE_WRAPPERS_AVAILABLE = True
except ImportError:
    PERFORMANCE_WRAPPERS_AVAILABLE = False
    print("⚠️ Performance wrappers not available, some tests will be skipped")

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

class ComprehensiveBenchmark:
    """Comprehensive benchmarking system for all optimizations"""

    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
        self.system_info = self.collect_system_info()

    def collect_system_info(self) -> Dict:
        """Collect system information for benchmark context"""
        try:
            cpu_info = {
                'physical_cores': psutil.cpu_count(logical=False),
                'logical_cores': psutil.cpu_count(logical=True),
                'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                'cpu_percent': psutil.cpu_percent(interval=1)
            }

            memory_info = psutil.virtual_memory()._asdict()

            disk_info = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info[partition.mountpoint] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                except:
                    continue

            return {
                'cpu': cpu_info,
                'memory': memory_info,
                'disk': disk_info,
                'python_version': sys.version,
                'platform': sys.platform,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error collecting system info: {e}")
            return {}

    def benchmark_numpy_operations(self, size: int = 1000000) -> Dict:
        """Benchmark NumPy operations for trading calculations"""
        logger.info(f"Benchmarking NumPy operations with {size} elements...")

        start_time = time.time()

        try:
            # Generate sample data
            prices = np.random.randn(size).cumsum() + 100
            volumes = np.random.randint(100, 10000, size)

            # Benchmark various operations
            operations = {}

            # Moving averages
            start_op = time.time()
            ma_20 = pd.Series(prices).rolling(20).mean()
            operations['moving_average_20'] = time.time() - start_op

            # RSI calculation
            start_op = time.time()
            delta = pd.Series(prices).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            operations['rsi_calculation'] = time.time() - start_op

            # Standard deviation
            start_op = time.time()
            std_20 = pd.Series(prices).rolling(20).std()
            operations['standard_deviation_20'] = time.time() - start_op

            # Bollinger Bands
            start_op = time.time()
            middle_band = pd.Series(prices).rolling(20).mean()
            std = pd.Series(prices).rolling(20).std()
            upper_band = middle_band + (std * 2)
            lower_band = middle_band - (std * 2)
            operations['bollinger_bands'] = time.time() - start_op

            # Volume analysis
            start_op = time.time()
            volume_ma = pd.Series(volumes).rolling(20).mean()
            volume_ratio = volumes / volume_ma
            operations['volume_analysis'] = time.time() - start_op

            total_time = time.time() - start_time

            return {
                'total_time': total_time,
                'operations': operations,
                'operations_per_second': len(operations) / total_time,
                'data_size': size,
                'memory_usage_mb': sys.getsizeof(prices) / (1024 * 1024)
            }

        except Exception as e:
            logger.error(f"Error in NumPy benchmark: {e}")
            return {'error': str(e)}

    def benchmark_data_serialization(self, sample_size: int = 10000) -> Dict:
        """Benchmark different serialization methods"""
        logger.info(f"Benchmarking data serialization with {sample_size} records...")

        # Generate sample market data
        sample_data = []
        base_time = int(time.time())

        for i in range(sample_size):
            sample_data.append({
                'symbol': f'STOCK{i % 100}',
                'timestamp': base_time + i,
                'price': 100 + np.random.randn() * 5,
                'volume': np.random.randint(100, 10000),
                'bid': 99.5 + np.random.randn() * 0.5,
                'ask': 100.5 + np.random.randn() * 0.5,
                'open': 100 + np.random.randn() * 2,
                'high': 101 + np.random.randn() * 2,
                'low': 99 + np.random.randn() * 2,
                'close': 100 + np.random.randn() * 5
            })

        serialization_methods = {}

        try:
            # Standard JSON
            import json
            start_time = time.time()
            json_data = json.dumps(sample_data)
            json_load = json.loads(json_data)
            serialization_methods['json'] = time.time() - start_time

            # orjson (if available)
            try:
                import orjson
                start_time = time.time()
                orjson_data = orjson.dumps(sample_data)
                orjson_load = orjson.loads(orjson_data)
                serialization_methods['orjson'] = time.time() - start_time
            except ImportError:
                serialization_methods['orjson'] = None

            # ujson (if available)
            try:
                import ujson
                start_time = time.time()
                ujson_data = ujson.dumps(sample_data)
                ujson_load = ujson.loads(ujson_data)
                serialization_methods['ujson'] = time.time() - start_time
            except ImportError:
                serialization_methods['ujson'] = None

            # msgpack (if available)
            try:
                import msgpack
                start_time = time.time()
                msgpack_data = msgpack.dumps(sample_data)
                msgpack_load = msgpack.loads(msgpack_data)
                serialization_methods['msgpack'] = time.time() - start_time
            except ImportError:
                serialization_methods['msgpack'] = None

            return {
                'methods': serialization_methods,
                'sample_size': sample_size,
                'best_method': min([(k, v) for k, v in serialization_methods.items() if v is not None], key=lambda x: x[1])[0] if any(v is not None for v in serialization_methods.values()) else None
            }

        except Exception as e:
            logger.error(f"Error in serialization benchmark: {e}")
            return {'error': str(e)}

    def benchmark_async_operations(self, num_tasks: int = 100) -> Dict:
        """Benchmark async operations for concurrent processing"""
        logger.info(f"Benchmarking async operations with {num_tasks} tasks...")

        async def async_task(task_id: int):
            """Simulate async operation"""
            await asyncio.sleep(0.001)  # Simulate I/O operation
            return f"task_{task_id}_completed"

        async def run_async_benchmark():
            start_time = time.time()

            # Create tasks
            tasks = [async_task(i) for i in range(num_tasks)]

            # Run tasks concurrently
            results = await asyncio.gather(*tasks)

            total_time = time.time() - start_time
            return {
                'total_time': total_time,
                'tasks_per_second': num_tasks / total_time,
                'tasks_completed': len(results)
            }

        try:
            # Run async benchmark
            result = asyncio.run(run_async_benchmark())
            return result

        except Exception as e:
            logger.error(f"Error in async benchmark: {e}")
            return {'error': str(e)}

    def benchmark_memory_usage(self, data_size: int = 100000) -> Dict:
        """Benchmark memory usage patterns"""
        logger.info(f"Benchmarking memory usage with {data_size} elements...")

        start_time = time.time()
        initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        try:
            # Create large datasets
            data_arrays = []

            # NumPy arrays
            for i in range(10):
                arr = np.random.randn(data_size)
                data_arrays.append(arr)

            # Pandas DataFrames
            for i in range(5):
                df = pd.DataFrame({
                    'price': np.random.randn(data_size) + 100,
                    'volume': np.random.randint(100, 10000, data_size),
                    'timestamp': range(data_size)
                })
                data_arrays.append(df)

            peak_memory = psutil.Process().memory_info().rss / (1024 * 1024)

            # Force garbage collection
            import gc
            gc.collect()

            final_memory = psutil.Process().memory_info().rss / (1024 * 1024)

            total_time = time.time() - start_time

            return {
                'initial_memory_mb': initial_memory,
                'peak_memory_mb': peak_memory,
                'final_memory_mb': final_memory,
                'memory_increase_mb': peak_memory - initial_memory,
                'memory_released_mb': peak_memory - final_memory,
                'total_time': total_time,
                'data_size': data_size
            }

        except Exception as e:
            logger.error(f"Error in memory benchmark: {e}")
            return {'error': str(e)}

    def benchmark_performance_wrappers(self) -> Dict:
        """Benchmark the custom performance wrappers"""
        logger.info("Benchmarking performance wrappers...")

        if not PERFORMANCE_WRAPPERS_AVAILABLE:
            return {'error': 'Performance wrappers not available'}

        try:
            # Test data processor
            start_time = time.time()

            # Generate test data batch
            test_data = []
            for i in range(1000):
                test_data.append({
                    'symbol': f'STOCK{i % 100}',
                    'price': 100 + np.random.randn() * 5,
                    'volume': np.random.randint(100, 10000),
                    'timestamp': int(time.time()) + i
                })

            # Process batch
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            start_proc = time.time()
            processed_data = loop.run_until_complete(
                data_processor.process_market_data_batch(test_data)
            )
            processing_time = time.time() - start_proc

            total_time = time.time() - start_time

            return {
                'data_processing_time': processing_time,
                'total_time': total_time,
                'records_processed': len(processed_data),
                'records_per_second': len(processed_data) / processing_time,
                'memory_optimization_result': data_processor.optimize_memory_usage()
            }

        except Exception as e:
            logger.error(f"Error in performance wrappers benchmark: {e}")
            return {'error': str(e)}

    def run_all_benchmarks(self) -> Dict:
        """Run all benchmark tests"""
        logger.info("Starting comprehensive benchmarking...")
        self.start_time = datetime.now()

        benchmarks = {
            'numpy_operations': self.benchmark_numpy_operations(),
            'data_serialization': self.benchmark_data_serialization(),
            'async_operations': self.benchmark_async_operations(),
            'memory_usage': self.benchmark_memory_usage(),
            'performance_wrappers': self.benchmark_performance_wrappers()
        }

        self.end_time = datetime.now()

        # Calculate overall performance score
        total_score = 0
        valid_benchmarks = 0

        for name, result in benchmarks.items():
            if 'error' not in result:
                # Simple scoring based on performance metrics
                if name == 'numpy_operations' and 'operations_per_second' in result:
                    score = min(100, result['operations_per_second'] / 10)
                    total_score += score
                    valid_benchmarks += 1
                elif name == 'data_serialization' and 'methods' in result:
                    best_time = min(v for v in result['methods'].values() if v is not None)
                    score = min(100, 1 / best_time * 100)
                    total_score += score
                    valid_benchmarks += 1
                elif name == 'async_operations' and 'tasks_per_second' in result:
                    score = min(100, result['tasks_per_second'] / 10)
                    total_score += score
                    valid_benchmarks += 1
                elif name == 'performance_wrappers' and 'records_per_second' in result:
                    score = min(100, result['records_per_second'] / 100)
                    total_score += score
                    valid_benchmarks += 1

        overall_score = total_score / valid_benchmarks if valid_benchmarks > 0 else 0

        return {
            'system_info': self.system_info,
            'benchmarks': benchmarks,
            'overall_performance_score': overall_score,
            'benchmark_duration': str(self.end_time - self.start_time),
            'timestamp': datetime.now().isoformat()
        }

    def save_results(self, results: Dict, filename: str = None):
        """Save benchmark results to file"""
        if filename is None:
            filename = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"Benchmark results saved to {filename}")
            return filename

        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return None

    def generate_report(self, results: Dict) -> str:
        """Generate human-readable benchmark report"""
        report = []
        report.append("=" * 60)
        report.append("FORTRESS TRADING SYSTEM - PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {results['timestamp']}")
        report.append(f"Duration: {results['benchmark_duration']}")
        report.append(f"Overall Performance Score: {results['overall_performance_score']:.1f}/100")
        report.append("")

        # System Information
        if 'system_info' in results:
            report.append("SYSTEM INFORMATION:")
            report.append("-" * 30)
            system = results['system_info']

            if 'cpu' in system:
                cpu = system['cpu']
                report.append(f"CPU Cores: {cpu.get('physical_cores', 'N/A')} physical, {cpu.get('logical_cores', 'N/A')} logical")
                if cpu.get('cpu_freq'):
                    report.append(f"CPU Frequency: {cpu['cpu_freq'].get('current', 'N/A')} MHz")

            if 'memory' in system:
                memory = system['memory']
                report.append(f"Total Memory: {memory.get('total', 0) / (1024**3):.1f} GB")
                report.append(f"Available Memory: {memory.get('available', 0) / (1024**3):.1f} GB")

            report.append("")

        # Benchmark Results
        benchmarks = results.get('benchmarks', {})

        if 'numpy_operations' in benchmarks and 'error' not in benchmarks['numpy_operations']:
            report.append("NUMPY OPERATIONS BENCHMARK:")
            report.append("-" * 30)
            numpy = benchmarks['numpy_operations']
            report.append(f"Total Time: {numpy['total_time']:.3f}s")
            report.append(f"Operations/Second: {numpy['operations_per_second']:.1f}")
            report.append(f"Data Size: {numpy['data_size']} elements")
            report.append(f"Memory Usage: {numpy['memory_usage_mb']:.1f} MB")

            if 'operations' in numpy:
                report.append("Operation Times:")
                for op, time_val in numpy['operations'].items():
                    report.append(f"  {op}: {time_val:.4f}s")
            report.append("")

        if 'data_serialization' in benchmarks and 'error' not in benchmarks['data_serialization']:
            report.append("DATA SERIALIZATION BENCHMARK:")
            report.append("-" * 30)
            serialization = benchmarks['data_serialization']
            report.append(f"Sample Size: {serialization['sample_size']} records")

            if 'methods' in serialization:
                report.append("Serialization Times:")
                for method, time_val in serialization['methods'].items():
                    if time_val is not None:
                        report.append(f"  {method}: {time_val:.4f}s")
                    else:
                        report.append(f"  {method}: Not available")

                if serialization.get('best_method'):
                    report.append(f"Best Method: {serialization['best_method']}")
            report.append("")

        if 'async_operations' in benchmarks and 'error' not in benchmarks['async_operations']:
            report.append("ASYNC OPERATIONS BENCHMARK:")
            report.append("-" * 30)
            async_ops = benchmarks['async_operations']
            report.append(f"Total Time: {async_ops['total_time']:.3f}s")
            report.append(f"Tasks/Second: {async_ops['tasks_per_second']:.1f}")
            report.append(f"Tasks Completed: {async_ops['tasks_completed']}")
            report.append("")

        if 'memory_usage' in benchmarks and 'error' not in benchmarks['memory_usage']:
            report.append("MEMORY USAGE BENCHMARK:")
            report.append("-" * 30)
            memory = benchmarks['memory_usage']
            report.append(f"Initial Memory: {memory['initial_memory_mb']:.1f} MB")
            report.append(f"Peak Memory: {memory['peak_memory_mb']:.1f} MB")
            report.append(f"Final Memory: {memory['final_memory_mb']:.1f} MB")
            report.append(f"Memory Increase: {memory['memory_increase_mb']:.1f} MB")
            report.append(f"Memory Released: {memory['memory_released_mb']:.1f} MB")
            report.append(f"Total Time: {memory['total_time']:.3f}s")
            report.append("")

        if 'performance_wrappers' in benchmarks and 'error' not in benchmarks['performance_wrappers']:
            report.append("PERFORMANCE WRAPPERS BENCHMARK:")
            report.append("-" * 30)
            wrappers = benchmarks['performance_wrappers']
            report.append(f"Data Processing Time: {wrappers['data_processing_time']:.3f}s")
            report.append(f"Total Time: {wrappers['total_time']:.3f}s")
            report.append(f"Records Processed: {wrappers['records_processed']}")
            report.append(f"Records/Second: {wrappers['records_per_second']:.1f}")
            report.append(f"Memory Optimization: {wrappers['memory_optimization_result']:.1f}%")
            report.append("")

        report.append("=" * 60)
        report.append("END OF BENCHMARK REPORT")
        report.append("=" * 60)

        return "\n".join(report)

def main():
    """Main benchmark function"""
    print("🚀 Starting Comprehensive Benchmarking System...")
    print("=" * 60)

    benchmark = ComprehensiveBenchmark()

    try:
        # Run all benchmarks
        results = benchmark.run_all_benchmarks()

        # Generate and display report
        report = benchmark.generate_report(results)
        print(report)

        # Save results
        filename = benchmark.save_results(results)
        if filename:
            print(f"\n📊 Results saved to: {filename}")

        # Performance recommendations
        print("\n🔧 PERFORMANCE RECOMMENDATIONS:")
        print("-" * 40)

        score = results.get('overall_performance_score', 0)
        if score >= 80:
            print("✅ Excellent performance! System is well-optimized.")
        elif score >= 60:
            print("⚠️  Good performance, but there are optimization opportunities.")
            print("   - Consider enabling more Numba optimizations")
            print("   - Review memory usage patterns")
        elif score >= 40:
            print("⚠️  Moderate performance, significant optimizations needed.")
            print("   - Enable Numba JIT compilation for critical functions")
            print("   - Implement async processing for I/O operations")
            print("   - Review and optimize data structures")
        else:
            print("❌ Poor performance, major optimizations required.")
            print("   - Implement comprehensive performance optimizations")
            print("   - Consider Rust extensions for critical operations")
            print("   - Review system architecture and bottlenecks")

        print(f"\n🎯 Overall Score: {score:.1f}/100")

        return 0

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
