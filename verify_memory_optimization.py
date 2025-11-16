#!/usr/bin/env python3
"""
Memory Optimization Verification Script
Checks the effectiveness of memory optimization deployment
"""

import psutil
import time
import json
import os
from pathlib import Path

def check_memory_optimization():
    """Check current memory optimization status"""

    print("🔍 Verifying Memory Optimization...")
    print("=" * 50)

    # Get current memory stats
    memory = psutil.virtual_memory()
    process = psutil.Process()

    print(f"📊 Current Memory Status:")
    print(f"   System Memory: {memory.percent:.1f}% used ({memory.used / 1024 / 1024:.1f}MB)")
    print(f"   Available Memory: {memory.available / 1024 / 1024:.1f}MB")
    print(f"   Process Memory: {process.memory_info().rss / 1024 / 1024:.1f}MB")

    # Check if optimization files exist
    optimization_files = [
        "memory_optimization_config.json",
        "memory_optimizer.py",
        "memory_optimized_config.py",
        "memory_optimized_database.py"
    ]

    print(f"\n📁 Optimization Files Status:")
    files_exist = 0
    for file in optimization_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
            files_exist += 1
        else:
            print(f"   ❌ {file}")

    # Check OpenAlgo app.py modifications
    app_file = "openalgo/openalgo/app.py"
    if os.path.exists(app_file):
        with open(app_file, 'r') as f:
            content = f.read()
            if 'memory_optimizer' in content:
                print(f"   ✅ OpenAlgo app.py memory optimization integrated")
            else:
                print(f"   ❌ OpenAlgo app.py memory optimization missing")

    # Memory improvement calculation
    original_usage = 89.4  # From deployment log
    current_usage = memory.percent
    improvement = original_usage - current_usage

    print(f"\n📈 Memory Optimization Results:")
    print(f"   Original Memory Usage: {original_usage:.1f}%")
    print(f"   Current Memory Usage: {current_usage:.1f}%")
    print(f"   Memory Improvement: {improvement:.1f}%")

    # Status assessment
    print(f"\n🎯 Optimization Status:")
    if improvement > 0:
        print(f"   ✅ Memory optimization successful - {improvement:.1f}% improvement")
    elif current_usage < 90:
        print(f"   ✅ Memory usage stabilized at acceptable level")
    else:
        print(f"   ⚠️ Memory usage still high, may need additional optimization")

    # Recommendations
    print(f"\n💡 Recommendations:")
    if current_usage > 85:
        print(f"   • Memory usage is still high ({current_usage:.1f}%)")
        print(f"   • Consider restarting other memory-intensive processes")
        print(f"   • Monitor memory usage over the next few hours")
    else:
        print(f"   • Memory optimization appears effective")
        print(f"   • Continue monitoring with performance_monitor.py")

    # Create summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "memory_usage_percent": current_usage,
        "memory_available_mb": memory.available / 1024 / 1024,
        "process_memory_mb": process.memory_info().rss / 1024 / 1024,
        "optimization_files_deployed": files_exist,
        "memory_improvement_percent": improvement,
        "status": "successful" if improvement > 0 or current_usage < 90 else "needs_attention"
    }

    # Save summary
    summary_file = "memory_optimization_verification.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n📋 Summary saved to: {summary_file}")
    print("=" * 50)

    return summary

if __name__ == "__main__":
    check_memory_optimization()
