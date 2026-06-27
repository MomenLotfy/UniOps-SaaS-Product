from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from ..constants import DecisionState

class DecisionBaseSchema(BaseModel):
    """
    Common fields for all Decision Engine schemas.
    """
    tenant_id: str
    created_at: datetime
    updated_at: datetime
    version: int
    correlation_id: str
    trace_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

class DecisionRead(DecisionBaseSchema):
    """
    Schema for returning a Decision object.
    """
    id: str
    status: DecisionState
    final_result: Optional[str] = None
    context_id: str

class DecisionHistoryRead(DecisionBaseSchema):
    """
    Schema for returning decision state history.
    """
    id: str
    decision_id: str
    from_state: Optional[DecisionState] = None
    to_state: DecisionState
    changed_by: str
    change_reason: Optional[str] = None

class DecisionStatsRead(BaseModel):
    """
    Schema for decision pipeline statistics.
    """
    state: str
    count: int
    avg_duration_ms: float

class DecisionDetailRead(DecisionRead):
    """
    Full detailed view of a decision including its plan and reasoning.
    """
    plan_steps: List[dict] = []
    reasons: List[dict] = []
    context_summary: dict = {}
    policy_ref: Optional[dict] = None
