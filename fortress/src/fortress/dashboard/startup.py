"""Dashboard startup utilities for connecting to Fortress Brain."""

from typing import Optional
import asyncio
import structlog

from fortress.brain.brain import FortressBrain
from fortress.core.event_bus import EventBus
from .state import set_brain, get_event_bus

logger = structlog.get_logger(__name__)

class DashboardConnector:
    """Manages connection between dashboard and Fortress Brain."""
    
    def __init__(self):
        self.brain: Optional[FortressBrain] = None
        self.event_bus: Optional[EventBus] = None
        self._connected = False
    
    async def connect_to_brain(self, brain: FortressBrain) -> bool:
        """Connect dashboard to running Fortress Brain."""
        try:
            self.brain = brain
            self.event_bus = get_event_bus()
            
            # Set brain in dashboard state
            set_brain(brain)
            
            # Connect to event bus
            await self.event_bus.connect()
            
            self._connected = True
            
            logger.info(
                "Dashboard successfully connected to Fortress Brain",
                brain_id=brain.brain_id,
                event_bus_connected=self.event_bus.is_connected
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to connect dashboard to brain", error=str(e))
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect dashboard from brain."""
        if self.event_bus and self.event_bus.is_connected:
            await self.event_bus.disconnect()
        
        self.brain = None
        self.event_bus = None
        self._connected = False
        
        logger.info("Dashboard disconnected from Fortress Brain")
    
    def is_connected(self) -> bool:
        """Check if dashboard is connected to brain."""
        return self._connected and self.brain is not None
    
    def get_connection_status(self) -> dict:
        """Get detailed connection status."""
        return {
            "connected": self.is_connected(),
            "brain_id": self.brain.brain_id if self.brain else None,
            "event_bus_connected": self.event_bus.is_connected if self.event_bus else False,
            "brain_state": self.brain.get_state().model_dump() if self.brain else None,
        }

# Global connector instance
_connector: Optional[DashboardConnector] = None

async def initialize_dashboard_connection(brain: FortressBrain) -> bool:
    """Initialize dashboard connection to Fortress Brain."""
    global _connector
    
    if _connector is None:
        _connector = DashboardConnector()
    
    return await _connector.connect_to_brain(brain)

async def get_dashboard_connection() -> Optional[DashboardConnector]:
    """Get the dashboard connector instance."""
    return _connector

def is_dashboard_connected() -> bool:
    """Check if dashboard is connected to brain."""
    return _connector is not None and _connector.is_connected()