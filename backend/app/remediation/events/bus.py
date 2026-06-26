from __future__ import annotations
from typing import Callable, Dict, List, Any, Awaitable
from app.remediation.events.messages import RemediationMessage, RemediationEventType
from app.utils.logger import logger

class IEventBus:
    """
    Interface for the internal event-driven architecture.
    Decouples event producers from consumers.
    """
    async def publish(self, message: RemediationMessage) -> None:
        """Publishes an event to the bus."""
        pass

    async def subscribe(self, event_type: RemediationEventType, handler: Callable[[RemediationMessage], Awaitable[None]]) -> None:
        """Subscribes a handler to a specific event type."""
        pass

class InternalEventBus(IEventBus):
    """
    In-memory implementation of the Event Bus.
    Future versions can be replaced with a distributed bus (e.g. Redis PubSub, Kafka).
    """
    def __init__(self):
        self._handlers: Dict[RemediationEventType, List[Callable[[RemediationMessage], Awaitable[None]]]] = {}

    async def publish(self, message: RemediationMessage) -> None:
        logger.info(f"[EventBus] Publishing event {message.event_type} (ID: {message.event_id})")

        handlers = self._handlers.get(message.event_type, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"[EventBus] Handler failed for event {message.event_type}: {e}")

    async def subscribe(self, event_type: RemediationEventType, handler: Callable[[RemediationMessage], Awaitable[None]]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"[EventBus] Subscribed handler to {event_type}")

# Global instance for the application
event_bus = InternalEventBus()
