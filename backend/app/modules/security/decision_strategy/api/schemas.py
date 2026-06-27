"""
Decision Strategy API — Pydantic request/response schemas.

All endpoints are READ-ONLY.  Schemas are deliberately flat + stable
so the frontend can rely on field names.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..constants import StrategyState, StrategyType


# ── Responses ────────────────────────────────────────────────────────
class StrategyScoreRead(BaseModel):
    dimension: str
    value: float
    weight: float
    contribution: float
    rationale: str

    class Config:
        from_attributes = True


class StrategyCandidateRead(BaseModel):
    candidate_type: StrategyType
    rank: Optional[int]
    is_valid: bool
    rejection_reason: Optional[str]
    composite_score: float
    feasibility_score: float
    risk_score: float
    confidence: float

    class Config:
        from_attributes = True


class StrategyRead(BaseModel):
    id: str
    tenant_id: str
    decision_id: str
    plan_id: Optional[str]
    strategy_type: StrategyType
    state: StrategyState
    priority: int
    confidence: float
    risk_score: float
    feasibility_score: float
    composite_score: float
    business_justification: Optional[str]
    technical_justification: Optional[str]
    selection_reason: Optional[str]
    expected_downtime_min: int
    requires_human_approval: bool
    is_reversible: bool
    correlation_id: Optional[str]
    trace_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrategyDetailRead(StrategyRead):
    """Detail view — includes score breakdown + alternatives."""
    score_breakdown: List[StrategyScoreRead] = Field(default_factory=list)
    alternatives: List[StrategyCandidateRead] = Field(default_factory=list)


class StrategyHistoryRead(BaseModel):
    id: str
    tenant_id: str
    strategy_id: str
    from_state: Optional[StrategyState]
    to_state: StrategyState
    changed_by: str
    change_reason: Optional[str]
    correlation_id: Optional[str]
    trace_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StrategyVersionRead(BaseModel):
    id: str
    tenant_id: str
    strategy_id: str
    version_number: int
    snapshot: Dict[str, Any]
    change_summary: Optional[str]
    correlation_id: Optional[str]
    trace_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StrategyStatisticsRead(BaseModel):
    tenant_id: str
    total_strategies: int
    per_type: Dict[str, Dict[str, Any]]
    per_state: Dict[str, int]
    evaluation_total: int
    avg_evaluation_duration_ms: float

    class Config:
        from_attributes = True


class StrategyListResponse(BaseModel):
    items: List[StrategyRead]
    total: int
    limit: int
    offset: int


class StrategyHistoryListResponse(BaseModel):
    items: List[StrategyHistoryRead]
    total: int


class StrategyVersionListResponse(BaseModel):
    items: List[StrategyVersionRead]
    total: int
