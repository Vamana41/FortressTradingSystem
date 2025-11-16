#!/usr/bin/env python3
"""
System Performance Monitor for Fortress Trading System

Comprehensive monitoring dashboard that tracks performance metrics,
system health, and provides real-time insights for optimization.
"""

import asyncio
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import psutil
import redis
import sqlite3
from collections import deque
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    thread_count: int
    load_average: Optional[List[float]] = None
    redis_connections: int = 0
    database_size_mb: float = 0.0
    response_time_ms: float = 0.0

@dataclass
class TradingMetrics:
    """Trading-specific metrics"""
    timestamp: datetime
    orders_per_second: float
    trades_executed: int
    average_order_latency_ms: float
    market_data_updates: int
    websocket_connections: int
    api_requests_per_minute: float
    error_rate_percent: float
    token_refresh_success_rate: float
    broker_connection_status: str

@dataclass
class Alert:
    """System alert"""
    timestamp: datetime
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    component: str
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None

class SystemMonitor:
    """Comprehensive system monitoring for Fortress Trading System"""

    def __init__(self):
        self.base_dir = Path.cwd()
        self.config = self.load_monitoring_config()

        # Metrics storage
        self.system_metrics_history = deque(maxlen=self.config["history_size"])
        self.trading_metrics_history = deque(maxlen=self.config["history_size"])
        self.alerts_history = deque(maxlen=self.config["alerts_history_size"])

        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread = None
        self.alert_thread = None

        # Database connection
        self.db_path = self.base_dir / "monitoring.db"
        self.init_database()

        # Redis connection
        self.redis_client = None
        self.init_redis()

        # Thresholds
        self.thresholds = self.config["thresholds"]

        logger.info("SystemMonitor initialized")

    def load_monitoring_config(self) -> Dict:
        """Load monitoring configuration"""
        config_path = self.base_dir / "system_monitoring_config.json"
        default_config = {
            "monitoring_interval_seconds": 5,
            "history_size": 1000,
            "alerts_history_size": 500,
            "database_retention_days": 7,
            "redis_host": "localhost",
            "redis_port": 6379,
            "redis_db": 0,
            "thresholds": {
                "cpu_warning": 70.0,
                "cpu_critical": 85.0,
                "memory_warning": 75.0,
                "memory_critical": 90.0,
                "disk_warning": 80.0,
                "disk_critical": 95.0,
                "response_time_warning": 1000.0,  # ms
                "response_time_critical": 2000.0,  # ms
                "error_rate_warning": 5.0,  # percent
                "error_rate_critical": 10.0,  # percent
                "orders_per_second_min": 10.0,
                "websocket_connections_min": 1
            },
            "notifications": {
                "enabled": True,
                "email_enabled": False,
                "telegram_enabled": False,
                "log_alerts": True
            }
        }

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    for key, value in loaded_config.items():
                        if key in default_config:
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            except Exception as e:
                logger.error(f"Error loading monitoring config: {e}")

        return default_config

    def init_database(self):
        """Initialize monitoring database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # System metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_used_mb REAL,
                    memory_available_mb REAL,
                    disk_usage_percent REAL,
                    network_bytes_sent INTEGER,
                    network_bytes_recv INTEGER,
                    process_count INTEGER,
                    thread_count INTEGER,
                    load_average_1m REAL,
                    load_average_5m REAL,
                    load_average_15m REAL,
                    redis_connections INTEGER,
                    database_size_mb REAL,
                    response_time_ms REAL
                )
            ''')

            # Trading metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trading_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    orders_per_second REAL,
                    trades_executed INTEGER,
                    average_order_latency_ms REAL,
                    market_data_updates INTEGER,
                    websocket_connections INTEGER,
                    api_requests_per_minute REAL,
                    error_rate_percent REAL,
                    token_refresh_success_rate REAL,
                    broker_connection_status TEXT
                )
            ''')

            # Alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    severity TEXT,
                    component TEXT,
                    message TEXT,
                    value REAL,
                    threshold REAL
                )
            ''')

            conn.commit()
            conn.close()
            logger.info("Monitoring database initialized")

        except Exception as e:
            logger.error(f"Error initializing monitoring database: {e}")

    def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=self.config["redis_host"],
                port=self.config["redis_port"],
                db=self.config["redis_db"],
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Error connecting to Redis: {e}")
            self.redis_client = None

    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()

            # Load average (Unix systems)
            load_avg = None
            if hasattr(psutil, 'getloadavg'):
                load_avg = list(psutil.getloadavg())

            # Database size
            db_size_mb = 0.0
            if self.db_path.exists():
                db_size_mb = self.db_path.stat().st_size / (1024 * 1024)

            # Redis connections
            redis_connections = 0
            if self.redis_client:
                try:
                    info = self.redis_client.info()
                    redis_connections = info.get('connected_clients', 0)
                except:
                    pass

            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=(disk.used / disk.total) * 100,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                process_count=len(psutil.pids()),
                thread_count=psutil.Process().num_threads(),
                load_average=load_avg,
                redis_connections=redis_connections,
                database_size_mb=db_size_mb
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                process_count=0,
                thread_count=0
            )

    def collect_trading_metrics(self) -> TradingMetrics:
        """Collect trading-specific metrics"""
        try:
            # This would integrate with your trading system
            # For now, we'll use placeholder values

            # Get metrics from Redis if available
            orders_per_second = 0.0
            trades_executed = 0
            avg_latency = 0.0
            market_updates = 0
            websocket_connections = 0
            api_requests = 0.0
            error_rate = 0.0
            token_success = 100.0
            broker_status = "connected"

            if self.redis_client:
                try:
                    # Try to get trading metrics from Redis
                    orders_per_second = float(self.redis_client.get('trading:orders_per_second') or 0.0)
                    trades_executed = int(self.redis_client.get('trading:trades_executed') or 0)
                    avg_latency = float(self.redis_client.get('trading:avg_latency_ms') or 0.0)
                    market_updates = int(self.redis_client.get('trading:market_data_updates') or 0)
                    websocket_connections = int(self.redis_client.get('trading:websocket_connections') or 0)
                    api_requests = float(self.redis_client.get('trading:api_requests_per_minute') or 0.0)
                    error_rate = float(self.redis_client.get('trading:error_rate') or 0.0)
                    token_success = float(self.redis_client.get('trading:token_refresh_success') or 100.0)
                    broker_status = self.redis_client.get('trading:broker_status') or "unknown"
                except:
                    pass

            metrics = TradingMetrics(
                timestamp=datetime.now(),
                orders_per_second=orders_per_second,
                trades_executed=trades_executed,
                average_order_latency_ms=avg_latency,
                market_data_updates=market_updates,
                websocket_connections=websocket_connections,
                api_requests_per_minute=api_requests,
                error_rate_percent=error_rate,
                token_refresh_success_rate=token_success,
                broker_connection_status=broker_status
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting trading metrics: {e}")
            return TradingMetrics(
                timestamp=datetime.now(),
                orders_per_second=0.0,
                trades_executed=0,
                average_order_latency_ms=0.0,
                market_data_updates=0,
                websocket_connections=0,
                api_requests_per_minute=0.0,
                error_rate_percent=0.0,
                token_refresh_success_rate=0.0,
                broker_connection_status="error"
            )

    def check_thresholds(self, system_metrics: SystemMetrics, trading_metrics: TradingMetrics) -> List[Alert]:
        """Check metrics against thresholds and generate alerts"""
        alerts = []

        # System alerts
        if system_metrics.cpu_percent > self.thresholds["cpu_critical"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="CRITICAL",
                component="CPU",
                message="CPU usage critical",
                value=system_metrics.cpu_percent,
                threshold=self.thresholds["cpu_critical"]
            ))
        elif system_metrics.cpu_percent > self.thresholds["cpu_warning"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="WARNING",
                component="CPU",
                message="CPU usage high",
                value=system_metrics.cpu_percent,
                threshold=self.thresholds["cpu_warning"]
            ))

        if system_metrics.memory_percent > self.thresholds["memory_critical"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="CRITICAL",
                component="Memory",
                message="Memory usage critical",
                value=system_metrics.memory_percent,
                threshold=self.thresholds["memory_critical"]
            ))
        elif system_metrics.memory_percent > self.thresholds["memory_warning"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="WARNING",
                component="Memory",
                message="Memory usage high",
                value=system_metrics.memory_percent,
                threshold=self.thresholds["memory_warning"]
            ))

        if system_metrics.disk_usage_percent > self.thresholds["disk_critical"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="CRITICAL",
                component="Disk",
                message="Disk usage critical",
                value=system_metrics.disk_usage_percent,
                threshold=self.thresholds["disk_critical"]
            ))
        elif system_metrics.disk_usage_percent > self.thresholds["disk_warning"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="WARNING",
                component="Disk",
                message="Disk usage high",
                value=system_metrics.disk_usage_percent,
                threshold=self.thresholds["disk_warning"]
            ))

        # Trading alerts
        if trading_metrics.error_rate_percent > self.thresholds["error_rate_critical"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="CRITICAL",
                component="Trading",
                message="Error rate critical",
                value=trading_metrics.error_rate_percent,
                threshold=self.thresholds["error_rate_critical"]
            ))
        elif trading_metrics.error_rate_percent > self.thresholds["error_rate_warning"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="WARNING",
                component="Trading",
                message="Error rate high",
                value=trading_metrics.error_rate_percent,
                threshold=self.thresholds["error_rate_warning"]
            ))

        if trading_metrics.orders_per_second < self.thresholds["orders_per_second_min"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="WARNING",
                component="Trading",
                message="Low order processing rate",
                value=trading_metrics.orders_per_second,
                threshold=self.thresholds["orders_per_second_min"]
            ))

        if trading_metrics.websocket_connections < self.thresholds["websocket_connections_min"]:
            alerts.append(Alert(
                timestamp=datetime.now(),
                severity="WARNING",
                component="WebSocket",
                message="No WebSocket connections",
                value=trading_metrics.websocket_connections,
                threshold=self.thresholds["websocket_connections_min"]
            ))

        return alerts

    def store_metrics(self, system_metrics: SystemMetrics, trading_metrics: TradingMetrics, alerts: List[Alert]):
        """Store metrics in database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Store system metrics
            cursor.execute('''
                INSERT INTO system_metrics (
                    timestamp, cpu_percent, memory_percent, memory_used_mb,
                    memory_available_mb, disk_usage_percent, network_bytes_sent,
                    network_bytes_recv, process_count, thread_count, load_average_1m,
                    load_average_5m, load_average_15m, redis_connections, database_size_mb,
                    response_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_metrics.timestamp,
                system_metrics.cpu_percent,
                system_metrics.memory_percent,
                system_metrics.memory_used_mb,
                system_metrics.memory_available_mb,
                system_metrics.disk_usage_percent,
                system_metrics.network_bytes_sent,
                system_metrics.network_bytes_recv,
                system_metrics.process_count,
                system_metrics.thread_count,
                system_metrics.load_average[0] if system_metrics.load_average else None,
                system_metrics.load_average[1] if system_metrics.load_average else None,
                system_metrics.load_average[2] if system_metrics.load_average else None,
                system_metrics.redis_connections,
                system_metrics.database_size_mb,
                system_metrics.response_time_ms
            ))

            # Store trading metrics
            cursor.execute('''
                INSERT INTO trading_metrics (
                    timestamp, orders_per_second, trades_executed,
                    average_order_latency_ms, market_data_updates,
                    websocket_connections, api_requests_per_minute,
                    error_rate_percent, token_refresh_success_rate,
                    broker_connection_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trading_metrics.timestamp,
                trading_metrics.orders_per_second,
                trading_metrics.trades_executed,
                trading_metrics.average_order_latency_ms,
                trading_metrics.market_data_updates,
                trading_metrics.websocket_connections,
                trading_metrics.api_requests_per_minute,
                trading_metrics.error_rate_percent,
                trading_metrics.token_refresh_success_rate,
                trading_metrics.broker_connection_status
            ))

            # Store alerts
            for alert in alerts:
                cursor.execute('''
                    INSERT INTO alerts (
                        timestamp, severity, component, message, value, threshold
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    alert.timestamp,
                    alert.severity,
                    alert.component,
                    alert.message,
                    alert.value,
                    alert.threshold
                ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing metrics: {e}")

    def start_monitoring(self):
        """Start system monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()

        self.alert_thread = threading.Thread(target=self._alert_processing_loop, daemon=True)
        self.alert_thread.start()

        logger.info("System monitoring started")

    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        if self.alert_thread:
            self.alert_thread.join(timeout=5)

        logger.info("System monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        interval = self.config["monitoring_interval_seconds"]

        while self.monitoring_active:
            try:
                # Collect metrics
                system_metrics = self.collect_system_metrics()
                trading_metrics = self.collect_trading_metrics()

                # Check thresholds
                alerts = self.check_thresholds(system_metrics, trading_metrics)

                # Store in history
                self.system_metrics_history.append(system_metrics)
                self.trading_metrics_history.append(trading_metrics)
                self.alerts_history.extend(alerts)

                # Store in database
                self.store_metrics(system_metrics, trading_metrics, alerts)

                # Log current status
                logger.info(f"System: CPU={system_metrics.cpu_percent:.1f}%, "
                          f"Memory={system_metrics.memory_percent:.1f}%, "
                          f"Trading: Orders={trading_metrics.orders_per_second:.1f}/s, "
                          f"Errors={trading_metrics.error_rate_percent:.1f}%")

                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval)

    def _alert_processing_loop(self):
        """Process alerts and send notifications"""
        while self.monitoring_active:
            try:
                # Process recent alerts
                recent_alerts = [alert for alert in self.alerts_history
                               if (datetime.now() - alert.timestamp).seconds < 60]

                # Send notifications for critical alerts
                for alert in recent_alerts:
                    if alert.severity in ["CRITICAL", "ERROR"]:
                        self.send_notification(alert)

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in alert processing: {e}")
                time.sleep(30)

    def send_notification(self, alert: Alert):
        """Send notification for alert"""
        if not self.config["notifications"]["enabled"]:
            return

        message = f"[{alert.severity}] {alert.component}: {alert.message}"
        if alert.value and alert.threshold:
            message += f" (Value: {alert.value:.1f}, Threshold: {alert.threshold:.1f})"

        # Log alert
        if self.config["notifications"]["log_alerts"]:
            logger.warning(message)

        # Here you would integrate with email, Telegram, etc.
        # For now, we'll just log it
        logger.info(f"Notification sent: {message}")

    def get_current_status(self) -> Dict:
        """Get current system status"""
        if not self.system_metrics_history or not self.trading_metrics_history:
            return {"status": "No data available"}

        latest_system = self.system_metrics_history[-1]
        latest_trading = self.trading_metrics_history[-1]

        return {
            "timestamp": datetime.now().isoformat(),
            "system_status": {
                "cpu_usage": latest_system.cpu_percent,
                "memory_usage": latest_system.memory_percent,
                "disk_usage": latest_system.disk_usage_percent,
                "redis_connections": latest_system.redis_connections,
                "database_size_mb": latest_system.database_size_mb
            },
            "trading_status": {
                "orders_per_second": latest_trading.orders_per_second,
                "trades_executed": latest_trading.trades_executed,
                "websocket_connections": latest_trading.websocket_connections,
                "error_rate_percent": latest_trading.error_rate_percent,
                "broker_status": latest_trading.broker_connection_status
            },
            "recent_alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "severity": alert.severity,
                    "component": alert.component,
                    "message": alert.message
                }
                for alert in list(self.alerts_history)[-5:]  # Last 5 alerts
            ]
        }

    def get_performance_report(self, hours: int = 24) -> Dict:
        """Get comprehensive performance report"""
        try:
            # Get data from last N hours
            cutoff_time = datetime.now() - timedelta(hours=hours)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Get system metrics
            cursor.execute('''
                SELECT
                    AVG(cpu_percent),
                    MAX(cpu_percent),
                    AVG(memory_percent),
                    MAX(memory_percent),
                    AVG(response_time_ms),
                    MAX(response_time_ms)
                FROM system_metrics
                WHERE timestamp > ?
            ''', (cutoff_time,))

            system_stats = cursor.fetchone()

            # Get trading metrics
            cursor.execute('''
                SELECT
                    AVG(orders_per_second),
                    MAX(orders_per_second),
                    SUM(trades_executed),
                    AVG(error_rate_percent),
                    MAX(error_rate_percent)
                FROM trading_metrics
                WHERE timestamp > ?
            ''', (cutoff_time,))

            trading_stats = cursor.fetchone()

            # Get alerts count
            cursor.execute('''
                SELECT severity, COUNT(*)
                FROM alerts
                WHERE timestamp > ?
                GROUP BY severity
            ''', (cutoff_time,))

            alerts_summary = dict(cursor.fetchall())

            conn.close()

            return {
                "period_hours": hours,
                "generated_at": datetime.now().isoformat(),
                "system_performance": {
                    "avg_cpu_percent": system_stats[0] or 0.0,
                    "max_cpu_percent": system_stats[1] or 0.0,
                    "avg_memory_percent": system_stats[2] or 0.0,
                    "max_memory_percent": system_stats[3] or 0.0,
                    "avg_response_time_ms": system_stats[4] or 0.0,
                    "max_response_time_ms": system_stats[5] or 0.0
                },
                "trading_performance": {
                    "avg_orders_per_second": trading_stats[0] or 0.0,
                    "max_orders_per_second": trading_stats[1] or 0.0,
                    "total_trades": trading_stats[2] or 0,
                    "avg_error_rate": trading_stats[3] or 0.0,
                    "max_error_rate": trading_stats[4] or 0.0
                },
                "alerts_summary": alerts_summary,
                "health_score": self.calculate_health_score(system_stats, trading_stats, alerts_summary)
            }

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {"error": str(e)}

    def calculate_health_score(self, system_stats, trading_stats, alerts_summary) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0

        # Deduct points for high resource usage
        if system_stats[0] and system_stats[0] > 70:  # avg_cpu
            score -= 10
        if system_stats[2] and system_stats[2] > 75:  # avg_memory
            score -= 10

        # Deduct points for high error rates
        if trading_stats[3] and trading_stats[3] > 5:  # avg_error_rate
            score -= 15

        # Deduct points for alerts
        critical_alerts = alerts_summary.get('CRITICAL', 0)
        error_alerts = alerts_summary.get('ERROR', 0)
        score -= (critical_alerts * 5 + error_alerts * 3)

        return max(0.0, min(100.0, score))

def main():
    """Main function for testing the monitor"""
    monitor = SystemMonitor()

    # Start monitoring
    monitor.start_monitoring()

    try:
        # Run for a short time to collect some data
        logger.info("Monitoring system for 30 seconds...")
        time.sleep(30)

        # Get current status
        status = monitor.get_current_status()
        print("\nCurrent System Status:")
        print(json.dumps(status, indent=2, default=str))

        # Get performance report
        report = monitor.get_performance_report(hours=1)
        print("\nPerformance Report:")
        print(json.dumps(report, indent=2, default=str))

    except KeyboardInterrupt:
        logger.info("Stopping monitoring...")

    finally:
        # Stop monitoring
        monitor.stop_monitoring()
        logger.info("Monitoring stopped")

if __name__ == "__main__":
    main()
