"""Contract Rollover Management for Fortress Trading System."""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from structlog import get_logger

from fortress.core.event_bus import EventBus
from .symbol_manager import SymbolManager, RolloverConfig

logger = get_logger(__name__)


@dataclass
class RolloverRequest:
    """Request for contract rollover."""
    from_contract: str
    to_contract: str
    quantity: int
    rollover_type: str = "auto"
    requested_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    status: str = "pending"


class ContractRolloverManager:
    """Manages futures contract rollovers."""

    def __init__(self, symbol_manager: SymbolManager, event_bus: Optional[EventBus] = None):
        self.symbol_manager = symbol_manager
        self.event_bus = event_bus
        self.logger = logger.bind(component="ContractRolloverManager")

        self.rollover_requests: Dict[str, RolloverRequest] = {}
        self.rollover_configs: Dict[str, RolloverConfig] = {}
        self.monitoring_active = False

        self.logger.info("ContractRolloverManager initialized")

    async def start_monitoring(self) -> None:
        """Start monitoring for expiring contracts."""
        if self.monitoring_active:
            return
        self.monitoring_active = True
        self.logger.info("Started contract expiry monitoring")

    async def stop_monitoring(self) -> None:
        """Stop monitoring for expiring contracts."""
        self.monitoring_active = False
        self.logger.info("Stopped contract expiry monitoring")

    async def request_rollover(self, request: RolloverRequest) -> bool:
        """Request a contract rollover."""
        try:
            self.rollover_requests[request.from_contract] = request
            self.logger.info(
                "Rollover request created",
                from_contract=request.from_contract,
                to_contract=request.to_contract
            )
            return True
        except Exception as e:
            self.logger.error("Error creating rollover request", error=str(e))
            return False

    def get_rollover_requests(self, status: Optional[str] = None) -> List[RolloverRequest]:
        """Get rollover requests."""
        requests = list(self.rollover_requests.values())
        if status:
            requests = [r for r in requests if r.status == status]
        return requests

    def add_rollover_config(self, config: RolloverConfig) -> None:
        """Add rollover configuration."""
        self.rollover_configs[config.symbol] = config
        self.logger.info("Added rollover configuration", symbol=config.symbol)

    def get_rollover_config(self, symbol: str) -> Optional[RolloverConfig]:
        """Get rollover configuration for a symbol."""
        return self.rollover_configs.get(symbol)

    def get_statistics(self) -> Dict[str, Any]:
        """Get rollover manager statistics."""
        return {
            "monitoring_active": self.monitoring_active,
            "total_rollover_requests": len(self.rollover_requests),
            "rollover_configs": len(self.rollover_configs)
        }

    async def shutdown(self) -> None:
        """Shutdown the rollover manager."""
        await self.stop_monitoring()
        self.logger.info("ContractRolloverManager shutdown complete")
