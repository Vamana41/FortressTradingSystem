"""Redis-based event bus for Fortress Trading System."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Callable, Dict, List, Optional, Set

import redis.asyncio as redis
import structlog

from .events import Event, EventPriority, EventType


logger = structlog.get_logger(__name__)


class EventBus:
    """Redis-based event bus for event-driven architecture."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        db: int = 0,
        key_prefix: str = "fortress",
    ):
        """Initialize event bus."""
        self.redis_url = redis_url
        self.db = db
        self.key_prefix = key_prefix
        self._redis: Optional[redis.Redis] = None
        self._subscribers: Dict[EventType, Set[Callable]] = {}
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []
        
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                db=self.db,
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("Connected to Redis event bus", url=self.redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        
        # Cancel consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
        
        if self._redis:
            await self._redis.close()
            logger.info("Disconnected from Redis event bus")
    
    def _get_queue_key(self, event_type: EventType, priority: EventPriority) -> str:
        """Get Redis queue key for event type and priority."""
        return f"{self.key_prefix}:events:{event_type}:{priority}"
    
    def _get_processing_key(self, event_id: str) -> str:
        """Get Redis key for processing events."""
        return f"{self.key_prefix}:processing:{event_id}"
    
    async def publish(self, event: Event) -> bool:
        """Publish event to Redis queue."""
        if not self._redis:
            logger.error("Redis not connected")
            return False
        
        try:
            queue_key = self._get_queue_key(event.event_type, event.priority)
            event_json = event.to_json()
            
            # Use LPUSH for LIFO queue (newest events processed first for high priority)
            result = await self._redis.lpush(queue_key, event_json)
            
            logger.info(
                "Event published",
                event_id=event.event_id,
                event_type=event.event_type,
                priority=event.priority,
                queue_size=result,
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                event_id=event.event_id,
                error=str(e),
            )
            return False
    
    async def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any],
    ) -> None:
        """Subscribe to event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        
        self._subscribers[event_type].add(handler)
        logger.info("Handler subscribed", event_type=event_type)
    
    async def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any],
    ) -> None:
        """Unsubscribe from event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(handler)
            logger.info("Handler unsubscribed", event_type=event_type)
    
    async def consume_events(self, event_type: EventType, priority: EventPriority) -> None:
        """Consume events from Redis queue."""
        if not self._redis:
            logger.error("Redis not connected")
            return
        
        queue_key = self._get_queue_key(event_type, priority)
        
        while self._running:
            try:
                # Use BRPOP for blocking pop from right (oldest first)
                result = await self._redis.brpop(queue_key, timeout=1)
                
                if result is None:
                    continue
                
                _, event_json = result
                event = Event.from_json(event_json)
                
                # Mark as processing
                processing_key = self._get_processing_key(event.event_id)
                await self._redis.setex(processing_key, 300, "processing")  # 5 min TTL
                
                # Process event
                await self._process_event(event)
                
                # Remove from processing
                await self._redis.delete(processing_key)
                
            except asyncio.CancelledError:
                logger.info("Event consumer cancelled", event_type=event_type, priority=priority)
                break
            except Exception as e:
                logger.error(
                    "Error consuming event",
                    event_type=event_type,
                    priority=priority,
                    error=str(e),
                )
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _process_event(self, event: Event) -> None:
        """Process a single event."""
        logger.info(
            "Processing event",
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
        )
        
        # Get handlers for this event type
        handlers = self._subscribers.get(event.event_type, set())
        
        # Execute handlers
        for handler in handlers:
            try:
                result = await handler(event)
                logger.info(
                    "Event handler completed",
                    event_id=event.event_id,
                    handler=handler.__name__,
                    result=result,
                )
            except Exception as e:
                logger.error(
                    "Event handler failed",
                    event_id=event.event_id,
                    handler=handler.__name__,
                    error=str(e),
                )
                # Publish error event
                error_event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.ERROR_OCCURRED,
                    source="event_bus",
                    data={
                        "original_event_id": event.event_id,
                        "handler": handler.__name__,
                        "error": str(e),
                    },
                )
                await self.publish(error_event)
    
    async def start_consumers(self) -> None:
        """Start event consumers for all subscribed event types."""
        if not self._subscribers:
            logger.warning("No subscribers registered")
            return
        
        self._running = True
        
        # Start consumers for each event type with different priorities
        priorities = [EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW]
        
        for event_type in self._subscribers.keys():
            for priority in priorities:
                task = asyncio.create_task(
                    self.consume_events(event_type, priority),
                    name=f"consumer-{event_type}-{priority}",
                )
                self._consumer_tasks.append(task)
                logger.info(
                    "Started event consumer",
                    event_type=event_type,
                    priority=priority,
                )
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self._redis:
            return {}
        
        stats = {}
        
        try:
            # Get queue lengths for all event types and priorities
            for event_type in EventType:
                stats[event_type] = {}
                for priority in EventPriority:
                    queue_key = self._get_queue_key(event_type, priority)
                    length = await self._redis.llen(queue_key)
                    stats[event_type][priority] = length
            
            # Get processing event count
            processing_pattern = f"{self.key_prefix}:processing:*"
            processing_keys = await self._redis.keys(processing_pattern)
            stats["processing_count"] = len(processing_keys)
            
        except Exception as e:
            logger.error("Failed to get queue stats", error=str(e))
        
        return stats
    
    async def purge_queue(self, event_type: EventType, priority: EventPriority) -> int:
        """Purge events from queue."""
        if not self._redis:
            return 0
        
        try:
            queue_key = self._get_queue_key(event_type, priority)
            deleted = await self._redis.delete(queue_key)
            logger.info(
                "Queue purged",
                event_type=event_type,
                priority=priority,
                deleted_count=deleted,
            )
            return deleted
            
        except Exception as e:
            logger.error(
                "Failed to purge queue",
                event_type=event_type,
                priority=priority,
                error=str(e),
            )
            return 0


class EventBusManager:
    """Manager for multiple event bus instances."""
    
    def __init__(self):
        """Initialize event bus manager."""
        self._event_buses: Dict[str, EventBus] = {}
    
    def get_event_bus(self, name: str = "default", **kwargs) -> EventBus:
        """Get or create event bus instance."""
        if name not in self._event_buses:
            self._event_buses[name] = EventBus(**kwargs)
        
        return self._event_buses[name]
    
    async def connect_all(self) -> None:
        """Connect all event buses."""
        for event_bus in self._event_buses.values():
            await event_bus.connect()
    
    async def disconnect_all(self) -> None:
        """Disconnect all event buses."""
        for event_bus in self._event_buses.values():
            await event_bus.disconnect()


# Global event bus manager
event_bus_manager = EventBusManager()


# Convenience functions
async def publish_event(event: Event, bus_name: str = "default") -> bool:
    """Publish event to named event bus."""
    event_bus = event_bus_manager.get_event_bus(bus_name)
    return await event_bus.publish(event)


async def subscribe_to_event(
    event_type: EventType,
    handler: Callable[[Event], Any],
    bus_name: str = "default",
) -> None:
    """Subscribe to event type on named event bus."""
    event_bus = event_bus_manager.get_event_bus(bus_name)
    await event_bus.subscribe(event_type, handler)


async def start_event_consumers(bus_name: str = "default") -> None:
    """Start event consumers for named event bus."""
    event_bus = event_bus_manager.get_event_bus(bus_name)
    await event_bus.start_consumers()