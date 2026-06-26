from __future__ import annotations
from typing import List, Dict
from app.remediation.workers.base import BaseRemediationWorker
from app.remediation.queue.interfaces import IQueueProvider
from app.utils.logger import logger

class PlanningWorker(BaseRemediationWorker):
    def get_queue_name(self) -> str:
        return "remediation.planning"

    async def handle_message(self, message: Any) -> Any:
        logger.info(f"[PlanningWorker] Processing planning request for execution: {message.payload.get('execution_id')}")
        # Logic for Decision Engine and ExecutionPlan generation goes here.
        return {"status": "plan_generated"}

class ExecutionWorker(BaseRemediationWorker):
    def get_queue_name(self) -> str:
        return "remediation.execution"

    async def handle_message(self, message: Any) -> Any:
        logger.info(f"[ExecutionWorker] Executing remediation plan: {message.payload.get('plan_id')}")
        # Logic for calling the specific plugin strategy goes here.
        return {"status": "executed"}

class ValidationWorker(BaseRemediationWorker):
    def get_queue_name(self) -> str:
        return "remediation.validation"

    async def handle_message(self, message: Any) -> Any:
        logger.info(f la "[ValidationWorker] Validating plan: {message.payload.get('plan_id')}")
        # Logic for calling IRemediationValidator goes here.
        return {"status": "validated"}

class NotificationWorker(BaseRemediationWorker):
    def get_queue_name(self) -> str:
        return "remediation.notifications"

    async def handle_message(self, message: Any) -> Any:
        logger.info(f"[NotificationWorker] Sending notification for event: {message.payload.get('event_type')}")
        return {"status": "notified"}

class MetricsWorker(BaseRemediationWorker):
    def get_queue_name(self) -> str:
        return "remediation.metrics"

    async def handle_message(self, message: Any) -> Any:
        logger.info(f"[MetricsWorker] Recording metrics for execution: {message.payload.get('execution_id')}")
        return {"status": "recorded"}

class WorkerRegistry:
    """Manages the lifecycle of all remediation workers."""
    def __init__(self, queue_provider: IQueueProvider):
        self.queue_provider = queue_provider
        self.workers: Dict[str, BaseRemediationWorker] = {}

    def register_worker(self, worker_cls: type[BaseRemediationWorker]) -> None:
        worker = worker_cls(self.queue_provider, worker_cls.__name__)
        self.workers[worker_cls.__name__] = worker

    async def start_all(self) -> None:
        for worker in self.workers.values():
            await worker.start()

    async def stop_all(self) -> None:
        for worker in self.workers.values():
            await worker.stop()
