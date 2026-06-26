from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class RemediationEvent(Enum):
    """Event types for the remediation lifecycle."""
    PLAN_GENERATED = "plan_generated"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    VALIDATION_FAILED = "validation_failed"

class RemediationEventPayload(BaseModel):
    """Standard payload for all remediation events."""
    event_type: RemediationEvent
    tenant_id: str
    plan_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Contextual data (finding_id, strategy_id, etc.)
    metadata: Dict[str, Any] = {}

    # Detailed result or error
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event_type.value,
            "tenant_id": self.tenant_id,
            "plan_id": self.plan_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "result": self.result,
            "error": self.error
        }
