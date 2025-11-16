from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import asdict
import asyncio

from fastapi import APIRouter, HTTPException, Query

from ..state import get_brain
from ..performance_monitor import performance_monitor
from fortress.symbol_management.symbol_manager import SymbolManager
from fortress.symbol_management.contract_rollover import ContractRolloverManager
from fortress.scanner import ScannerEngine, ScannerConfig, PREBUILT_SCANNERS, IndicatorCalculator

api_router = APIRouter()

# Initialize symbol management components
symbol_manager = SymbolManager()
rollover_manager: Optional[ContractRolloverManager] = None

# Initialize scanner components
scanner_engine: Optional[ScannerEngine] = None

def get_scanner_engine() -> ScannerEngine:
    """Get or create scanner engine instance."""
    global scanner_engine
    if scanner_engine is None:
        from ..state import get_event_bus
        scanner_engine = ScannerEngine(get_event_bus())
    return scanner_engine

def get_rollover_manager() -> ContractRolloverManager:
    global rollover_manager
    if rollover_manager is None:
        from ..state import get_event_bus
        rollover_manager = ContractRolloverManager(symbol_manager, get_event_bus())
    return rollover_manager

@api_router.get("/status")
async def status() -> Dict[str, Any]:
    brain = get_brain()
    if not brain:
        return {"healthy": True, "message": "brain not attached", "strategies": 0, "positions": 0}
    state = brain.get_state()
    return {
        "healthy": state.is_healthy,
        "startup_time": state.startup_time,
        "strategies": len(state.strategies),
        "positions": len(state.positions),
        "processed_signals": state.processed_signals,
    }

@api_router.get("/positions")
async def positions() -> Dict[str, Any]:
    brain = get_brain()
    if not brain:
        return {"positions": []}
    items = []
    for symbol, pos in brain.get_state().positions.items():
        items.append({
            "symbol": symbol,
            "net_quantity": pos.net_quantity,
            "average_price": pos.average_price,
            "realized_pnl": pos.realized_pnl,
            "unrealized_pnl": pos.unrealized_pnl,
            "last_update_time": pos.last_update_time,
        })
    return {"positions": items}

@api_router.get("/risk")
async def risk() -> Dict[str, Any]:
    brain = get_brain()
    if not brain:
        return {"portfolio_state": {}, "risk_state": {}}
    return brain.get_risk_summary()

@api_router.get("/signals")
async def signals(symbol: str | None = None, strategy: str | None = None, limit: int = 50) -> Dict[str, Any]:
    brain = get_brain()
    if not brain:
        return {"signals": []}
    return {"signals": brain.get_multi_timeframe_signals(symbol, strategy, limit)}

@api_router.get("/timeframes/{symbol}/{strategy}")
async def timeframe_summary(symbol: str, strategy: str) -> Dict[str, Any]:
    brain = get_brain()
    if not brain:
        return {"error": "brain not attached"}
    return brain.get_timeframe_summary(symbol, strategy)

@api_router.get("/pnl")
async def pnl() -> Dict[str, Any]:
    brain = get_brain()
    if not brain:
        return {"realized": 0.0, "unrealized": 0.0}
    realized = sum(p.realized_pnl for p in brain.get_state().positions.values())
    unrealized = sum(p.unrealized_pnl for p in brain.get_state().positions.values())
    return {"realized": realized, "unrealized": unrealized}

# Symbol Management Endpoints
@api_router.get("/symbols")
async def get_symbols() -> Dict[str, Any]:
    """Get all registered symbols"""
    symbols = symbol_manager.get_all_symbols()
    return {"symbols": [symbol.__dict__ for symbol in symbols]}

@api_router.get("/symbols/{symbol}")
async def get_symbol(symbol: str) -> Dict[str, Any]:
    """Get specific symbol information"""
    symbol_info = symbol_manager.get_symbol(symbol)
    if not symbol_info:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return {"symbol": symbol_info.__dict__}

@api_router.get("/futures/contracts")
async def get_futures_contracts(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Get futures contracts, optionally filtered by symbol"""
    contracts = symbol_manager.get_all_futures_contracts()
    if symbol:
        contracts = [c for c in contracts if c.base_symbol == symbol]
    return {"contracts": [contract.__dict__ for contract in contracts]}

@api_router.get("/futures/active")
async def get_active_contracts() -> Dict[str, Any]:
    """Get currently active futures contracts"""
    active_contracts = symbol_manager.get_active_contracts()
    return {"active_contracts": active_contracts}

@api_router.get("/futures/expiring")
async def get_expiring_contracts(days: int = Query(default=7, ge=1, le=30)) -> Dict[str, Any]:
    """Get contracts expiring within specified days"""
    manager = get_rollover_manager()
    expiring = manager.get_expiring_contracts(days)
    return {"expiring_contracts": [contract.__dict__ for contract in expiring]}

@api_router.post("/futures/rollover/{symbol}")
async def request_rollover(symbol: str) -> Dict[str, Any]:
    """Request manual rollover for a symbol"""
    manager = get_rollover_manager()
    try:
        request_id = manager.request_rollover(symbol)
        return {"request_id": request_id, "status": "requested"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/futures/rollover/status/{request_id}")
async def get_rollover_status(request_id: str) -> Dict[str, Any]:
    """Get status of rollover request"""
    manager = get_rollover_manager()
    request = manager.get_rollover_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Rollover request not found")
    return {"request": request.__dict__}

# Performance and Analytics Endpoints
@api_router.get("/performance/summary")
async def performance_summary(days: int = Query(default=30, ge=1, le=365)) -> Dict[str, Any]:
    """Get performance summary for specified days"""
    brain = get_brain()
    if not brain:
        return {"error": "brain not attached"}
    
    # Calculate performance metrics
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get historical data from brain state
    state = brain.get_state()
    total_pnl = sum(p.realized_pnl + p.unrealized_pnl for p in state.positions.values())
    
    return {
        "period_days": days,
        "total_pnl": total_pnl,
        "total_positions": len(state.positions),
        "win_rate": 0.0,  # TODO: Implement win rate calculation
        "sharpe_ratio": 0.0,  # TODO: Implement Sharpe ratio calculation
        "max_drawdown": 0.0,  # TODO: Implement max drawdown calculation
    }

@api_router.get("/analytics/signals")
async def signal_analytics(
    hours: int = Query(default=24, ge=1, le=168),
    symbol: Optional[str] = None,
    strategy: Optional[str] = None
) -> Dict[str, Any]:
    """Get signal analytics for specified time period"""
    brain = get_brain()
    if not brain:
        return {"signals": [], "summary": {}}
    
    signals = brain.get_multi_timeframe_signals(symbol, strategy, limit=1000)
    
    # Filter by time period
    cutoff_time = datetime.now() - timedelta(hours=hours)
    recent_signals = [s for s in signals if datetime.fromisoformat(s.get("timestamp", "")) >= cutoff_time]
    
    # Calculate analytics
    signal_types = {}
    strategy_counts = {}
    symbol_counts = {}
    
    for signal in recent_signals:
        sig_type = signal.get("final_signal", {}).get("signal_type", "unknown")
        signal_types[sig_type] = signal_types.get(sig_type, 0) + 1
        
        strat = signal.get("strategy", "unknown")
        strategy_counts[strat] = strategy_counts.get(strat, 0) + 1
        
        sym = signal.get("symbol", "unknown")
        symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
    
    return {
        "period_hours": hours,
        "total_signals": len(recent_signals),
        "signal_types": signal_types,
        "strategy_counts": strategy_counts,
        "symbol_counts": symbol_counts,
        "signals": recent_signals[:100]  # Return first 100 for display
    }

# Performance Monitoring Endpoints
@api_router.get("/performance/current")
async def get_current_performance() -> Dict[str, Any]:
    """Get current system performance metrics"""
    return performance_monitor.get_current_metrics()

@api_router.get("/performance/history")
async def get_performance_history(
    hours: int = Query(default=1, ge=1, le=24)
) -> Dict[str, Any]:
    """Get performance history for specified hours"""
    history = performance_monitor.get_performance_history(hours)
    return {"history": history, "hours": hours}

@api_router.post("/performance/benchmark/{name}")
async def run_benchmark(
    name: str,
    iterations: int = Query(default=100, ge=10, le=10000)
) -> Dict[str, Any]:
    """Run a performance benchmark"""
    
    async def dummy_benchmark():
        """Dummy benchmark function for testing"""
        await asyncio.sleep(0.001)  # 1ms delay
        # Simulate some CPU work
        _ = sum(i * i for i in range(100))
    
    try:
        result = await performance_monitor.run_benchmark(name, dummy_benchmark, iterations)
        return asdict(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {str(e)}")

@api_router.get("/performance/benchmarks")
async def get_benchmark_results(
    limit: int = Query(default=10, ge=1, le=100)
) -> Dict[str, Any]:
    """Get recent benchmark results"""
    results = performance_monitor.get_benchmark_results(limit)
    return {"benchmarks": results, "count": len(results)}

@api_router.get("/performance/summary")
async def get_performance_summary() -> Dict[str, Any]:
    """Get comprehensive performance summary"""
    current = performance_monitor.get_current_metrics()
    history = performance_monitor.get_performance_history(24)  # Last 24 hours
    benchmarks = performance_monitor.get_benchmark_results(5)  # Last 5 benchmarks
    
    # Calculate trends
    system_trend = "stable"
    if history:
        recent_cpu = [h["cpu_percent"] for h in history[-10:]]
        if len(recent_cpu) >= 2:
            avg_recent = sum(recent_cpu) / len(recent_cpu)
            avg_older = sum([h["cpu_percent"] for h in history[-20:-10]]) / max(len(history[-20:-10]), 1)
            
            if avg_recent > avg_older * 1.2:
                system_trend = "increasing"
            elif avg_recent < avg_older * 0.8:
                system_trend = "decreasing"
    
    return {
        "current": current,
        "history_count": len(history),
        "benchmark_count": len(benchmarks),
        "system_trend": system_trend,
        "uptime_hours": current.get("uptime_seconds", 0) / 3600 if current else 0,
        "recommendations": get_performance_recommendations(current)
    }

@api_router.post("/performance/metrics/save")
async def save_performance_metrics() -> Dict[str, Any]:
    """Save current performance metrics to file"""
    try:
        performance_monitor.save_metrics()
        return {"status": "saved", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save metrics: {str(e)}")

def get_performance_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """Get performance recommendations based on current metrics"""
    recommendations = []
    
    if not metrics:
        return recommendations
    
    system_metrics = metrics.get("system", {})
    trading_metrics = metrics.get("trading", {})
    
    # System recommendations
    if system_metrics.get("cpu_percent", 0) > 80:
        recommendations.append("High CPU usage detected. Consider optimizing signal processing or reducing concurrent strategies.")
    
    if system_metrics.get("memory_percent", 0) > 85:
        recommendations.append("High memory usage detected. Consider reducing data cache size or optimizing memory usage.")
    
    if system_metrics.get("disk_percent", 0) > 90:
        recommendations.append("High disk usage detected. Consider cleaning up old log files and data.")
    
    # Trading recommendations
    if trading_metrics.get("error_rate", 0) > 5:
        recommendations.append("High error rate detected. Check system logs and API connections.")
    
    if trading_metrics.get("latency_ms", 0) > 100:
        recommendations.append("High latency detected. Consider optimizing network connections or reducing processing complexity.")
    
    if trading_metrics.get("signals_per_second", 0) > 10:
        recommendations.append("High signal rate detected. Consider implementing rate limiting or signal filtering.")
    
    return recommendations

# Scanner API Endpoints
@api_router.get("/scanner/prebuilt")
async def get_prebuilt_scanners() -> Dict[str, Any]:
    """Get all prebuilt scanner configurations"""
    try:
        scanners = list(PREBUILT_SCANNERS.values())
        return {"scanners": scanners, "count": len(scanners)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prebuilt scanners: {str(e)}")

@api_router.get("/scanner/prebuilt/{scanner_name}")
async def get_prebuilt_scanner(scanner_name: str) -> Dict[str, Any]:
    """Get a specific prebuilt scanner configuration"""
    try:
        scanner = PREBUILT_SCANNERS.get(scanner_name)
        if not scanner:
            raise HTTPException(status_code=404, detail=f"Scanner '{scanner_name}' not found")
        return scanner
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scanner: {str(e)}")

@api_router.post("/scanner/scan")
async def create_scan_job(
    scanner_name: str,
    symbols: List[str],
    timeframe: str = Query(default="1d", regex="^(1m|5m|15m|1h|4h|1d|1w)$"),
    custom_rules: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create a new scan job"""
    try:
        scanner_engine = get_scanner_engine()
        
        # Get scanner configuration
        if custom_rules:
            scanner_config = ScannerConfig(
                name=f"custom_{scanner_name}",
                description=f"Custom scanner based on {scanner_name}",
                rules=custom_rules,
                timeframe=timeframe
            )
        else:
            scanner_config = PREBUILT_SCANNERS.get(scanner_name)
            if not scanner_config:
                raise HTTPException(status_code=404, detail=f"Scanner '{scanner_name}' not found")
        
        # Ensure scanner engine is running
        if not scanner_engine.is_running:
            await scanner_engine.start()
        
        # Create scan job
        job_id = await scanner_engine.create_scan_job(scanner_config, symbols, timeframe)
        
        return {
            "job_id": job_id,
            "scanner_name": scanner_config.name,
            "symbols_count": len(symbols),
            "timeframe": timeframe,
            "status": "created"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create scan job: {str(e)}")

@api_router.get("/scanner/jobs")
async def get_active_scan_jobs() -> Dict[str, Any]:
    """Get all active scan jobs"""
    try:
        scanner_engine = get_scanner_engine()
        jobs = scanner_engine.get_active_jobs()
        
        job_list = []
        for job in jobs:
            job_list.append({
                "job_id": job.job_id,
                "scanner_name": job.scanner_config.name,
                "status": job.status.value,
                "progress": job.progress,
                "symbols_total": job.total_symbols,
                "symbols_processed": job.processed_symbols,
                "start_time": job.start_time.isoformat(),
                "timeframe": job.timeframe
            })
        
        return {"jobs": job_list, "count": len(job_list)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scan jobs: {str(e)}")

@api_router.get("/scanner/jobs/{job_id}")
async def get_scan_job_status(job_id: str) -> Dict[str, Any]:
    """Get status of a specific scan job"""
    try:
        scanner_engine = get_scanner_engine()
        job = scanner_engine.get_job_status(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        job_data = {
            "job_id": job.job_id,
            "scanner_name": job.scanner_config.name,
            "status": job.status.value,
            "progress": job.progress,
            "symbols_total": job.total_symbols,
            "symbols_processed": job.processed_symbols,
            "start_time": job.start_time.isoformat(),
            "timeframe": job.timeframe
        }
        
        if job.end_time:
            job_data["end_time"] = job.end_time.isoformat()
        
        if job.error_message:
            job_data["error_message"] = job.error_message
        
        # Include results if job is completed
        if job.status.value == "completed" and job.results:
            job_data["results_count"] = len(job.results)
            job_data["results"] = [
                {
                    "symbol": result.symbol,
                    "signal": result.signal,
                    "strength": result.strength,
                    "timestamp": result.timestamp.isoformat(),
                    "metadata": result.metadata
                }
                for result in job.results[:50]  # Limit to first 50 results
            ]
        
        return job_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

@api_router.delete("/scanner/jobs/{job_id}")
async def cancel_scan_job(job_id: str) -> Dict[str, Any]:
    """Cancel a scan job"""
    try:
        scanner_engine = get_scanner_engine()
        success = await scanner_engine.cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found or cannot be cancelled")
        
        return {"job_id": job_id, "status": "cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

@api_router.get("/scanner/statistics")
async def get_scanner_statistics() -> Dict[str, Any]:
    """Get scanner statistics"""
    try:
        scanner_engine = get_scanner_engine()
        stats = scanner_engine.get_scan_statistics()
        cache_info = scanner_engine.get_cache_info()
        
        return {
            "statistics": stats,
            "cache_info": cache_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scanner statistics: {str(e)}")

@api_router.post("/scanner/cache/clear")
async def clear_scanner_cache() -> Dict[str, Any]:
    """Clear scanner data cache"""
    try:
        scanner_engine = get_scanner_engine()
        await scanner_engine.clear_cache()
        
        return {"status": "cleared", "timestamp": datetime.now().isoformat()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@api_router.post("/scanner/start")
async def start_scanner_engine() -> Dict[str, Any]:
    """Start the scanner engine"""
    try:
        scanner_engine = get_scanner_engine()
        
        if scanner_engine.is_running:
            return {"status": "already_running", "message": "Scanner engine is already running"}
        
        await scanner_engine.start()
        return {"status": "started", "message": "Scanner engine started successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scanner engine: {str(e)}")

@api_router.post("/scanner/stop")
async def stop_scanner_engine() -> Dict[str, Any]:
    """Stop the scanner engine"""
    try:
        scanner_engine = get_scanner_engine()
        
        if not scanner_engine.is_running:
            return {"status": "not_running", "message": "Scanner engine is not running"}
        
        await scanner_engine.stop()
        return {"status": "stopped", "message": "Scanner engine stopped successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop scanner engine: {str(e)}")
    
    system_metrics = metrics.get("system", {})
    trading_metrics = metrics.get("trading", {})
    
    # System recommendations
    if system_metrics.get("cpu_percent", 0) > 80:
        recommendations.append("High CPU usage detected. Consider optimizing signal processing or reducing concurrent strategies.")
    
    if system_metrics.get("memory_percent", 0) > 85:
        recommendations.append("High memory usage detected. Consider reducing data cache size or optimizing memory usage.")
    
    if system_metrics.get("disk_percent", 0) > 90:
        recommendations.append("High disk usage detected. Consider cleaning up old log files and data.")
    
    # Trading recommendations
    if trading_metrics.get("error_rate", 0) > 5:
        recommendations.append("High error rate detected. Check system logs and API connections.")
    
    if trading_metrics.get("latency_ms", 0) > 100:
        recommendations.append("High latency detected. Consider optimizing network connections or reducing processing complexity.")
    
    if trading_metrics.get("signals_per_second", 0) > 10:
        recommendations.append("High signal rate detected. Consider implementing rate limiting or signal filtering.")
    
    return recommendations