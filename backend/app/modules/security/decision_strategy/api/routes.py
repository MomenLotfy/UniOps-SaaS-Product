"""
Decision Strategy API routes.

4 read-only endpoints:
  GET /security/decision-strategies                    list strategies
  GET /security/decision-strategies/{id}              strategy detail
  GET /security/decision-strategies/statistics        tenant-wide stats
  GET /security/decision-strategies/history/{id}      state-transition history

Mirrors the `decision_engine/api/routes.py` conventions exactly:
  - router prefix `/decision-strategies`
  - tag `Security Decision Strategies`
  - tenant_id from `TenantID` dependency (no path/query leakage)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, TenantID

from ..constants import StrategyState, StrategyType
from ..models.strategy import DecisionStrategy
from ..services.strategy_service import DecisionStrategyService
from .schemas import (
    StrategyDetailRead,
    StrategyHistoryListResponse,
    StrategyHistoryRead,
    StrategyListResponse,
    StrategyRead,
    StrategyStatisticsRead,
)

router = APIRouter(prefix="/decision-strategies", tags=["Security Decision Strategies"])


# ── List ─────────────────────────────────────────────────────────────
@router.get("/", response_model=StrategyListResponse)
async def list_strategies(
    state: Optional[StrategyState] = Query(None, description="Filter by state"),
    strategy_type: Optional[StrategyType] = Query(None, description="Filter by type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db),
) -> StrategyListResponse:
    """
    List decision strategies for the current tenant.
    """
    service = DecisionStrategyService(db)
    rows = await service.list_strategies(
        tenant_id=tenant_id,
        state=state,
        strategy_type=strategy_type,
        limit=limit,
        offset=offset,
    )
    return StrategyListResponse(
        items=[StrategyRead.model_validate(r) for r in rows],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


# ── Detail ───────────────────────────────────────────────────────────
@router.get("/{strategy_id}", response_model=StrategyDetailRead)
async def get_strategy(
    strategy_id: str,
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db),
) -> StrategyDetailRead:
    """
    Full detail for a single strategy, including score breakdown and
    rejected alternatives for audit.
    """
    service = DecisionStrategyService(db)
    strategy: Optional[DecisionStrategy] = await service.get_strategy(strategy_id)

    if strategy is None or strategy.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Decision strategy not found")

    score_breakdown = [
        {
            "dimension": s.dimension,
            "value": s.value,
            "weight": s.weight,
            "contribution": s.contribution,
            "rationale": s.rationale,
        }
        for c in (strategy.candidates or [])
        if c.rank == 1
        for s in (c.scores or [])
    ]

    alternatives = [
        {
            "candidate_type": c.candidate_type,
            "rank": c.rank,
            "is_valid": c.is_valid,
            "rejection_reason": c.rejection_reason,
            "composite_score": c.composite_score,
            "feasibility_score": c.feasibility_score,
            "risk_score": c.risk_score,
            "confidence": c.confidence,
        }
        for c in (strategy.candidates or [])
        if c.rank is None
    ]

    return StrategyDetailRead(
        id=strategy.id,
        tenant_id=strategy.tenant_id,
        decision_id=strategy.decision_id,
        plan_id=strategy.plan_id,
        strategy_type=strategy.strategy_type,
        state=strategy.state,
        priority=strategy.priority,
        confidence=strategy.confidence,
        risk_score=strategy.risk_score,
        feasibility_score=strategy.feasibility_score,
        composite_score=strategy.composite_score,
        business_justification=strategy.business_justification,
        technical_justification=strategy.technical_justification,
        selection_reason=strategy.selection_reason,
        expected_downtime_min=strategy.expected_downtime_min or 0,
        requires_human_approval=strategy.requires_human_approval,
        is_reversible=strategy.is_reversible,
        correlation_id=strategy.correlation_id,
        trace_id=strategy.trace_id,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
        score_breakdown=score_breakdown,
        alternatives=alternatives,
    )


# ── Statistics ───────────────────────────────────────────────────────
@router.get("/statistics", response_model=StrategyStatisticsRead)
async def get_statistics(
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db),
) -> StrategyStatisticsRead:
    """
    Tenant-wide strategy metrics: per-type + per-state counts, total
    evaluations, average evaluation duration.
    """
    service = DecisionStrategyService(db)
    stats = await service.get_statistics(tenant_id)
    return StrategyStatisticsRead(**stats)


# ── History ──────────────────────────────────────────────────────────
@router.get("/history/{strategy_id}", response_model=StrategyHistoryListResponse)
async def get_history(
    strategy_id: str,
    tenant_id: str = Depends(TenantID),
    db: AsyncSession = Depends(get_db),
) -> StrategyHistoryListResponse:
    """
    State-transition history for one strategy.
    """
    service = DecisionStrategyService(db)
    strategy = await service.get_strategy(strategy_id)
    if strategy is None or strategy.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Decision strategy not found")

    history = await service.list_history(strategy_id)
    items = [StrategyHistoryRead.model_validate(h) for h in history]
    return StrategyHistoryListResponse(items=items, total=len(items))
