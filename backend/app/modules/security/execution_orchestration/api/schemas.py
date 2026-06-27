"""
Pydantic schemas for the read-only Execution API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..constants import (
    ExecutionConstraintType,
    ExecutionDependencyKind,
    ExecutionPackageState,
    ReadinessFactor,
    ReadinessOutcome,
)


class ExecutionPackageSchema(BaseModel):
    id: str
    tenant_id: str
    decision_id: str
    strategy_id: Optional[str] = None
    approval_id: Optional[str] = None
    package_state: ExecutionPackageState
    package_version: int
    is_immutable: bool
    is_ready: bool
    is_rejected: bool
    rejection_reason: Optional[str] = None
    decision_version: Optional[int] = None
    strategy_version: Optional[int] = None
    approval_version: Optional[int] = None
    summary: Optional[str] = None
    payload_hash: Optional[str] = None
    dependency_count: int
    constraint_count: int
    metadata_count: int
    package_size_kb: float
    version: int
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExecutionPackageDetailSchema(ExecutionPackageSchema):
    readiness_status: Optional[str] = None
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    selected_strategy: Optional[str] = None
    approval_status: Optional[str] = None


class ExecutionPreparationSchema(BaseModel):
    id: str
    package_id: str
    decision_id: str
    is_complete: bool
    missing_fields: Optional[str] = None
    decision_snapshot: Dict[str, Any] = Field(default_factory=dict)
    strategy_snapshot: Dict[str, Any] = Field(default_factory=dict)
    approval_snapshot: Dict[str, Any] = Field(default_factory=dict)
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ExecutionReadinessSchema(BaseModel):
    id: str
    package_id: str
    outcome: ReadinessOutcome
    factors_total: int
    factors_passed: int
    factors_warned: int
    factors_failed: int
    validation_ms: float
    verdicts: Optional[str] = None
    created_at: datetime


class ExecutionDependencySchema(BaseModel):
    id: str
    package_id: str
    kind: ExecutionDependencyKind
    reference: str
    display_name: Optional[str] = None
    is_resolved: bool
    resolution_ms: float
    notes: Optional[str] = None
    created_at: datetime


class ExecutionConstraintSchema(BaseModel):
    id: str
    package_id: str
    constraint_type: ExecutionConstraintType
    is_met: bool
    severity: str
    details: Optional[str] = None
    created_at: datetime


class ExecutionRequirementSchema(BaseModel):
    id: str
    package_id: str
    requirement_type: str
    value: Optional[str] = None
    is_mandatory: bool
    description: Optional[str] = None
    created_at: datetime


class ExecutionMetadataSchema(BaseModel):
    id: str
    package_id: str
    key: str
    value: str
    created_at: datetime


class ExecutionHistoryEntrySchema(BaseModel):
    id: str
    package_id: str
    from_state: Optional[ExecutionPackageState] = None
    to_state: ExecutionPackageState
    changed_by: str
    change_reason: Optional[str] = None
    changed_at: Optional[str] = None
    created_at: datetime


class ExecutionAuditEntrySchema(BaseModel):
    id: str
    package_id: str
    event_type: str
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    occurred_at: Optional[str] = None
    created_at: datetime


class ExecutionVersionSchema(BaseModel):
    id: str
    package_id: str
    version_number: int
    snapshot: Dict[str, Any]
    change_summary: Optional[str] = None
    created_at: datetime


class ExecutionStatisticsEntrySchema(BaseModel):
    id: str
    package_id: Optional[str] = None
    package_state: ExecutionPackageState
    count: int
    avg_duration_ms: float
    avg_package_size_kb: float
    rejected_count: int
    ready_count: int
    created_at: datetime


class ExecutionStatisticsSchema(BaseModel):
    tenant_id: str
    by_state: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None


class ExecutionSummarySchema(BaseModel):
    id: str
    package_id: str
    readiness_status: str
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    selected_strategy: Optional[str] = None
    approval_status: str
    dependency_count: int
    constraint_passed: int
    constraint_failed: int
    package_metadata: Dict[str, Any] = Field(default_factory=dict)
    package_timeline: List[Any] = Field(default_factory=list)
    created_at: datetime


__all__ = [
    "ExecutionAuditEntrySchema",
    "ExecutionConstraintSchema",
    "ExecutionDependencySchema",
    "ExecutionHistoryEntrySchema",
    "ExecutionMetadataSchema",
    "ExecutionPackageDetailSchema",
    "ExecutionPackageSchema",
    "ExecutionPreparationSchema",
    "ExecutionReadinessSchema",
    "ExecutionRequirementSchema",
    "ExecutionStatisticsEntrySchema",
    "ExecutionStatisticsSchema",
    "ExecutionSummarySchema",
    "ExecutionVersionSchema",
]