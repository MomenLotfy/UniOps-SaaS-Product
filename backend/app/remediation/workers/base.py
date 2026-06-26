from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.utils.logger import logger
from app.remediation.queue.interfaces import IQueueProvider, QueueMessage

class BaseRemediationWorker(ABC):
    """
    Abstract base class for all remediation runtime workers.
    Handles common worker lifecycle and queue integration.
    """
    def __init__(self, queue_provider: IQueueProvider, worker_name: str):
        self.queue_provider = queue_provider
        self.worker_name = worker_name
        self.is_running = False

    async def start(self) -> None:
        """Starts the worker and begins subscribing to its target queue."""
        self.is_running = True
        logger.info(f"[Worker] {self.worker_name} started and listening for tasks...")
        await self.queue_provider.subscribe(self.get_queue_name(), self._process_wrapper)

    async def stop(self) -> None:
        """Gracefully shuts down the worker."""
        self.is_running = False
        logger.info(f"[Worker] {self.worker_name} stopped.")

    async def _process_wrapper(self, message: QueueMessage) -> None:
        """Wrapper to handle errors and acknowledgments for the worker's core logic."""
        try:
            await self.handle_message(message)
            await self.queue_provider.acknowledge(message.message_id)
        except Exception as e:
            logger.error(f"[Worker] {self.worker_name} failed to process message {message.message_id}: {e}")
            # Implement retry logic or DLQ based on retry_count
            if message.retry_count < message.max_retries:
                await self.queue_provider.reject(message.message_id, requeue=True)
            else:
                await self.queue_provider.move_to_dlq(message, str(e))

    @abstractmethod
    def get_queue_name(self) -> str:
        """Returns the name of the queue this worker consumes from."""
        pass

    @abstractmethod
    async def handle_message(self, message: QueueMessage) -> Any:
        """The actual work logic to be implemented by specific workers."""
        pass
