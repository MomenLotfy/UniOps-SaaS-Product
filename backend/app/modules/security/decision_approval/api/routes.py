"""
Read-only FastAPI routes for the Approval Engine.

Mounted at `/security/decision-approvals/` by the parent module.
All endpoints are GET-only.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

from ..constants import ApprovalState, ApprovalType
from ..services import ApprovalService
from .schemas import (
    ApprovalHistoryEntrySchema,
    ApprovalPolicySchema,
    ApprovalRequestDetailSchema,
    ApprovalRequestSchema,
    ApprovalStatisticsSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security/decision-approvals", tags=["decision-approvals"])


def _to_request_schema(row) -> ApprovalRequestSchema:
    return ApprovalRequestSchema(
        id=row.id,
        tenant_id=row.tenant_id,
        decision_id=row.decision_id,
        strategy_id=row.strategy_id,
        approval_state=row.approval_state,
        approval_type=row.approval_type,
        requirement_mode=row.requirement_mode,
        summary=row.summary,
        business_justification=row.business_justification,
        technical_justification=row.technical_justification,
        risk_score=row.risk_score,
        criticality_score=row.criticality_score,
        composite_score=row.composite_score,
        confidence=row.confidence,
        expires_at=row.expires_at,
        is_emergency=row.is_emergency,
        auto_decided=row.auto_decided,
        blocked=row.blocked,
        blocked_reason=row.blocked_reason,
        version=row.version,
        correlation_id=row.correlation_id,
        trace_id=row.trace_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_detail_schema(row) -> ApprovalRequestDetailSchema:
    base = _to_request_schema(row).model_dump()
    base["decisions"] = []
    return ApprovalRequestDetailSchema(**base)


@router.get(
    "/",
    response_model=List[ApprovalRequestSchema],
    summary="List approval requests",
)
async def list_approvals(
    tenant_id: str = Query(..., description="Tenant identifier"),
    approval_state: Optional[ApprovalState] = Query(None, alias="state"),
    approval_type: Optional[ApprovalType] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    svc = ApprovalService(db)
    rows = await svc.list_requests(
        tenant_id,
        state=approval_state,
        approval_type=approval_type,
        limit=limit,
        offset=offset,
    )
    return [_to_request_schema(r) for r in rows]


@router.get(
    "/{approval_id}",
    response_model=ApprovalRequestDetailSchema,
    summary="Get approval detail",
)
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
):
    svc = ApprovalService(db)
    row = await svc.get_request(approval_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ApprovalRequest {approval_id} not found",
        )
    return _to_request_schema(row)


@router.get(
    "/history/{approval_id}",
    response_model=List[ApprovalHistoryEntrySchema],
    summary="Approval state-transition history",
)
async def approval_history(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from ..models.approval import ApprovalHistory

    stmt = (
        select(ApprovalHistory)
        .where(ApprovalHistory.request_id == approval_id)
        .order_by(ApprovalHistory.created_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        ApprovalHistoryEntrySchema(
            id=r.id,
            request_id=r.request_id,
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
    "/statistics",
    response_model=ApprovalStatisticsSchema,
    summary="Tenant-wide approval metrics",
)
async def approval_statistics(
    tenant_id: str = Query(..., description="Tenant identifier"),
    db: AsyncSession = Depends(get_db),
):
    svc = ApprovalService(db)
    data = await svc.get_statistics(tenant_id)
    return ApprovalStatisticsSchema(**data)


@router.get(
    "/policies",
    response_model=List[ApprovalPolicySchema],
    summary="List registered approval policies",
)
async def approval_policies(
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (optional)"),
    db: AsyncSession = Depends(get_db),
):
    svc = ApprovalService(db)
    rows = await svc.list_policies(tenant_id=tenant_id)
    return [
        ApprovalPolicySchema(
            id=r.id,
            tenant_id=r.tenant_id,
            policy_name=r.policy_name,
            policy_version=r.policy_version,
            description=r.description,
            is_active=r.is_active,
            priority=r.priority,
            config=r.config or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


__all__ = ["router"]
