"""
Pydantic schemas for the read-only Approval API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..constants import (
    ApprovalActorRole,
    ApprovalOutcome,
    ApprovalRequirementMode,
    ApprovalState,
    ApprovalType,
)


class ApprovalDecisionSchema(BaseModel):
    id: str
    request_id: str
    approver_id: str
    approver_role: Optional[str] = None
    outcome: ApprovalOutcome
    rationale: Optional[str] = None
    decided_at: Optional[str] = None
    created_at: datetime


class ApprovalRequirementSchema(BaseModel):
    id: str
    request_id: str
    required_role: str
    sequence_order: int
    is_mandatory: bool
    description: Optional[str] = None
    created_at: datetime


class ApprovalConstraintSchema(BaseModel):
    id: str
    request_id: str
    constraint_type: str
    is_met: bool
    details: Optional[str] = None
    created_at: datetime


class ApprovalEvidenceSchema(BaseModel):
    id: str
    request_id: str
    evidence_type: str
    evidence_value: str
    source: Optional[str] = None
    created_at: datetime


class ApprovalReasonSchema(BaseModel):
    id: str
    request_id: str
    reason_code: str
    description: str
    category: str
    created_at: datetime


class ApprovalHistoryEntrySchema(BaseModel):
    id: str
    request_id: str
    from_state: Optional[ApprovalState] = None
    to_state: ApprovalState
    changed_by: str
    change_reason: Optional[str] = None
    changed_at: Optional[str] = None
    created_at: datetime


class ApprovalAuditEntrySchema(BaseModel):
    id: str
    request_id: str
    event_type: str
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    occurred_at: Optional[str] = None
    created_at: datetime


class ApprovalRequestSchema(BaseModel):
    id: str
    tenant_id: str
    decision_id: str
    strategy_id: Optional[str] = None
    approval_state: ApprovalState
    approval_type: ApprovalType
    requirement_mode: ApprovalRequirementMode
    summary: Optional[str] = None
    business_justification: Optional[str] = None
    technical_justification: Optional[str] = None
    risk_score: float
    criticality_score: float
    composite_score: float
    confidence: float
    expires_at: Optional[str] = None
    is_emergency: bool
    auto_decided: bool
    blocked: bool
    blocked_reason: Optional[str] = None
    version: int
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ApprovalRequestDetailSchema(ApprovalRequestSchema):
    decisions: List[ApprovalDecisionSchema] = Field(default_factory=list)
    requirements: List[ApprovalRequirementSchema] = Field(default_factory=list)
    constraints: List[ApprovalConstraintSchema] = Field(default_factory=list)
    evidence: List[ApprovalEvidenceSchema] = Field(default_factory=list)
    reasons: List[ApprovalReasonSchema] = Field(default_factory=list)


class ApprovalPolicySchema(BaseModel):
    id: str
    tenant_id: str
    policy_name: str
    policy_version: int
    description: Optional[str] = None
    is_active: bool
    priority: int
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ApprovalStatisticsSchema(BaseModel):
    tenant_id: str
    by_type_state: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
#  Sprint 2 R24: mutation request / response schemas
# ─────────────────────────────────────────────────────────────────────
class ApprovalActionRequest(BaseModel):
    """
    Payload for ``POST /security/decision-approvals/{id}/actions``.

    Exactly one of ``approve`` / ``reject`` / ``cancel`` / ``archive`` must be
    supplied.  ``reason`` is optional but recommended for audit traceability.
    """
    approve: Optional[bool] = None
    reject: Optional[bool] = None
    cancel: Optional[bool] = None
    archive: Optional[bool] = None
    reason: Optional[str] = Field(default=None, max_length=2000)
    actor_id: Optional[str] = Field(default=None, max_length=100)
    actor_role: Optional[str] = Field(default=None, max_length=100)


class ApprovalActionResponse(BaseModel):
    """Returned by every mutating endpoint."""
    approval_id: str
    tenant_id: str
    previous_state: ApprovalState
    new_state: ApprovalState
    version: int
    changed_by: str
    change_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    replayed: bool = False
    occurred_at: datetime


class IdempotencyRecord(BaseModel):
    """Persisted record used to satisfy Idempotency-Key semantics."""

    tenant_id: str
    key: str
    request_id: str
    payload_hash: str
    response_snapshot: Dict[str, Any]
    created_at: datetime


__all__ = [
    "ApprovalActionRequest",
    "ApprovalActionResponse",
    "ApprovalActorRole",
    "ApprovalAuditEntrySchema",
    "ApprovalConstraintSchema",
    "ApprovalDecisionSchema",
    "ApprovalEvidenceSchema",
    "ApprovalHistoryEntrySchema",
    "ApprovalPolicySchema",
    "ApprovalReasonSchema",
    "ApprovalRequestDetailSchema",
    "ApprovalRequestSchema",
    "ApprovalRequirementSchema",
    "ApprovalStatisticsSchema",
    "IdempotencyRecord",
]