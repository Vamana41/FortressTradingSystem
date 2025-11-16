#!/usr/bin/env python3
import time
import json
import sys
import psutil
import numpy as np
from datetime import datetime
from pathlib import Path

# Simple performance benchmark
def benchmark_cpu():
    print("CPU Benchmark...")
    start = time.time()
    
    # Simple calculation
    total = 0
    for i in range(1000000):
        total += i * i
    
    cpu_time = time.time() - start
    print(f"CPU time: {cpu_time:.4f}s")
    return cpu_time

def benchmark_memory():
    print("Memory Benchmark...")
    process = psutil.Process()
    
    start_memory = process.memory_info().rss / 1024 / 1024
    
    # Allocate memory
    data = [np.random.randn(1000) for _ in range(100)]
    
    peak_memory = process.memory_info().rss / 1024 / 1024
    
    print(f"Memory: Start={start_memory:.2f}MB, Peak={peak_memory:.2f}MB")
    return peak_memory - start_memory

def benchmark_numpy():
    print("NumPy Benchmark...")
    
    size = 1000
    a = np.random.randn(size, size)
    b = np.random.randn(size, size)
    
    start = time.time()
    c = np.dot(a, b)
    numpy_time = time.time() - start
    
    print(f"NumPy: {size}x{size} multiplication in {numpy_time:.4f}s")
    return numpy_time

def main():
    print("Fortress Trading System - Performance Benchmark")
    print("=" * 50)
    
    results = {
        'cpu_time': benchmark_cpu(),
        'memory_increase': benchmark_memory(),
        'numpy_time': benchmark_numpy(),
        'timestamp': datetime.now().isoformat(),
        'python_version': sys.version
    }
    
    # Save results
    results_file = f"simple_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {results_file}")

if __name__ == "__main__":
    main()
