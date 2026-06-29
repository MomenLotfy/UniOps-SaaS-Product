from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.deps import get_db, TenantID
from ..services.decision_service import DecisionService
from ..services.statistics_service import StatisticsService
from ..models.decision import Decision
from .schemas import DecisionRead, DecisionDetailRead, DecisionStatsRead, DecisionHistoryRead

router = APIRouter(prefix="/decisions", tags=["Security Decisions"])

@router.get("/", response_model=List[DecisionRead])
async def get_decisions(
    status: Optional[str] = Query(None),
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db)
):
    """
    List all remediation decisions for the current tenant.
    """
    service = DecisionService(db)
    return await service.list_decisions(tenant_id, status)

@router.get("/{decision_id}", response_model=DecisionDetailRead)
async def get_decision(
    decision_id: str,
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full details for a specific decision.
    """
    service = DecisionService(db)
    decision = await service.get_decision_detail(tenant_id, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Transforming internal model to DetailRead schema
    return {
        "id": decision.id,
        "tenant_id": decision.tenant_id,
        "created_at": decision.created_at,
        "updated_at": decision.updated_at,
        "version": decision.version,
        "correlation_id": decision.correlation_id,
        "trace_id": decision.trace_id,
        "metadata": decision.metadata_json,
        "status": decision.status,
        "final_result": decision.final_result,
        "context_id": decision.context_id,
        "plan_steps": [
            {"type": s.step_type, "result": s.result}
            for s in decision.plan.steps if decision.plan
        ],
        "reasons": [
            {"code": r.reason_code, "desc": r.description}
            for r in decision.reasons
        ],
        "context_summary": decision.context.raw_data if decision.context else {},
        "policy_ref": {
            "id": decision.policy_ref.policy_id,
            "version": decision.policy_ref.policy_version
        } if decision.policy_ref else None
    }

@router.get("/statistics", response_model=List[DecisionStatsRead])
async def get_decision_stats(
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated metrics for decision outcomes.

    Sprint 2 R23: wired to the real ``StatisticsService.get_tenant_metrics``
    which reads from ``security_decision_statistics`` (one bucket per state).
    Returns one ``DecisionStatsRead`` row per state with non-zero count.
    """
    stats_service = StatisticsService(db)
    metrics = await stats_service.get_tenant_metrics(tenant_id)
    by_state = metrics.get("by_state", {}) or {}
    avg_durations = metrics.get("avg_durations", {}) or {}
    return [
        DecisionStatsRead(
            state=str(state),
            count=int(by_state[state]),
            avg_duration_ms=float(avg_durations.get(state, 0.0)),
        )
        for state in by_state
    ]

@router.get("/history/{decision_id}", response_model=List[DecisionHistoryRead])
async def get_decision_history(
    decision_id: str,
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the state transition history for a decision.
    """
    from ..models.decision import DecisionHistory
    from sqlalchemy import select

    result = await db.execute(
        select(DecisionHistory).where(DecisionHistory.decision_id == decision_id, DecisionHistory.tenant_id == tenant_id)
    )
    history = result.scalars().all()

    return [
        DecisionHistoryRead(
            id=h.id,
            tenant_id=h.tenant_id,
            created_at=h.created_at,
            updated_at=h.updated_at,
            version=h.version,
            correlation_id=h.correlation_id,
            trace_id=h.trace_id,
            metadata=h.metadata_json,
            decision_id=h.decision_id,
            from_state=h.from_state,
            to_state=h.to_state,
            changed_by=h.changed_by,
            change_reason=h.change_reason
        ) for h in history
    ]
