#!/usr/bin/env python3
"""
System Status Dashboard for Fortress Trading System
Real-time monitoring of all system components
"""

import time
import json
import psutil
import asyncio
import aiohttp
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import sys
import threading
from collections import deque
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - DASHBOARD - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemStatusDashboard:
    """Real-time system status dashboard"""
    
    def __init__(self):
        self.running = False
        self.update_interval = 5  # seconds
        self.metrics_history = deque(maxlen=1000)
        self.component_status = {}
        self.alerts = deque(maxlen=100)
        self.dashboard_thread = None
        
        # Component URLs and ports
        self.components = {
            'openalgo': {'url': 'http://localhost:5000', 'port': 5000, 'type': 'api'},
            'fortress': {'url': 'http://localhost:8080', 'port': 8080, 'type': 'api'},
            'redis': {'url': 'redis://localhost:6379', 'port': 6379, 'type': 'database'},
            'rtd_ws': {'url': 'ws://localhost:8765', 'port': 8765, 'type': 'websocket'}
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def get_system_metrics(self) -> Dict:
        """Collect comprehensive system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                except:
                    continue
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Process metrics
            current_process = psutil.Process()
            process_info = {
                'pid': current_process.pid,
                'name': current_process.name(),
                'memory_mb': current_process.memory_info().rss / (1024 * 1024),
                'cpu_percent': current_process.cpu_percent(),
                'num_threads': current_process.num_threads(),
                'open_files': len(current_process.open_files()),
                'connections': len(current_process.connections())
            }
            
            # Python-specific metrics
            import gc
            gc_stats = {
                'collections': gc.get_stats(),
                'thresholds': gc.get_threshold(),
                'count': gc.get_count()
            }
            
            return {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency': cpu_freq.current if cpu_freq else None,
                    'per_cpu': psutil.cpu_percent(percpu=True, interval=0.1)
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory.percent,
                    'swap_total': swap.total,
                    'swap_used': swap.used,
                    'swap_percent': swap.percent
                },
                'disk': disk_usage,
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'process': process_info,
                'python': {
                    'version': sys.version,
                    'gc_stats': gc_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {'error': str(e)}
    
    async def check_component_health(self, name: str, config: Dict) -> Dict:
        """Check health of a specific component"""
        try:
            start_time = time.time()
            
            if config['type'] == 'api':
                # Check API endpoint
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    try:
                        async with session.get(f"{config['url']}/api/v1/ping") as response:
                            response_time = (time.time() - start_time) * 1000  # ms
                            return {
                                'name': name,
                                'status': 'healthy' if response.status == 200 else 'unhealthy',
                                'response_time_ms': response_time,
                                'status_code': response.status,
                                'last_check': datetime.now().isoformat()
                            }
                    except Exception as e:
                        return {
                            'name': name,
                            'status': 'down',
                            'error': str(e),
                            'response_time_ms': (time.time() - start_time) * 1000,
                            'last_check': datetime.now().isoformat()
                        }
            
            elif config['type'] == 'websocket':
                # Check WebSocket connection
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(config['url']) as ws:
                            await ws.close()
                            response_time = (time.time() - start_time) * 1000
                            return {
                                'name': name,
                                'status': 'healthy',
                                'response_time_ms': response_time,
                                'last_check': datetime.now().isoformat()
                            }
                except Exception as e:
                    return {
                        'name': name,
                        'status': 'down',
                        'error': str(e),
                        'response_time_ms': (time.time() - start_time) * 1000,
                        'last_check': datetime.now().isoformat()
                    }
            
            elif config['type'] == 'database':
                # For Redis, we'll just check if port is open
                import socket
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex(('localhost', config['port']))
                    sock.close()
                    response_time = (time.time() - start_time) * 1000
                    return {
                        'name': name,
                        'status': 'healthy' if result == 0 else 'down',
                        'response_time_ms': response_time,
                        'last_check': datetime.now().isoformat()
                    }
                except Exception as e:
                    return {
                        'name': name,
                        'status': 'down',
                        'error': str(e),
                        'response_time_ms': (time.time() - start_time) * 1000,
                        'last_check': datetime.now().isoformat()
                    }
            
        except Exception as e:
            return {
                'name': name,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def check_all_components(self) -> Dict:
        """Check health of all components"""
        tasks = []
        for name, config in self.components.items():
            tasks.append(self.check_component_health(name, config))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        component_status = {}
        for result in results:
            if isinstance(result, dict):
                component_status[result['name']] = result
            else:
                # Handle exceptions
                logger.error(f"Component check failed: {result}")
        
        return component_status
    
    def check_alerts(self, metrics: Dict, component_status: Dict):
        """Check for system alerts"""
        alerts = []
        
        # CPU alerts
        if 'cpu' in metrics and metrics['cpu']['percent'] > 80:
            alerts.append({
                'level': 'warning',
                'type': 'cpu',
                'message': f"High CPU usage: {metrics['cpu']['percent']:.1f}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # Memory alerts
        if 'memory' in metrics and metrics['memory']['percent'] > 85:
            alerts.append({
                'level': 'critical',
                'type': 'memory',
                'message': f"High memory usage: {metrics['memory']['percent']:.1f}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # Disk alerts
        if 'disk' in metrics:
            for mount, usage in metrics['disk'].items():
                if usage['percent'] > 90:
                    alerts.append({
                        'level': 'critical',
                        'type': 'disk',
                        'message': f"High disk usage on {mount}: {usage['percent']:.1f}%",
                        'timestamp': datetime.now().isoformat()
                    })
        
        # Component health alerts
        for name, status in component_status.items():
            if status['status'] != 'healthy':
                alerts.append({
                    'level': 'critical' if status['status'] == 'down' else 'warning',
                    'type': 'component',
                    'message': f"Component {name} is {status['status']}",
                    'component': name,
                    'timestamp': datetime.now().isoformat()
                })
        
        # Add alerts to history
        for alert in alerts:
            self.alerts.append(alert)
            logger.warning(f"ALERT: {alert['message']}")
        
        return alerts
    
    def format_dashboard_output(self, metrics: Dict, component_status: Dict, alerts: List) -> str:
        """Format dashboard output for display"""
        output = []
        
        # Header
        output.append("=" * 80)
        output.append(f"FORTRESS TRADING SYSTEM - STATUS DASHBOARD")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("=" * 80)
        
        # System Metrics
        if 'error' not in metrics:
            output.append("\n📊 SYSTEM METRICS:")
            output.append("-" * 40)
            
            # CPU
            cpu = metrics.get('cpu', {})
            cpu_status = "🔴" if cpu.get('percent', 0) > 80 else "🟡" if cpu.get('percent', 0) > 60 else "🟢"
            output.append(f"{cpu_status} CPU: {cpu.get('percent', 0):.1f}% ({cpu.get('count', 0)} cores)")
            
            # Memory
            memory = metrics.get('memory', {})
            memory_status = "🔴" if memory.get('percent', 0) > 85 else "🟡" if memory.get('percent', 0) > 70 else "🟢"
            output.append(f"{memory_status} Memory: {memory.get('percent', 0):.1f}% ({memory.get('used', 0) / (1024**3):.1f}GB used)")
            
            # Process
            process = metrics.get('process', {})
            output.append(f"📈 Process: {process.get('memory_mb', 0):.1f}MB memory, {process.get('cpu_percent', 0):.1f}% CPU")
            
            # Disk
            disk = metrics.get('disk', {})
            for mount, usage in disk.items():
                disk_status = "🔴" if usage['percent'] > 90 else "🟡" if usage['percent'] > 80 else "🟢"
                output.append(f"{disk_status} Disk {mount}: {usage['percent']:.1f}% full")
        
        # Component Status
        output.append("\n🔧 COMPONENT STATUS:")
        output.append("-" * 40)
        
        for name, status in component_status.items():
            health_icon = "✅" if status['status'] == 'healthy' else "❌" if status['status'] == 'down' else "⚠️"
            response_time = status.get('response_time_ms', 0)
            output.append(f"{health_icon} {name.upper()}: {status['status'].upper()} ({response_time:.0f}ms)")
        
        # Recent Alerts
        if alerts:
            output.append("\n🚨 RECENT ALERTS:")
            output.append("-" * 40)
            for alert in alerts[-5:]:  # Show last 5 alerts
                level_icon = "🔴" if alert['level'] == 'critical' else "🟡"
                output.append(f"{level_icon} {alert['type'].upper()}: {alert['message']}")
        
        # Footer
        output.append("\n" + "=" * 80)
        output.append("Press Ctrl+C to stop monitoring")
        output.append("=" * 80)
        
        return "\n".join(output)
    
    async def update_dashboard(self):
        """Update dashboard with current metrics"""
        try:
            # Collect system metrics
            metrics = self.get_system_metrics()
            
            # Check component health
            component_status = await self.check_all_components()
            
            # Check for alerts
            alerts = self.check_alerts(metrics, component_status)
            
            # Store metrics history
            self.metrics_history.append({
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'components': component_status,
                'alerts': alerts
            })
            
            # Update component status
            self.component_status = component_status
            
            # Format and display output
            output = self.format_dashboard_output(metrics, component_status, alerts)
            
            # Clear screen and display (simple approach)
            print("\n" * 50)  # Clear screen
            print(output)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
            return False
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting system status dashboard...")
        
        while self.running:
            try:
                await self.update_dashboard()
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.update_interval)
    
    def start(self):
        """Start the dashboard"""
        if self.running:
            logger.warning("Dashboard already running")
            return
        
        self.running = True
        logger.info("System dashboard started")
        
        try:
            asyncio.run(self.monitor_loop())
        except KeyboardInterrupt:
            logger.info("Dashboard stopped by user")
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the dashboard"""
        self.running = False
        logger.info("System dashboard stopped")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def save_metrics_history(self, filename: str = None):
        """Save metrics history to file"""
        if filename is None:
            filename = f"system_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            data = {
                'system_info': {
                    'platform': sys.platform,
                    'python_version': sys.version,
                    'timestamp': datetime.now().isoformat()
                },
                'metrics_history': list(self.metrics_history),
                'total_records': len(self.metrics_history)
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Metrics history saved to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving metrics history: {e}")
            return None

def main():
    """Main function"""
    print("🚀 Starting Fortress Trading System Status Dashboard...")
    print("Initializing monitoring components...")
    
    dashboard = SystemStatusDashboard()
    
    try:
        dashboard.start()
    except KeyboardInterrupt:
        print("\n\nDashboard stopped by user.")
        # Save metrics before exit
        filename = dashboard.save_metrics_history()
        if filename:
            print(f"Metrics saved to: {filename}")
    except Exception as e:
        print(f"\nDashboard error: {e}")

if __name__ == "__main__":
    main()