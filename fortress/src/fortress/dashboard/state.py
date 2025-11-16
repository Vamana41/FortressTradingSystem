from typing import Optional

from fortress.brain.brain import FortressBrain
from fortress.core.event_bus import EventBus, event_bus_manager

_brain: Optional[FortressBrain] = None
_event_bus: Optional[EventBus] = None

def set_brain(brain: FortressBrain) -> None:
    global _brain
    _brain = brain

def get_brain() -> Optional[FortressBrain]:
    return _brain

def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = event_bus_manager.get_event_bus(name="fortress", redis_url="redis://localhost:6379", key_prefix="fortress")
    return _event_bus