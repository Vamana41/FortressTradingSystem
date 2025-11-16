#!/usr/bin/env python3
import gc
import sys
import subprocess
from pathlib import Path

def apply_optimizations():
    # Configure GC
    gc.set_threshold(700, 10, 10)
    gc.enable()
    
    # Configure asyncio on Windows
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    print("Python 3.14 optimizations applied")

def start_fortress():
    apply_optimizations()
    
    # Start main components
    components = [
        "rtd_ws_integration_manager.py",
        "fortress_openalgo_complete_integration.py",
        "amibroker_realtime_data_solution.py"
    ]
    
    for component in components:
        if Path(component).exists():
            print(f"Starting {component}...")
            subprocess.Popen([sys.executable, component])
    
    print("Fortress Trading System started with optimizations")

if __name__ == "__main__":
    start_fortress()
