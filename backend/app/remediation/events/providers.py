from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Awaitable
from app.remediation.events.messages import RemediationMessage, RemediationEventType

class IEventBusProvider(ABC):
    """
    Abstraction for the underlying event transport mechanism.
    Allows switching between In-Memory, Redis, RabbitMQ, Kafka, etc.
    """
    @abstractmethod
    async def publish(self, message: RemediationMessage) -> None:
        """Low-level publish operation."""
        pass

    @abstractmethod
    async def subscribe(self, event_type: RemediationEventType, handler: Callable[[RemediationMessage], Awaitable[None]]) -> None:
        """Low-level subscription operation."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the provider."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the provider connection."""
        pass
