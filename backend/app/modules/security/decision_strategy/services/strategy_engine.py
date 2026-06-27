"""
Decision Strategy Engine.

Deterministic orchestrator: takes a `Decision` + aggregated
`DecisionContext`, asks the registry for candidate descriptors, and
returns a `StrategyEvaluationResult` (winner + ranked list + diagnostics).

Mirrors `DecisionEngine` in the sibling decision_engine module.

Pure-function entry point: `evaluate(...)`.  Persistence is the
caller's responsibility — see `StrategyEvaluationPipeline`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from ..constants import STRATEGY_CACHE_TTL_SECONDS, StrategyState
from ..models.strategy import (
    DecisionStrategy,
    StrategyCandidate,
    StrategyConstraint,
    StrategyMetadata,
    StrategyReason,
    StrategyRequirement,
    StrategyScore,
)
from .strategy_cache import DecisionStrategyCache
from .strategy_candidate_builder import StrategyCandidateBuilder
from .strategy_comparator import DecisionStrategyComparator
from .strategy_interfaces import (
    StrategyCandidateData,
    StrategyEvaluationResult,
)
from .strategy_ranking_engine import StrategyRankingEngine
from .strategy_registry import DecisionStrategyRegistry, bootstrap_default_strategies
from .strategy_selector import DecisionStrategySelector

logger = logging.getLogger(__name__)


class DecisionStrategyEngine:
    """
    Deterministic strategy selection.

    Composition root holds:
      - registry (17 descriptors by default)
      - candidate builder (resolver + factory + validator + scoring)
      - ranking engine (comparator-based, deterministic)
      - selector (top-valid, then NO_ACTION fallback)
      - cache (TTL-keyed by tenant + decision + context hash)
    """

    def __init__(
        self,
        registry: Optional[DecisionStrategyRegistry] = None,
        cache: Optional[DecisionStrategyCache] = None,
        cache_enabled: bool = True,
    ) -> None:
        from .strategy_factory import DecisionStrategyFactory
        from .strategy_resolver import DecisionStrategyResolver
        from .strategy_scoring_engine import StrategyScoringEngine
        from .strategy_validator import DecisionStrategyValidator

        self._registry = registry or DecisionStrategyRegistry()
        # Ensure the 17 canonical descriptors are present.  Skipping
        # bootstrap when the caller passes a fully-populated registry is
        # by design — useful for tests with isolated registries.
        if not registry:
            bootstrap_default_strategies(self._registry)
        self._factory  = DecisionStrategyFactory()
        self._resolver = DecisionStrategyResolver(self._registry)
        self._validator = DecisionStrategyValidator()
        self._scoring   = StrategyScoringEngine()
        self._builder   = StrategyCandidateBuilder(
            resolver=self._resolver,
            factory=self._factory,
            validator=self._validator,
            scoring_engine=self._scoring,
        )
        self._comparator = DecisionStrategyComparator()
        self._ranking    = StrategyRankingEngine(self._comparator)
        self._selector   = DecisionStrategySelector()
        self._cache_enabled = cache_enabled
        self._cache = cache or DecisionStrategyCache(ttl_seconds=STRATEGY_CACHE_TTL_SECONDS)

    # ── Public API ─────────────────────────────────────────────────────
    def evaluate(
        self,
        decision: Any,
        context: Any,
        statistics: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
    ) -> StrategyEvaluationResult:
        """
        Synchronous deterministic evaluation.  Returns a
        `StrategyEvaluationResult` with the winner and full ranked
        candidate list.

        Cache lookup is best-effort: on hit, the cached result is
        returned without recomputation.
        """
        if statistics is None:
            statistics = {}
        if tenant_id is None:
            tenant_id = getattr(context, "tenant_id", None) or getattr(decision, "tenant_id", "default")

        decision_id = getattr(decision, "id", "unknown")

        # Cache lookup
        if self._cache_enabled:
            cached = self._cache.get(tenant_id, decision_id, context)
            if cached is not None:
                logger.debug("strategy cache hit tenant=%s decision=%s", tenant_id, decision_id)
                return cached

        started = time.monotonic()

        candidates = self._builder.build_candidates(decision, context, statistics)
        ranked = self._ranking.rank(candidates)
        winner = self._selector.select(ranked)

        duration_ms = int((time.monotonic() - started) * 1000)

        result = StrategyEvaluationResult(
            tenant_id=tenant_id,
            decision_id=decision_id,
            candidates=ranked,
            winner=winner,
            ranking_stable=True,
            evaluation_duration_ms=duration_ms,
        )

        if self._cache_enabled and winner is not None:
            self._cache.put(tenant_id, decision_id, context, result)

        logger.info(
            "strategy evaluation tenant=%s decision=%s winner=%s candidates=%d valid=%d duration_ms=%d",
            tenant_id, decision_id,
            winner.candidate_type.value if winner else "NONE",
            len(ranked),
            sum(1 for c in ranked if c.is_valid),
            duration_ms,
        )
        return result

    # ── Persistence helpers ────────────────────────────────────────────
    async def persist_winner(
        self,
        result: StrategyEvaluationResult,
        db_session: Any,
    ) -> DecisionStrategy:
        """
        Convert the in-memory winning candidate into ORM rows.
        Called by the pipeline (which owns the transaction).

        Returns the persisted DecisionStrategy (with .id populated).
        """
        if result.winner is None:
            raise ValueError("Cannot persist a StrategyEvaluationResult with no winner")

        win = result.winner
        decision = win.decision  # attached during build

        # Persist the DecisionStrategy row first (so FK targets exist)
        strategy_row = DecisionStrategy(
            tenant_id=win.tenant_id,
            decision_id=result.decision_id,
            plan_id=getattr(decision, "plan_id", None) if decision else None,
            strategy_type=win.candidate_type,
            state=StrategyState.SELECTED,
            priority=win.priority,
            confidence=win.confidence,
            risk_score=win.risk_score,
            feasibility_score=win.feasibility_score,
            composite_score=win.composite_score,
            business_justification=win.business_justification,
            technical_justification=win.technical_justification,
            selection_reason=win.selection_reason,
            expected_downtime_min=win.expected_downtime_min,
            requires_human_approval=win.requires_human_approval,
            is_reversible=win.is_reversible,
            correlation_id=win.correlation_id,
            trace_id=win.trace_id,
        )
        db_session.add(strategy_row)
        await db_session.flush()  # populate id

        # Persist the winning StrategyCandidate row
        winning_candidate = StrategyCandidate(
            tenant_id=win.tenant_id,
            strategy_id=strategy_row.id,
            candidate_type=win.candidate_type,
            feasibility_score=win.feasibility_score,
            composite_score=win.composite_score,
            rank=win.rank if win.rank is not None else 1,
            is_valid=win.is_valid,
            rejected_reason=str(win.rejection_reason) if win.rejection_reason else None,
            correlation_id=win.correlation_id,
            trace_id=win.trace_id,
        )
        db_session.add(winning_candidate)
        await db_session.flush()  # populate id

        # Persist constraints (accept both dataclass objects and dicts)
        for c in win.constraints:
            if isinstance(c, dict):
                c_type   = c.get("type", c.get("constraint_type", "UNKNOWN"))
                c_met    = c.get("is_met", c.get("is_met", True))
                c_detail = c.get("details") or c.get("description") or ""
            else:
                c_type   = getattr(c, "type", "UNKNOWN")
                c_met    = getattr(c, "is_met", True)
                c_detail = getattr(c, "description", "") or ""
            db_session.add(StrategyConstraint(
                tenant_id=win.tenant_id,
                strategy_id=strategy_row.id,
                constraint_type=str(c_type)[:100],
                is_met=bool(c_met),
                details=str(c_detail)[:1000],
                correlation_id=win.correlation_id,
                trace_id=win.trace_id,
            ))

        # Persist requirements (accept both dataclass objects and dicts)
        for r in win.requirements:
            if isinstance(r, dict):
                r_type = r.get("type", r.get("requirement_type", "UNKNOWN"))
                r_val  = r.get("value") or r.get("description") or ""
            else:
                r_type = getattr(r, "type", "UNKNOWN")
                r_val  = getattr(r, "description", "") or ""
            db_session.add(StrategyRequirement(
                tenant_id=win.tenant_id,
                strategy_id=strategy_row.id,
                requirement_type=str(r_type)[:100],
                value=str(r_val)[:2000],
                correlation_id=win.correlation_id,
                trace_id=win.trace_id,
            ))

        # Persist reasons
        for r in win.reasons:
            db_session.add(StrategyReason(
                tenant_id=win.tenant_id,
                strategy_id=strategy_row.id,
                reason_code=r.reason_code,
                description=r.description,
                category="TECHNICAL",
                correlation_id=win.correlation_id,
                trace_id=win.trace_id,
            ))

        # Persist score breakdown (FK to winning_candidate.id)
        for s in win.score_breakdown:
            db_session.add(StrategyScore(
                tenant_id=win.tenant_id,
                candidate_id=winning_candidate.id,
                dimension=s.dimension,
                value=s.value,
                weight=s.weight,
                contribution=s.contribution,
                correlation_id=win.correlation_id,
                trace_id=win.trace_id,
            ))

        # Persist metadata (key/value, only for scalar values)
        ctx_meta = getattr(context, "raw_data", None) if 'context' in locals() else None  # noqa: F821
        if isinstance(ctx_meta, dict):
            for k, v in ctx_meta.items():
                if isinstance(v, (str, int, float, bool)):
                    db_session.add(StrategyMetadata(
                        tenant_id=win.tenant_id,
                        strategy_id=strategy_row.id,
                        key=str(k)[:128],
                        value=str(v)[:2000],
                        correlation_id=win.correlation_id,
                        trace_id=win.trace_id,
                    ))

        await db_session.flush()
        return strategy_row

    async def persist_alternatives(
        self,
        result: StrategyEvaluationResult,
        winning_strategy_id: str,
        db_session: Any,
    ) -> List:
        """
        Persist non-winning candidates as StrategyCandidate rows
        (audit trail of what was considered but not chosen).
        """
        rows = []
        for c in result.candidates:
            if c is result.winner:
                continue
            row = StrategyCandidate(
                tenant_id=c.tenant_id or result.tenant_id,
                strategy_id=winning_strategy_id,
                candidate_type=c.candidate_type,
                rank=c.rank,
                is_valid=c.is_valid,
                rejected_reason=str(c.rejection_reason) if c.rejection_reason else None,
                composite_score=c.composite_score,
                feasibility_score=c.feasibility_score,
                correlation_id=c.correlation_id,
                trace_id=c.trace_id,
            )
            db_session.add(row)
            rows.append(row)
        await db_session.flush()
        return rows