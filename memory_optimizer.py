#!/usr/bin/env python3
"""
Memory Optimization Utility for Fortress Trading System
Provides aggressive memory optimization and monitoring
"""

import gc
import psutil
import logging
import logging.handlers
import threading
import time
import weakref
from collections import OrderedDict
from contextlib import contextmanager
import functools
import sys
import os

class MemoryOptimizer:
    """Advanced memory optimization utility"""
    
    def __init__(self, config_file="memory_optimization_enhanced.json"):
        self.config = self.load_config(config_file)
        self.running = False
        self.monitor_thread = None
        self.optimization_thread = None
        self.object_cache = weakref.WeakValueDictionary()
        self.setup_logging()
        
    def setup_logging(self):
        """Setup optimized logging"""
        logging.basicConfig(
            level=logging.WARNING,  # Reduce log verbosity
            format='%(asctime)s - MEMORY_OPT - %(levelname)s - %(message)s',
            handlers=[
                logging.handlers.RotatingFileHandler(
                    'memory_optimization.log',
                    maxBytes=self.config.get('logging_optimization', {}).get('max_log_size_mb', 100) * 1024 * 1024,
                    backupCount=self.config.get('logging_optimization', {}).get('log_backup_count', 3)
                )
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self, config_file):
        """Load memory optimization configuration"""
        try:
            import json
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self.get_default_config()
    
    def get_default_config(self):
        """Get default memory optimization configuration"""
        return {
            "garbage_collection": {
                "enabled": True,
                "interval_seconds": 120,
                "aggressive_mode": True
            },
            "memory_profiling": {
                "enabled": True,
                "log_interval_seconds": 30,
                "max_memory_mb": 2048,
                "alert_threshold_percent": 75,
                "critical_threshold_percent": 85
            }
        }
    
    def start_optimization(self):
        """Start memory optimization threads"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_memory, daemon=True)
        self.optimization_thread = threading.Thread(target=self._optimize_memory, daemon=True)
        
        self.monitor_thread.start()
        self.optimization_thread.start()
        
        self.logger.info("Memory optimization started")
    
    def stop_optimization(self):
        """Stop memory optimization threads"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        if self.optimization_thread:
            self.optimization_thread.join(timeout=5)
        self.logger.info("Memory optimization stopped")
    
    def _monitor_memory(self):
        """Monitor memory usage"""
        while self.running:
            try:
                memory = psutil.virtual_memory()
                process = psutil.Process()
                
                # Check memory thresholds
                if memory.percent > self.config['memory_profiling']['critical_threshold_percent']:
                    self.logger.critical(f"CRITICAL MEMORY USAGE: {memory.percent:.1f}%")
                    self._emergency_cleanup()
                elif memory.percent > self.config['memory_profiling']['alert_threshold_percent']:
                    self.logger.warning(f"High memory usage: {memory.percent:.1f}%")
                
                # Log memory stats
                self.logger.debug(f"Memory: {memory.percent:.1f}%, Process: {process.memory_info().rss / 1024 / 1024:.1f}MB")
                
                time.sleep(self.config['memory_profiling']['log_interval_seconds'])
                
            except Exception as e:
                self.logger.error(f"Memory monitoring error: {e}")
                time.sleep(60)
    
    def _optimize_memory(self):
        """Perform memory optimization"""
        while self.running:
            try:
                # Aggressive garbage collection
                if self.config['garbage_collection']['aggressive_mode']:
                    gc.collect(2)  # Collect all generations
                    gc.collect(1)
                    gc.collect(0)
                else:
                    gc.collect(0)  # Only young generation
                
                # Clear large objects
                self._clear_large_objects()
                
                # Optimize string interning
                self._optimize_strings()
                
                time.sleep(self.config['garbage_collection']['interval_seconds'])
                
            except Exception as e:
                self.logger.error(f"Memory optimization error: {e}")
                time.sleep(60)
    
    def _emergency_cleanup(self):
        """Emergency memory cleanup"""
        self.logger.critical("Performing emergency memory cleanup")
        
        # Force multiple garbage collection cycles
        for i in range(3):
            gc.collect(i)
        
        # Clear all caches
        self.object_cache.clear()
        
        # Force Python to release memory
        if hasattr(sys, 'malloc_state'):
            sys.malloc_state = None
    
    def _clear_large_objects(self):
        """Clear large temporary objects"""
        # Clear large lists and dicts from globals
        for name, obj in list(globals().items()):
            if hasattr(obj, '__sizeof__'):
                size = obj.__sizeof__()
                if size > 1024 * 1024:  # > 1MB
                    self.logger.debug(f"Clearing large object: {name} ({size} bytes)")
                    globals()[name] = None
    
    def _optimize_strings(self):
        """Optimize string memory usage"""
        # Enable string interning for common strings
        common_strings = ['buy', 'sell', 'market', 'limit', 'open', 'close', 'high', 'low']
        for s in common_strings:
            intern(s)
    
    @contextmanager
    def memory_context(self):
        """Context manager for memory-intensive operations"""
        initial_memory = psutil.Process().memory_info().rss
        try:
            yield
        finally:
            # Force cleanup after memory-intensive operation
            gc.collect(0)
            final_memory = psutil.Process().memory_info().rss
            self.logger.debug(f"Memory context: {((final_memory - initial_memory) / 1024 / 1024):.1f}MB change")
    
    def memory_optimized_cache(maxsize=128):
        """Decorator for memory-optimized caching"""
        def decorator(func):
            cache = OrderedDict()
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                key = str(args) + str(kwargs)
                if key in cache:
                    # Move to end (LRU)
                    value = cache.pop(key)
                    cache[key] = value
                    return value
                
                result = func(*args, **kwargs)
                
                # Add to cache
                cache[key] = result
                cache.move_to_end(key)
                
                # Maintain cache size
                while len(cache) > maxsize:
                    cache.popitem(last=False)
                
                return result
            
            return wrapper
        return decorator

# Global memory optimizer instance
memory_optimizer = MemoryOptimizer()

def optimize_memory():
    """Quick memory optimization function"""
    gc.collect()
    if hasattr(memory_optimizer, 'object_cache'):
        memory_optimizer.object_cache.clear()

def get_memory_stats():
    """Get current memory statistics"""
    memory = psutil.virtual_memory()
    process = psutil.Process()
    return {
        'system_memory_percent': memory.percent,
        'system_memory_available_mb': memory.available / 1024 / 1024,
        'process_memory_mb': process.memory_info().rss / 1024 / 1024,
        'process_memory_percent': process.memory_percent()
    }

if __name__ == "__main__":
    # Start memory optimization
    memory_optimizer.start_optimization()
    
    try:
        while True:
            stats = get_memory_stats()
            print(f"Memory: {stats['system_memory_percent']:.1f}% | Process: {stats['process_memory_mb']:.1f}MB")
            time.sleep(30)
    except KeyboardInterrupt:
        memory_optimizer.stop_optimization()