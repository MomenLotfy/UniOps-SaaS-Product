"""
Read-only FastAPI routes for the Approval Engine.

Mounted at `/security/decision-approvals/` by the parent module.

Sprint 2 R24: now exposes mutating endpoints behind ``POST``.  Every
mutation honours the ``Idempotency-Key`` request header (RFC draft)
so retries are safe.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

from ..constants import ApprovalState, ApprovalType
from ..services import ApprovalService
from ..services.approval_manager import ApprovalManager
from ..services.idempotency_service import IdempotencyService
from .schemas import (
    ApprovalActionRequest,
    ApprovalActionResponse,
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


@router.post(
    "/{approval_id}/actions",
    response_model=ApprovalActionResponse,
    summary="Apply an approval action (approve / reject / cancel / archive)",
    status_code=status.HTTP_200_OK,
)
async def apply_approval_action(
    approval_id: str,
    payload: ApprovalActionRequest,
    tenant_id: str = Query(..., description="Tenant identifier"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key", max_length=255),
    db: AsyncSession = Depends(get_db),
) -> ApprovalActionResponse:
    """
    Mutate the lifecycle of an approval request.

    Honours the ``Idempotency-Key`` header: replays of the same key
    (with the same body) return the original response without re-applying
    the transition.  The same key with a different body raises 409.
    """
    chosen = [
        name for name, flag in (
            ("approve", payload.approve),
            ("reject",  payload.reject),
            ("cancel",  payload.cancel),
            ("archive", payload.archive),
        ) if flag
    ]
    if len(chosen) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of approve / reject / cancel / archive must be set",
        )

    body_for_hash = payload.model_dump()
    body_for_hash["approval_id"] = approval_id

    idem = IdempotencyService(db)
    replay = await idem.lookup(tenant_id, idempotency_key or "", body_for_hash)
    if replay:
        replay["replayed"] = True
        return ApprovalActionResponse(**replay)

    # Verify the request belongs to the tenant before mutating.
    svc = ApprovalService(db)
    row = await svc.get_request(approval_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ApprovalRequest {approval_id} not found",
        )
    previous_state = row.approval_state

    actor_id = payload.actor_id or "anonymous"
    manager = ApprovalManager(db)
    if chosen[0] == "approve":
        updated = await manager.approve(approval_id, changed_by=actor_id, reason=payload.reason)
    elif chosen[0] == "reject":
        updated = await manager.reject(approval_id, changed_by=actor_id, reason=payload.reason)
    elif chosen[0] == "cancel":
        updated = await manager.cancel(approval_id, changed_by=actor_id, reason=payload.reason)
    else:  # archive
        updated = await manager.archive(approval_id, changed_by=actor_id, reason=payload.reason)

    response = ApprovalActionResponse(
        approval_id=approval_id,
        tenant_id=tenant_id,
        previous_state=previous_state,
        new_state=updated.approval_state,
        version=updated.version,
        changed_by=actor_id,
        change_reason=payload.reason,
        idempotency_key=idempotency_key,
        replayed=False,
        occurred_at=datetime.now(timezone.utc),
    )
    await idem.store(
        tenant_id,
        idempotency_key,
        request_id=updated.id,
        payload=body_for_hash,
        response_snapshot=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/{approval_id}/expire",
    response_model=ApprovalActionResponse,
    summary="Force an approval request into EXPIRED (system action)",
)
async def expire_approval(
    approval_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
    db: AsyncSession = Depends(get_db),
) -> ApprovalActionResponse:
    """System-only path used by the scheduler to expire stale approvals."""
    svc = ApprovalService(db)
    row = await svc.get_request(approval_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ApprovalRequest {approval_id} not found",
        )
    previous_state = row.approval_state
    manager = ApprovalManager(db)
    updated = await manager.expire(approval_id)
    return ApprovalActionResponse(
        approval_id=approval_id,
        tenant_id=tenant_id,
        previous_state=previous_state,
        new_state=updated.approval_state,
        version=updated.version,
        changed_by="system",
        change_reason="TTL elapsed",
        idempotency_key=None,
        replayed=False,
        occurred_at=datetime.now(timezone.utc),
    )


__all__ = ["router"]
