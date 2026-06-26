from __future__ import annotations
from typing import Callable, Dict, List, Any, Awaitable, Optional
from app.remediation.events.messages import RemediationMessage, RemediationEventType
from app.remediation.events.providers import IEventBusProvider
from app.utils.logger import logger
from app.config import settings

class InternalEventBusProvider(IEventBusProvider):
    """
    In-memory implementation of the Event Bus Provider.
    Suitable for development and single-process deployments.
    """
    def __init__(self):
        self._handlers: Dict[RemediationEventType, List[Callable[[RemediationMessage], Awaitable[None]]]] = {}

    async def connect(self) -> None:
        logger.debug("[InternalEventBusProvider] In-memory bus connected")

    async def disconnect(self) -> None:
        logger.debug("[InternalEventBusProvider] In-memory bus disconnected")

    async def publish(self, message: RemediationMessage) -> None:
        handlers = self._handlers.get(message.event_type, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"[InternalEventBusProvider] Handler failed for event {message.event_type}: {e}")

    async def subscribe(self, event_type: RemediationEventType, handler: Callable[[RemediationMessage], Awaitable[None]]) -> None:
        if event_type not in self._handlers:
            self._handlers[ la event_type] = []
        self._handlers[event_type].append(handler)

class EventBus:
    """
    The main Event Bus orchestrator.
    Delegates actual transport to an IEventBusProvider.
    """
    def __init__(self, provider: IEventBusProvider):
        self.provider = provider

    async def publish(self, message: RemediationMessage) -> None:
        logger.info(f"[EventBus] Publishing event {message.event_type} (ID: {message.event_id})")
        await self.provider.publish(message)

    async def subscribe(self, event_type: RemediationEventType, handler: Callable[[RemediationMessage], Awaitable[None]]) -> None:
        await self.provider.subscribe(event_type, handler)

def get_event_bus() -> EventBus:
    """
    Factory function to resolve the event bus provider based on configuration.
    Ensures backward compatibility by defaulting to InternalEventBusProvider.
    """
    provider_type = getattr(settings, "remediation_event_bus_provider", "internal")

    if provider_type == "internal":
        provider = InternalEventBusProvider()
    else:
        # In a real implementation, this would map to RedisEventBusProvider, KafkaProvider, etc.
        logger.warning(f"[EventBus] Requested provider {provider_type} not implemented. Falling back to internal.")
        provider = InternalEventBusProvider()

    return EventBus(provider)

# Global instance for the application
event_bus = get_event_bus()
