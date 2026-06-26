from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, Awaitable
from pydantic import BaseModel

class QueueMessage(BaseModel):
    """Generic wrapper for messages put into a queue."""
    message_id: str
    payload: Any
    priority: int = 0
    delay_seconds: int = 0
    retry_count: int = 0
    max_retries: int = 3

class IQueueProvider(ABC):
    """
    Abstract interface for queueing providers.
    Ensures the engine is not hardcoded to any specific backend (Redis, RabbitMQ, SQS).
    """
    @abstractmethod
    async def publish(self, queue_name: str, message: QueueMessage) -> bool:
        """Pushes a message into the specified queue."""
        pass

    @abstractmethod
    async def subscribe(self, queue_name: str, handler: Callable[[QueueMessage], Awaitable[None]]) -> None:
        """Subscribes a worker to consume messages from the queue."""
        pass

    @abstractmethod
    async def acknowledge(self, message_id: str) -> None:
        """Marks a message as successfully processed."""
        pass

    @abstractmethod
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """Rejects a message, optionally putting it back in the queue."""
        pass

    @abstractmethod
    async def move_to_dlq(self, message: QueueMessage, reason: str) -> None:
        """Moves a message to the Dead Letter Queue after exhaustive failures."""
        pass
