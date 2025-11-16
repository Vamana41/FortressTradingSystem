#!/usr/bin/env python3
"""
System-wide Memory Investigation Script
Identifies memory hogs and leaks across the entire system
"""

import psutil
import os
import time
import json
from pathlib import Path
import subprocess

def get_system_memory_breakdown():
    """Get detailed system memory breakdown"""
    print("🔍 SYSTEM-WIDE MEMORY INVESTIGATION")
    print("=" * 60)

    # System memory info
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    print(f"📊 SYSTEM MEMORY OVERVIEW:")
    print(f"   Total Physical Memory: {memory.total / (1024**3):.1f} GB")
    print(f"   Used Memory: {memory.used / (1024**3):.1f} GB ({memory.percent:.1f}%)")
    print(f"   Available Memory: {memory.available / (1024**3):.1f} GB")
    print(f"   Free Memory: {memory.free / (1024**3):.1f} GB")
    print(f"   Cached Memory: {getattr(memory, 'cached', 0) / (1024**3):.1f} GB")
    print(f"   Buffered Memory: {getattr(memory, 'buffers', 0) / (1024**3):.1f} GB")
    print(f"   Shared Memory: {getattr(memory, 'shared', 0) / (1024**3):.1f} GB")
    print(f"   Slab Memory: {getattr(memory, 'slab', 0) / (1024**3):.1f} GB")

    print(f"\n💾 SWAP MEMORY:")
    print(f"   Total Swap: {swap.total / (1024**3):.1f} GB")
    print(f"   Used Swap: {swap.used / (1024**3):.1f} GB ({swap.percent:.1f}%)")
    print(f"   Free Swap: {swap.free / (1024**3):.1f} GB")

    return {
        'total_gb': memory.total / (1024**3),
        'used_gb': memory.used / (1024**3),
        'available_gb': memory.available / (1024**3),
        'percent': memory.percent,
        'cached_gb': getattr(memory, 'cached', 0) / (1024**3),
            'buffers_gb': getattr(memory, 'buffers', 0) / (1024**3)
    }

def find_memory_hog_processes():
    """Find processes consuming the most memory"""
    print(f"\n🔥 TOP MEMORY CONSUMING PROCESSES:")
    print("-" * 60)

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent', 'cpu_percent', 'create_time']):
        try:
            pinfo = proc.info
            if pinfo['memory_info']:
                memory_mb = pinfo['memory_info'].rss / (1024**2)
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'memory_mb': memory_mb,
                    'memory_percent': pinfo['memory_percent'],
                    'cpu_percent': pinfo['cpu_percent'],
                    'create_time': pinfo['create_time']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort by memory usage
    processes.sort(key=lambda x: x['memory_mb'], reverse=True)

    total_memory_mb = psutil.virtual_memory().total / (1024**2)

    print(f"{'PID':<8} {'Name':<25} {'Memory MB':<12} {'Memory %':<10} {'CPU %':<8}")
    print("-" * 60)

    memory_hogs = []
    for proc in processes[:20]:  # Top 20 processes
        print(f"{proc['pid']:<8} {proc['name'][:24]:<25} {proc['memory_mb']:<12.1f} {proc['memory_percent']:<10.1f} {proc['cpu_percent'] or 0:<8.1f}")

        # Flag processes using > 500MB as potential memory hogs
        if proc['memory_mb'] > 500:
            memory_hogs.append(proc)

    return memory_hogs

def check_python_processes():
    """Check specifically for Python processes"""
    print(f"\n🐍 PYTHON PROCESSES (Potential Trading System Components):")
    print("-" * 60)

    python_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'memory_percent']):
        try:
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                memory_mb = proc.info['memory_info'].rss / (1024**2)

                python_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline,
                    'memory_mb': memory_mb,
                    'memory_percent': proc.info['memory_percent']
                })

                # Show process details
                print(f"PID: {proc.info['pid']}")
                print(f"   Memory: {memory_mb:.1f} MB ({proc.info['memory_percent']:.1f}%)")
                print(f"   Command: {cmdline[:80]}...")
                print()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return python_processes

def investigate_memory_leaks():
    """Investigate potential memory leaks"""
    print(f"\n🕵️ MEMORY LEAK INVESTIGATION:")
    print("-" * 60)

    # Check for processes with unusually high memory growth
    print("Checking for memory growth patterns...")

    suspicious_processes = []

    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'create_time']):
        try:
            memory_mb = proc.info['memory_info'].rss / (1024**2)
            runtime_hours = (time.time() - proc.info['create_time']) / 3600

            # Flag processes that are using > 1GB and running for a while
            if memory_mb > 1024 and runtime_hours > 1:
                suspicious_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'memory_mb': memory_mb,
                    'runtime_hours': runtime_hours,
                    'memory_per_hour': memory_mb / runtime_hours
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if suspicious_processes:
        print("⚠️  POTENTIAL MEMORY LEAKS DETECTED:")
        for proc in sorted(suspicious_processes, key=lambda x: x['memory_mb'], reverse=True)[:10]:
            print(f"   PID {proc['pid']} ({proc['name']}): {proc['memory_mb']:.1f}MB, running {proc['runtime_hours']:.1f}h")
    else:
        print("✅ No obvious memory leaks detected")

    return suspicious_processes

def check_system_services():
    """Check system services and background processes"""
    print(f"\n⚙️ SYSTEM SERVICES & BACKGROUND PROCESSES:")
    print("-" * 60)

    # Common Windows services that might consume memory
    service_keywords = ['sql', 'chrome', 'firefox', 'edge', 'antivirus', 'defender', 'update', 'backup', 'sync']

    service_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'username']):
        try:
            name = proc.info['name'].lower()
            memory_mb = proc.info['memory_info'].rss / (1024**2)

            # Check if it's a potential service
            if any(keyword in name for keyword in service_keywords) and memory_mb > 100:
                service_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'memory_mb': memory_mb,
                    'user': proc.info['username']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if service_processes:
        print("🔄 BACKGROUND SERVICES USING SIGNIFICANT MEMORY:")
        for proc in sorted(service_processes, key=lambda x: x['memory_mb'], reverse=True)[:15]:
            print(f"   {proc['name']} (PID: {proc['pid']}): {proc['memory_mb']:.1f}MB - User: {proc['user']}")

    return service_processes

def check_browser_processes():
    """Check browser processes which are often memory hogs"""
    print(f"\n🌐 BROWSER PROCESSES (Major Memory Consumers):")
    print("-" * 60)

    browser_keywords = ['chrome', 'firefox', 'edge', 'opera', 'safari', 'brave']
    browser_processes = []

    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            name = proc.info['name'].lower()
            memory_mb = proc.info['memory_info'].rss / (1024**2)

            if any(browser in name for browser in browser_keywords) and memory_mb > 50:
                browser_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'memory_mb': memory_mb
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if browser_processes:
        total_browser_memory = sum(p['memory_mb'] for p in browser_processes)
        print(f"📊 TOTAL BROWSER MEMORY: {total_browser_memory:.1f} MB")
        print("Individual processes:")
        for proc in sorted(browser_processes, key=lambda x: x['memory_mb'], reverse=True)[:10]:
            print(f"   {proc['name']} (PID: {proc['pid']}): {proc['memory_mb']:.1f} MB")
    else:
        print("✅ No browser processes detected")

    return browser_processes

def generate_recommendations(memory_hogs, python_processes, browser_processes):
    """Generate memory optimization recommendations"""
    print(f"\n💡 MEMORY OPTIMIZATION RECOMMENDATIONS:")
    print("-" * 60)

    recommendations = []

    # Browser recommendations
    total_browser_mb = sum(p['memory_mb'] for p in browser_processes)
    if total_browser_mb > 1000:
        recommendations.append(f"🌐 Close unnecessary browser tabs (saving ~{total_browser_mb:.0f}MB)")

    # Python process recommendations
    total_python_mb = sum(p['memory_mb'] for p in python_processes)
    if total_python_mb > 2000:
        recommendations.append(f"🐍 Review Python processes using {total_python_mb:.0f}MB total")

    # Memory hog recommendations
    if memory_hogs:
        total_hog_mb = sum(p['memory_mb'] for p in memory_hogs[:5])
        recommendations.append(f"🐷 Top 5 memory hogs use {total_hog_mb:.0f}MB - consider restarting them")

    # System recommendations
    memory = psutil.virtual_memory()
    if memory.percent > 80:
        recommendations.append("🔧 Consider restarting the system to clear cached memory")
        recommendations.append("💾 Check for Windows updates that might need restart")

    # Specific recommendations based on findings
    for rec in recommendations:
        print(f"   {rec}")

    if not recommendations:
        print("   ✅ Memory usage appears normal")

    return recommendations

def main():
    """Main investigation function"""
    try:
        # Get system memory breakdown
        system_memory = get_system_memory_breakdown()

        # Find memory hogs
        memory_hogs = find_memory_hog_processes()

        # Check Python processes specifically
        python_processes = check_python_processes()

        # Check browser processes
        browser_processes = check_browser_processes()

        # Investigate memory leaks
        suspicious_processes = investigate_memory_leaks()

        # Check system services
        service_processes = check_system_services()

        # Generate recommendations
        recommendations = generate_recommendations(memory_hogs, python_processes, browser_processes)

        # Save detailed report
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'system_memory': system_memory,
            'memory_hogs': memory_hogs[:10],
            'python_processes': python_processes,
            'browser_processes': browser_processes,
            'suspicious_processes': suspicious_processes[:5],
            'service_processes': service_processes[:10],
            'recommendations': recommendations
        }

        with open('system_memory_investigation.json', 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📋 Detailed report saved to: system_memory_investigation.json")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Investigation error: {e}")

if __name__ == "__main__":
    main()
