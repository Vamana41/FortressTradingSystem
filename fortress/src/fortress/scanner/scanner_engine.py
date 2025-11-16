"""
Scanner Engine for real-time market screening similar to ChartInk and PKScreener.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path

from fortress.core.event_bus import EventBus, Event
from fortress.core.events import EventType
from fortress.core.logging import get_logger
from .scanner_config import ScannerConfig, ScannerRule, ScannerResult
from .rule_parser import ChartInkStyleParser
from .indicators import IndicatorCalculator


class ScanStatus(Enum):
    """Scanner execution status."""
    IDLE = "idle"
    SCANNING = "scanning"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ScanJob:
    """Represents a scanner job."""
    job_id: str
    scanner_config: ScannerConfig
    symbols: List[str]
    timeframe: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: ScanStatus = ScanStatus.IDLE
    results: List[ScannerResult] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    total_symbols: int = 0
    processed_symbols: int = 0

    def __post_init__(self):
        if self.results is None:
            self.results = []
        self.total_symbols = len(self.symbols)


class ScannerEngine:
    """
    Real-time scanner engine for market screening.
    Similar to ChartInk and PKScreener functionality.
    """

    def __init__(self, event_bus: EventBus, data_provider: Optional[Any] = None):
        self.event_bus = event_bus
        self.data_provider = data_provider
        self.logger = get_logger(__name__)

        # Scanner components
        self.rule_parser = ChartInkStyleParser()
        self.indicators = IndicatorCalculator()

        # Active scan jobs
        self.active_jobs: Dict[str, ScanJob] = {}
        self.job_history: List[ScanJob] = []

        # Scanner state
        self.is_running = False
        self.scan_queue = asyncio.Queue()
        self.worker_tasks: List[asyncio.Task] = []

        # Market data cache
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.cache_timeout = timedelta(minutes=5)
        self.last_cache_update: Dict[str, datetime] = {}

        # Performance metrics
        self.scan_stats = {
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'average_scan_time': 0.0,
            'symbols_scanned': 0,
            'signals_generated': 0
        }

        # Subscribe to market data events
        self.event_bus.subscribe(EventType.MARKET_DATA_UPDATE, self._on_market_data_update)
        self.event_bus.subscribe(EventType.SYMBOL_DATA_UPDATE, self._on_symbol_data_update)

        self.logger.info("Scanner Engine initialized")

    async def start(self):
        """Start the scanner engine."""
        if self.is_running:
            self.logger.warning("Scanner engine is already running")
            return

        self.is_running = True
        self.logger.info("Starting scanner engine")

        # Start worker tasks
        for i in range(3):  # 3 concurrent workers
            task = asyncio.create_task(self._scan_worker(f"worker_{i}"))
            self.worker_tasks.append(task)

        # Start cache cleanup task
        cleanup_task = asyncio.create_task(self._cache_cleanup_worker())
        self.worker_tasks.append(cleanup_task)

        self.logger.info("Scanner engine started successfully")

    async def stop(self):
        """Stop the scanner engine."""
        if not self.is_running:
            return

        self.logger.info("Stopping scanner engine")
        self.is_running = False

        # Cancel all active jobs
        for job in self.active_jobs.values():
            job.status = ScanStatus.CANCELLED

        # Stop workers
        for task in self.worker_tasks:
            task.cancel()

        # Wait for workers to complete
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()

        self.logger.info("Scanner engine stopped")

    async def create_scan_job(
        self,
        scanner_config: ScannerConfig,
        symbols: List[str],
        timeframe: str = "1d"
    ) -> str:
        """Create a new scan job."""
        job_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.active_jobs)}"

        job = ScanJob(
            job_id=job_id,
            scanner_config=scanner_config,
            symbols=symbols,
            timeframe=timeframe,
            start_time=datetime.now()
        )

        self.active_jobs[job_id] = job
        await self.scan_queue.put(job)

        self.logger.info(f"Created scan job {job_id} for {len(symbols)} symbols")

        # Publish scan job created event
        await self.event_bus.publish(Event(
            type=EventType.SCANNER_JOB_CREATED,
            data={
                "job_id": job_id,
                "scanner_name": scanner_config.name,
                "symbols_count": len(symbols),
                "timeframe": timeframe
            }
        ))

        return job_id

    async def _scan_worker(self, worker_id: str):
        """Scanner worker task."""
        self.logger.info(f"Scanner worker {worker_id} started")

        while self.is_running:
            try:
                job = await self.scan_queue.get()

                if job.status == ScanStatus.CANCELLED:
                    continue

                await self._execute_scan_job(job)

            except asyncio.CancelledError:
                self.logger.info(f"Scanner worker {worker_id} cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in scanner worker {worker_id}: {e}")
                await asyncio.sleep(1)

    async def _execute_scan_job(self, job: ScanJob):
        """Execute a scan job."""
        start_time = datetime.now()
        job.status = ScanStatus.SCANNING

        try:
            self.logger.info(f"Starting scan job {job.job_id}")

            # Parse rules from scanner config
            rules = []
            for rule_str in job.scanner_config.rules:
                rule = self.rule_parser.parse_rule(rule_str)
                if rule:
                    rules.append(rule)

            if not rules:
                raise ValueError("No valid rules found in scanner configuration")

            # Scan each symbol
            results = []
            for i, symbol in enumerate(job.symbols):
                if job.status == ScanStatus.CANCELLED:
                    break

                try:
                    # Get market data for symbol
                    data = await self._get_symbol_data(symbol, job.timeframe)

                    if data is None or len(data) < 50:  # Minimum data required
                        continue

                    # Apply scanner rules
                    symbol_results = await self._scan_symbol(symbol, data, rules, job.timeframe)
                    results.extend(symbol_results)

                    # Update progress
                    job.processed_symbols = i + 1
                    job.progress = (i + 1) / job.total_symbols * 100

                    # Publish progress update
                    await self.event_bus.publish(Event(
                        type=EventType.SCANNER_PROGRESS,
                        data={
                            "job_id": job.job_id,
                            "progress": job.progress,
                            "processed_symbols": job.processed_symbols,
                            "total_symbols": job.total_symbols,
                            "current_symbol": symbol
                        }
                    ))

                except Exception as e:
                    self.logger.error(f"Error scanning symbol {symbol}: {e}")
                    continue

            # Update job results
            job.results = results
            job.status = ScanStatus.COMPLETED
            job.end_time = datetime.now()

            # Update scan statistics
            scan_time = (job.end_time - job.start_time).total_seconds()
            self.scan_stats['total_scans'] += 1
            self.scan_stats['successful_scans'] += 1
            self.scan_stats['symbols_scanned'] += job.processed_symbols
            self.scan_stats['signals_generated'] += len(results)

            # Update average scan time
            if self.scan_stats['successful_scans'] == 1:
                self.scan_stats['average_scan_time'] = scan_time
            else:
                self.scan_stats['average_scan_time'] = (
                    (self.scan_stats['average_scan_time'] * (self.scan_stats['successful_scans'] - 1) + scan_time) /
                    self.scan_stats['successful_scans']
                )

            self.logger.info(f"Scan job {job.job_id} completed: {len(results)} signals found in {scan_time:.2f}s")

            # Publish scan completed event
            await self.event_bus.publish(Event(
                type=EventType.SCANNER_JOB_COMPLETED,
                data={
                    "job_id": job.job_id,
                    "scanner_name": job.scanner_config.name,
                    "results_count": len(results),
                    "scan_time": scan_time,
                    "symbols_processed": job.processed_symbols
                }
            ))

        except Exception as e:
            job.status = ScanStatus.ERROR
            job.error_message = str(e)
            job.end_time = datetime.now()

            self.scan_stats['failed_scans'] += 1

            self.logger.error(f"Scan job {job.job_id} failed: {e}")

            # Publish scan error event
            await self.event_bus.publish(Event(
                type=EventType.SCANNER_JOB_ERROR,
                data={
                    "job_id": job.job_id,
                    "scanner_name": job.scanner_config.name,
                    "error": str(e)
                }
            ))

        finally:
            # Move job to history
            if job.job_id in self.active_jobs:
                self.job_history.append(job)
                del self.active_jobs[job.job_id]

    async def _scan_symbol(self, symbol: str, data: pd.DataFrame, rules: List[ScannerRule], timeframe: str) -> List[ScannerResult]:
        """Scan a single symbol against scanner rules."""
        results = []

        try:
            # Calculate technical indicators
            indicators = await self._calculate_indicators(data)

            # Apply each rule
            for rule in rules:
                try:
                    result = self._evaluate_rule(symbol, data, indicators, rule, timeframe)
                    if result:
                        results.append(result)

                        # Publish individual signal event
                        await self.event_bus.publish(Event(
                            type=EventType.SCANNER_SIGNAL,
                            data={
                                "symbol": symbol,
                                "rule_name": rule.name,
                                "signal": result.signal,
                                "strength": result.strength,
                                "timeframe": timeframe,
                                "timestamp": result.timestamp.isoformat()
                            }
                        ))

                except Exception as e:
                    self.logger.error(f"Error evaluating rule {rule.name} for {symbol}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error scanning symbol {symbol}: {e}")

        return results

    async def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators for the data."""
        indicators = {}

        try:
            # Price-based indicators
            indicators['close'] = data['close'].values
            indicators['high'] = data['high'].values
            indicators['low'] = data['low'].values
            indicators['volume'] = data['volume'].values

            # Moving averages
            indicators['sma_20'] = self.indicators.sma(data['close'], 20)
            indicators['sma_50'] = self.indicators.sma(data['close'], 50)
            indicators['sma_200'] = self.indicators.sma(data['close'], 200)
            indicators['ema_12'] = self.indicators.ema(data['close'], 12)
            indicators['ema_26'] = self.indicators.ema(data['close'], 26)

            # RSI
            indicators['rsi_14'] = self.indicators.rsi(data['close'], 14)

            # MACD
            macd_line, signal_line, histogram = self.indicators.macd(data['close'])
            indicators['macd_line'] = macd_line
            indicators['macd_signal'] = signal_line
            indicators['macd_histogram'] = histogram

            # Bollinger Bands
            upper_band, middle_band, lower_band = self.indicators.bollinger_bands(data['close'])
            indicators['bb_upper'] = upper_band
            indicators['bb_middle'] = middle_band
            indicators['bb_lower'] = lower_band

            # Stochastic
            k, d = self.indicators.stochastic(data['high'], data['low'], data['close'])
            indicators['stoch_k'] = k
            indicators['stoch_d'] = d

            # Volume indicators
            indicators['volume_sma'] = self.indicators.sma(data['volume'], 20)

            # Price changes
            indicators['price_change'] = data['close'].pct_change()
            indicators['price_change_5d'] = data['close'].pct_change(5)
            indicators['price_change_10d'] = data['close'].pct_change(10)

            # Support/Resistance levels
            support, resistance = self.indicators.support_resistance(data['low'], data['high'])
            indicators['support_level'] = support
            indicators['resistance_level'] = resistance

        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")

        return indicators

    def _evaluate_rule(self, symbol: str, data: pd.DataFrame, indicators: Dict[str, Any], rule: ScannerRule, timeframe: str) -> Optional[ScannerResult]:
        """Evaluate a single rule against symbol data."""
        try:
            # Get latest values
            latest_data = {
                'close': data['close'].iloc[-1],
                'open': data['open'].iloc[-1],
                'high': data['high'].iloc[-1],
                'low': data['low'].iloc[-1],
                'volume': data['volume'].iloc[-1],
                'timestamp': data.index[-1]
            }

            # Get latest indicator values
            latest_indicators = {}
            for key, values in indicators.items():
                if isinstance(values, np.ndarray) and len(values) > 0:
                    latest_indicators[key] = values[-1]
                else:
                    latest_indicators[key] = values

            # Combine data for rule evaluation
            evaluation_context = {**latest_data, **latest_indicators}

            # Evaluate rule condition
            condition_met = self._evaluate_condition(rule.condition, evaluation_context)

            if condition_met:
                # Calculate signal strength
                strength = self._calculate_signal_strength(evaluation_context, rule)

                return ScannerResult(
                    symbol=symbol,
                    scanner_name=rule.name,
                    signal=rule.signal_type,
                    strength=strength,
                    timeframe=timeframe,
                    timestamp=latest_data['timestamp'],
                    metadata={
                        'rule_description': rule.description,
                        'close_price': latest_data['close'],
                        'volume': latest_data['volume'],
                        'rsi': latest_indicators.get('rsi_14'),
                        'sma_20': latest_indicators.get('sma_20'),
                        'sma_50': latest_indicators.get('sma_50')
                    }
                )

        except Exception as e:
            self.logger.error(f"Error evaluating rule {rule.name} for {symbol}: {e}")

        return None

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a rule condition with given context."""
        try:
            # Simple condition evaluation (can be enhanced)
            # This is a basic implementation - can be made more sophisticated

            # Replace variable names with actual values
            condition_expr = condition
            for key, value in context.items():
                if isinstance(value, (int, float)) and not np.isnan(value):
                    condition_expr = condition_expr.replace(key, str(value))

            # Evaluate the condition
            return eval(condition_expr, {"__builtins__": {}})

        except Exception as e:
            self.logger.error(f"Error evaluating condition '{condition}': {e}")
            return False

    def _calculate_signal_strength(self, context: Dict[str, Any], rule: ScannerRule) -> float:
        """Calculate signal strength based on multiple factors."""
        strength = 0.5  # Base strength

        try:
            # RSI-based strength
            rsi = context.get('rsi_14')
            if rsi is not None and not np.isnan(rsi):
                if rule.signal_type == 'BUY':
                    if rsi < 30:
                        strength += 0.2
                    elif rsi < 40:
                        strength += 0.1
                elif rule.signal_type == 'SELL':
                    if rsi > 70:
                        strength += 0.2
                    elif rsi > 60:
                        strength += 0.1

            # Volume-based strength
            volume = context.get('volume')
            volume_sma = context.get('volume_sma')
            if volume and volume_sma and volume_sma > 0:
                volume_ratio = volume / volume_sma
                if volume_ratio > 1.5:
                    strength += 0.15
                elif volume_ratio > 1.2:
                    strength += 0.1

            # Price momentum strength
            price_change = context.get('price_change_5d')
            if price_change is not None and not np.isnan(price_change):
                if rule.signal_type == 'BUY' and price_change > 0:
                    strength += 0.1
                elif rule.signal_type == 'SELL' and price_change < 0:
                    strength += 0.1

            # Clamp strength to valid range
            strength = max(0.0, min(1.0, strength))

        except Exception as e:
            self.logger.error(f"Error calculating signal strength: {e}")

        return strength

    async def _get_symbol_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get market data for a symbol."""
        try:
            # Check cache first
            cache_key = f"{symbol}_{timeframe}"
            current_time = datetime.now()

            if (cache_key in self.data_cache and
                cache_key in self.last_cache_update and
                current_time - self.last_cache_update[cache_key] < self.cache_timeout):
                return self.data_cache[cache_key]

            # Get data from data provider or event bus
            if self.data_provider:
                data = await self.data_provider.get_historical_data(symbol, timeframe)
            else:
                # Request data through event bus
                data = await self._request_symbol_data(symbol, timeframe)

            if data is not None and len(data) > 0:
                # Update cache
                self.data_cache[cache_key] = data
                self.last_cache_update[cache_key] = current_time

                return data

        except Exception as e:
            self.logger.error(f"Error getting data for {symbol}: {e}")

        return None

    async def _request_symbol_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Request symbol data through event bus."""
        try:
            # Create a future to wait for the response
            response_future = asyncio.Future()

            # Temporarily subscribe to data response
            def on_data_response(event: Event):
                if event.data.get('symbol') == symbol and event.data.get('timeframe') == timeframe:
                    response_future.set_result(event.data.get('data'))

            self.event_bus.subscribe(EventType.SYMBOL_DATA_RESPONSE, on_data_response)

            # Request data
            await self.event_bus.publish(Event(
                type=EventType.SYMBOL_DATA_REQUEST,
                data={'symbol': symbol, 'timeframe': timeframe}
            ))

            # Wait for response with timeout
            try:
                data = await asyncio.wait_for(response_future, timeout=10.0)
                return pd.DataFrame(data) if data else None
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout waiting for data for {symbol}")
                return None

        except Exception as e:
            self.logger.error(f"Error requesting data for {symbol}: {e}")
            return None

        finally:
            # Unsubscribe from response
            self.event_bus.unsubscribe(EventType.SYMBOL_DATA_RESPONSE, on_data_response)

    async def _on_market_data_update(self, event: Event):
        """Handle market data updates."""
        try:
            symbol = event.data.get('symbol')
            timeframe = event.data.get('timeframe')
            data = event.data.get('data')

            if symbol and timeframe and data:
                cache_key = f"{symbol}_{timeframe}"
                df = pd.DataFrame(data)
                self.data_cache[cache_key] = df
                self.last_cache_update[cache_key] = datetime.now()

        except Exception as e:
            self.logger.error(f"Error handling market data update: {e}")

    async def _on_symbol_data_update(self, event: Event):
        """Handle symbol data updates."""
        await self._on_market_data_update(event)

    async def _cache_cleanup_worker(self):
        """Clean up expired cache entries."""
        while self.is_running:
            try:
                current_time = datetime.now()
                expired_keys = []

                for cache_key, last_update in self.last_cache_update.items():
                    if current_time - last_update > self.cache_timeout:
                        expired_keys.append(cache_key)

                # Remove expired entries
                for key in expired_keys:
                    if key in self.data_cache:
                        del self.data_cache[key]
                    if key in self.last_cache_update:
                        del self.last_cache_update[key]

                if expired_keys:
                    self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

                await asyncio.sleep(60)  # Cleanup every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cache cleanup worker: {e}")
                await asyncio.sleep(60)

    def get_job_status(self, job_id: str) -> Optional[ScanJob]:
        """Get status of a scan job."""
        return self.active_jobs.get(job_id) or next(
            (job for job in self.job_history if job.job_id == job_id), None
        )

    def get_active_jobs(self) -> List[ScanJob]:
        """Get all active scan jobs."""
        return list(self.active_jobs.values())

    def get_scan_statistics(self) -> Dict[str, Any]:
        """Get scanner statistics."""
        return self.scan_stats.copy()

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        return {
            'cache_size': len(self.data_cache),
            'cache_entries': list(self.data_cache.keys()),
            'last_updates': {k: v.isoformat() for k, v in self.last_cache_update.items()}
        }

    async def clear_cache(self):
        """Clear the data cache."""
        self.data_cache.clear()
        self.last_cache_update.clear()
        self.logger.info("Data cache cleared")

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scan job."""
        job = self.active_jobs.get(job_id)
        if job and job.status == ScanStatus.SCANNING:
            job.status = ScanStatus.CANCELLED
            self.logger.info(f"Cancelled scan job {job_id}")
            return True
        return False
