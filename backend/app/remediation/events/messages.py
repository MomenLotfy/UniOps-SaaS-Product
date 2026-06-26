from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class RemediationEventType(str, Enum):
    """Typed event keys for the remediation event bus."""
    # Request & Planning
    REMEDIATION_REQUESTED = "remediation.requested"
    EXECUTION_PLANNED = "execution.planned"
    CAPABILITY_RESOLVED = "capability.resolved"

    # Queue & Scheduling
    EXECUTION_QUEUED = "execution.queued"

    # Runtime Execution
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"

    # Validation
    VALIDATION_REQUESTED = "validation.requested"
    VALIDATION_COMPLETED = "validation.completed"
    VALIDATION_FAILED = "validation.failed"

    # Recovery
    ROLLBACK_REQUESTED = "rollback.requested"
    ROLLBACK_COMPLETED = "rollback.completed"

class RemediationMessage(BaseModel):
    """
    Immutable message schema for the event bus.
    Every event must follow this structure for consistency and traceability.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: RemediationEventType
    version: str = "1.0"

    tenant_id: str
    execution_id: str
    correlation_id: str

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_component: str # e.g. 'PlanningWorker', 'ExecutionPipeline'

    payload: Dict[str, Any]
    metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()
