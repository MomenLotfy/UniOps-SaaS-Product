"""
Approval Engine.

Deterministic orchestrator.  Takes a Decision + aggregated
`ApprovalContext`, asks the policy engine for a verdict, returns an
`ApprovalEvaluationResult` (winner + ranked list + diagnostics).

Pure-function entry point: `evaluate(...)`.  Persistence is the
caller's responsibility — see `ApprovalEvaluationPipeline`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..constants import ApprovalState
from ..models.approval import (
    ApprovalAudit,
    ApprovalConstraint,
    ApprovalDecision,
    ApprovalEvidence,
    ApprovalHistory,
    ApprovalMetadata,
    ApprovalReason,
    ApprovalRequest,
    ApprovalRequirement,
)
from .approval_cache import ApprovalCache
from .approval_context_builder import ApprovalContextBuilder
from .approval_interfaces import (
    ApprovalCandidateData,
    ApprovalEvaluationResult,
)
from .approval_policy_engine import ApprovalPolicyEngine

logger = logging.getLogger(__name__)


class ApprovalEngine:
    """
    Deterministic approval evaluator.

    Composition root holds:
      - context builder
      - policy engine (registry + resolver + scoring + factory)
      - cache (TTL-keyed by tenant + decision + context hash)
    """

    def __init__(
        self,
        policy_engine: Optional[ApprovalPolicyEngine] = None,
        context_builder: Optional[ApprovalContextBuilder] = None,
        cache: Optional[ApprovalCache] = None,
        cache_enabled: bool = True,
    ) -> None:
        self._policy_engine = policy_engine or ApprovalPolicyEngine()
        self._context_builder = context_builder or ApprovalContextBuilder()
        self._cache_enabled = cache_enabled
        self._cache = cache or ApprovalCache()

    # ── Public API ─────────────────────────────────────────────────
    def evaluate(
        self,
        decision: Any,
        strategy: Any = None,
        *,
        context: Any = None,
        statistics: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
        raw_data: Optional[Dict] = None,
    ) -> ApprovalEvaluationResult:
        """Synchronous deterministic evaluation."""
        if statistics is None:
            statistics = {}

        # Either a pre-built context is supplied (used for cache lookups
        # + reuse across calls), or one is assembled here.
        if context is None:
            context = self._context_builder.build(
                decision=decision,
                strategy=strategy,
                tenant_id=tenant_id,
                raw_data=raw_data,
            )
        if tenant_id is None:
            tenant_id = context.tenant_id
        decision_id = getattr(decision, "id", "unknown")

        # Cache lookup
        if self._cache_enabled:
            cached = self._cache.get(tenant_id, decision_id, context)
            if cached is not None:
                logger.debug(
                    "approval cache hit tenant=%s decision=%s", tenant_id, decision_id,
                )
                return cached

        started = time.monotonic()

        approval_type = self._context_builder.derive_approval_type(decision, strategy)
        candidate = self._policy_engine.build_candidate(
            decision=decision,
            context=context,
            approval_type=approval_type,
        )

        duration_ms = int((time.monotonic() - started) * 1000)
        result = ApprovalEvaluationResult(
            tenant_id=tenant_id,
            decision_id=decision_id,
            strategy_id=getattr(strategy, "id", None),
            candidate=candidate,
            candidates=[candidate],
            ranking_stable=True,
            evaluation_duration_ms=duration_ms,
        )

        if self._cache_enabled and candidate is not None:
            self._cache.put(tenant_id, decision_id, context, result)

        logger.info(
            "approval evaluation tenant=%s decision=%s strategy=%s requires=%s auto=%s/%s duration_ms=%d",
            tenant_id, decision_id,
            getattr(strategy, "id", None),
            candidate.requires_approval if candidate else None,
            candidate.auto_approve if candidate else None,
            candidate.auto_reject if candidate else None,
            duration_ms,
        )
        return result

    # ── Persistence helpers ────────────────────────────────────────
    async def persist_winner(
        self,
        result: ApprovalEvaluationResult,
        db_session: Any,
    ) -> ApprovalRequest:
        """Convert the winning candidate into ORM rows.  Called by the pipeline."""
        if result.candidate is None:
            raise ValueError("Cannot persist an ApprovalEvaluationResult with no candidate")
        cand = result.candidate

        # Persist the ApprovalRequest row first (so FK targets exist)
        row = ApprovalRequest(
            tenant_id=cand.tenant_id,
            decision_id=result.decision_id,
            strategy_id=result.strategy_id,
            approval_state=self._initial_state(cand),
            approval_type=cand.approval_type,
            requirement_mode=cand.requirement_mode,
            summary=cand.business_justification or cand.technical_justification or None,
            business_justification=cand.business_justification,
            technical_justification=cand.technical_justification,
            risk_score=cand.risk_score,
            criticality_score=cand.criticality_score,
            composite_score=cand.composite_score,
            confidence=cand.confidence,
            is_emergency=cand.is_emergency,
            auto_decided=cand.auto_approve or cand.auto_reject,
            blocked=cand.auto_reject,
            blocked_reason=("Automatic rejection" if cand.auto_reject else None),
            correlation_id=cand.correlation_id,
            trace_id=cand.trace_id,
        )
        db_session.add(row)
        await db_session.flush()

        # Requirements
        for req in cand.requirements:
            db_session.add(ApprovalRequirement(
                tenant_id=cand.tenant_id,
                request_id=row.id,
                required_role=req.role.value,
                sequence_order=req.sequence_order,
                is_mandatory=req.is_mandatory,
                description=req.description,
                correlation_id=cand.correlation_id,
                trace_id=cand.trace_id,
            ))

        # Constraints
        for c_type, is_met, details in cand.constraints:
            db_session.add(ApprovalConstraint(
                tenant_id=cand.tenant_id,
                request_id=row.id,
                constraint_type=str(c_type)[:100],
                is_met=bool(is_met),
                details=str(details)[:2000],
                correlation_id=cand.correlation_id,
                trace_id=cand.trace_id,
            ))

        # Evidence
        for ev_type, ev_value in cand.evidence:
            db_session.add(ApprovalEvidence(
                tenant_id=cand.tenant_id,
                request_id=row.id,
                evidence_type=str(ev_type)[:100],
                evidence_value=str(ev_value)[:4000],
                correlation_id=cand.correlation_id,
                trace_id=cand.trace_id,
            ))

        # Reasons
        for code, desc in cand.reasons:
            db_session.add(ApprovalReason(
                tenant_id=cand.tenant_id,
                request_id=row.id,
                reason_code=str(code)[:100],
                description=str(desc)[:2000],
                category="POLICY",
                correlation_id=cand.correlation_id,
                trace_id=cand.trace_id,
            ))

        # Metadata (key/value, scalar values only)
        if isinstance(cand.evidence, list):
            for k, v in (cand.evidence or []):
                if isinstance(v, (str, int, float, bool)):
                    db_session.add(ApprovalMetadata(
                        tenant_id=cand.tenant_id,
                        request_id=row.id,
                        key=str(k)[:128],
                        value=str(v)[:4000],
                        correlation_id=cand.correlation_id,
                        trace_id=cand.trace_id,
                    ))

        # Seed a CREATED history entry so the audit chain starts here
        db_session.add(ApprovalHistory(
            tenant_id=cand.tenant_id,
            request_id=row.id,
            from_state=None,
            to_state=row.approval_state,
            changed_by="system",
            change_reason="Initial state from policy evaluation",
            correlation_id=cand.correlation_id,
            trace_id=cand.trace_id,
        ))

        # Append-only audit ledger entry
        db_session.add(ApprovalAudit(
            tenant_id=cand.tenant_id,
            request_id=row.id,
            event_type="APPROVAL_CREATED",
            actor_id="system",
            actor_role="SYSTEM",
            details={
                "approval_type":   cand.approval_type.value,
                "requirement_mode": cand.requirement_mode.value,
                "requires_approval": cand.requires_approval,
                "auto_approve":    cand.auto_approve,
                "auto_reject":     cand.auto_reject,
                "composite_score": cand.composite_score,
            },
            occurred_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            correlation_id=cand.correlation_id,
            trace_id=cand.trace_id,
        ))

        await db_session.flush()
        return row

    @staticmethod
    def _initial_state(candidate: ApprovalCandidateData) -> ApprovalState:
        if candidate.auto_reject:
            return ApprovalState.REJECTED
        if candidate.auto_approve or not candidate.requires_approval:
            return ApprovalState.APPROVED
        if len(candidate.requirements) > 1:
            return ApprovalState.PARTIALLY_APPROVED
        return ApprovalState.WAITING_APPROVAL


__all__ = ["ApprovalEngine"]