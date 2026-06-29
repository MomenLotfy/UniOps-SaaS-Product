"""
Read-only FastAPI routes for the Execution Orchestration Engine.

Mounted at `/security/execution-packages/` by the parent module.
All endpoints are GET-only.

Sprint 1 R8 — every endpoint now authenticates via
``get_current_active_user`` and reads the tenant from the JWT via
``get_tenant_id`` instead of accepting a raw ``tenant_id`` query
parameter.  The previous design let any unauthenticated caller
read another tenant's execution packages by passing
``?tenant_id=...`` in the URL.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user, get_tenant_id

from ..constants import ExecutionPackageState
from ..services import ExecutionService
from .schemas import (
    ExecutionAuditEntrySchema,
    ExecutionConstraintSchema,
    ExecutionDependencySchema,
    ExecutionHistoryEntrySchema,
    ExecutionMetadataSchema,
    ExecutionPackageDetailSchema,
    ExecutionPackageSchema,
    ExecutionPreparationSchema,
    ExecutionReadinessSchema,
    ExecutionRequirementSchema,
    ExecutionStatisticsEntrySchema,
    ExecutionStatisticsSchema,
    ExecutionSummarySchema,
    ExecutionVersionSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/security/execution-packages",
    tags=["execution-orchestration"],
)


# ─────────────────────────────────────────────────────────────────────
#  Mappers
# ─────────────────────────────────────────────────────────────────────
def _to_package_schema(row) -> ExecutionPackageSchema:
    return ExecutionPackageSchema(
        id=row.id,
        tenant_id=row.tenant_id,
        decision_id=row.decision_id,
        strategy_id=row.strategy_id,
        approval_id=row.approval_id,
        package_state=row.package_state,
        package_version=row.package_version,
        is_immutable=row.is_immutable,
        is_ready=row.is_ready,
        is_rejected=row.is_rejected,
        rejection_reason=row.rejection_reason,
        decision_version=row.decision_version,
        strategy_version=row.strategy_version,
        approval_version=row.approval_version,
        summary=row.summary,
        payload_hash=row.payload_hash,
        dependency_count=row.dependency_count,
        constraint_count=row.constraint_count,
        metadata_count=row.metadata_count,
        package_size_kb=row.package_size_kb,
        version=row.version,
        correlation_id=row.correlation_id,
        trace_id=row.trace_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_detail_schema(row, summary=None) -> ExecutionPackageDetailSchema:
    base = _to_package_schema(row).model_dump()
    if summary is not None:
        base["readiness_status"]  = summary.readiness_status
        base["validation_results"] = summary.validation_results or {}
        base["selected_strategy"]  = summary.selected_strategy
        base["approval_status"]    = summary.approval_status
    else:
        base["readiness_status"]  = None
        base["validation_results"] = {}
        base["selected_strategy"]  = None
        base["approval_status"]    = "UNKNOWN"
    return ExecutionPackageDetailSchema(**base)


# ─────────────────────────────────────────────────────────────────────
#  Endpoints  (R8: tenant comes from JWT, user is authenticated)
# ─────────────────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=List[ExecutionPackageSchema],
    summary="List execution packages",
)
async def list_packages(
    tenant_id: str = Depends(get_tenant_id),
    package_state: Optional[ExecutionPackageState] = Query(None, alias="state"),
    decision_id: Optional[str] = Query(None, description="Filter by originating decision"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_packages(
        tenant_id,
        state=package_state,
        decision_id=decision_id,
        limit=limit,
        offset=offset,
    )
    return [_to_package_schema(r) for r in rows]


@router.get(
    "/statistics",
    response_model=ExecutionStatisticsSchema,
    summary="Tenant-wide execution package metrics",
)
async def package_statistics(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    data = await svc.get_statistics(tenant_id)
    return ExecutionStatisticsSchema(**data)


@router.get(
    "/{package_id}",
    response_model=ExecutionPackageDetailSchema,
    summary="Get execution package detail",
)
async def get_package(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    row = await svc.get_package(tenant_id, package_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ExecutionPackage {package_id} not found",
        )
    summary = await svc.get_summary(tenant_id, package_id)
    return _to_detail_schema(row, summary=summary)


@router.get(
    "/{package_id}/preparation",
    response_model=ExecutionPreparationSchema,
    summary="Pre-pipeline snapshot for a package",
)
async def get_preparation(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    row = await svc.get_preparation(tenant_id, package_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preparation for {package_id} not found",
        )
    return ExecutionPreparationSchema(
        id=row.id,
        package_id=row.package_id,
        decision_id=row.decision_id,
        is_complete=row.is_complete,
        missing_fields=row.missing_fields,
        decision_snapshot=row.decision_snapshot or {},
        strategy_snapshot=row.strategy_snapshot or {},
        approval_snapshot=row.approval_snapshot or {},
        context_snapshot=row.context_snapshot or {},
        created_at=row.created_at,
    )


@router.get(
    "/{package_id}/readiness",
    response_model=ExecutionReadinessSchema,
    summary="Readiness verdict for a package",
)
async def get_readiness(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    row = await svc.get_readiness(tenant_id, package_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Readiness for {package_id} not found",
        )
    return ExecutionReadinessSchema(
        id=row.id,
        package_id=row.package_id,
        outcome=row.outcome,
        factors_total=row.factors_total,
        factors_passed=row.factors_passed,
        factors_warned=row.factors_warned,
        factors_failed=row.factors_failed,
        validation_ms=row.validation_ms,
        verdicts=row.verdicts,
        created_at=row.created_at,
    )


@router.get(
    "/{package_id}/dependencies",
    response_model=List[ExecutionDependencySchema],
    summary="Resolved dependencies for a package",
)
async def list_dependencies(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_dependencies(tenant_id, package_id)
    return [
        ExecutionDependencySchema(
            id=r.id,
            package_id=r.package_id,
            kind=r.kind,
            reference=r.reference,
            display_name=r.display_name,
            is_resolved=r.is_resolved,
            resolution_ms=r.resolution_ms,
            notes=r.notes,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/constraints",
    response_model=List[ExecutionConstraintSchema],
    summary="Hard constraints evaluated for a package",
)
async def list_constraints(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_constraints(tenant_id, package_id)
    return [
        ExecutionConstraintSchema(
            id=r.id,
            package_id=r.package_id,
            constraint_type=r.constraint_type,
            is_met=r.is_met,
            severity=r.severity,
            details=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/requirements",
    response_model=List[ExecutionRequirementSchema],
    summary="Soft requirements attached to a package",
)
async def list_requirements(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_requirements(tenant_id, package_id)
    return [
        ExecutionRequirementSchema(
            id=r.id,
            package_id=r.package_id,
            requirement_type=r.requirement_type,
            value=r.value,
            is_mandatory=r.is_mandatory,
            description=r.description,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/metadata",
    response_model=List[ExecutionMetadataSchema],
    summary="Free-form metadata attached to a package",
)
async def list_metadata(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_metadata(tenant_id, package_id)
    return [
        ExecutionMetadataSchema(
            id=r.id,
            package_id=r.package_id,
            key=r.key,
            value=r.value,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/history",
    response_model=List[ExecutionHistoryEntrySchema],
    summary="State-change history for a package",
)
async def package_history(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_history(tenant_id, package_id)
    return [
        ExecutionHistoryEntrySchema(
            id=r.id,
            package_id=r.package_id,
            from_state=r.from_state,
            to_state=r.to_state,
            changed_by=r.changed_by,
            change_reason=r.change_reason,
            changed_at=r.changed_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/audit",
    response_model=List[ExecutionAuditEntrySchema],
    summary="Append-only audit ledger for a package",
)
async def package_audit(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_audit(tenant_id, package_id)
    return [
        ExecutionAuditEntrySchema(
            id=r.id,
            package_id=r.package_id,
            event_type=r.event_type,
            actor_id=r.actor_id,
            actor_role=r.actor_role,
            details=r.details,
            occurred_at=r.occurred_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/versions",
    response_model=List[ExecutionVersionSchema],
    summary="Versioned snapshots for a package",
)
async def package_versions(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_versions(tenant_id, package_id)
    return [
        ExecutionVersionSchema(
            id=r.id,
            package_id=r.package_id,
            version_number=r.version_number,
            snapshot=r.snapshot or {},
            change_summary=r.change_summary,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/statistics",
    response_model=List[ExecutionStatisticsEntrySchema],
    summary="Per-package metrics rows",
)
async def package_statistics_rows(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    rows = await svc.list_statistics(tenant_id, package_id)
    return [
        ExecutionStatisticsEntrySchema(
            id=r.id,
            package_id=r.package_id,
            package_state=r.package_state,
            count=r.count,
            avg_duration_ms=r.avg_duration_ms,
            avg_package_size_kb=r.avg_package_size_kb,
            rejected_count=r.rejected_count,
            ready_count=r.ready_count,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{package_id}/summary",
    response_model=ExecutionSummarySchema,
    summary="Denormalised summary for fast UI reads",
)
async def package_summary(
    package_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_active_user),
):
    svc = ExecutionService(db)
    row = await svc.get_summary(tenant_id, package_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary for {package_id} not found",
        )
    return ExecutionSummarySchema(
        id=row.id,
        package_id=row.package_id,
        readiness_status=row.readiness_status,
        validation_results=row.validation_results or {},
        selected_strategy=row.selected_strategy,
        approval_status=row.approval_status,
        dependency_count=row.dependency_count,
        constraint_passed=row.constraint_passed,
        constraint_failed=row.constraint_failed,
        package_metadata=row.package_metadata or {},
        package_timeline=row.package_timeline or [],
        created_at=row.created_at,
    )


__all__ = ["router"]