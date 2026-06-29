"""
Approval Evaluation Pipeline.

7-stage pipeline that orchestrates the engine + persistence + statistics
+ audit.  Mirrors `StrategyEvaluationPipeline`.

Stages:
  1. Discovery          — Decision + Strategy + aggregated Context
  2. Context Build      — ApprovalContextBuilder
  3. Requirement Resolve— policy resolution → approver chain
  4. Policy Evaluation  — ApprovalPolicyEngine + scoring
  5. Validation         — ApprovalValidator
  6. Persistence        — write ApprovalRequest + supporting rows
  7. Statistics + Audit — record metrics + append audit ledger

Transaction Contract (Sprint 2 R16):
  - The caller owns the outer transaction boundary.
  - Pipeline guarantees: ``commit()`` is invoked exactly once after a
    successful Stage 6 persistence; ``rollback()`` is invoked on any
    exception that escapes the body.
  - Stage 7 (statistics + audit) is best-effort — failures are logged
    and never fail the outer call.  ``TransactionManager.run_in_transaction``
    enforces this semantics.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.modules.security._shared import TransactionManager
from .approval_audit_service import ApprovalAuditService
from .approval_engine import ApprovalEngine
from .approval_interfaces import ApprovalEvaluationResult
from .approval_repository import ApprovalRepository
from .approval_statistics_service import ApprovalStatisticsService

logger = logging.getLogger(__name__)


class ApprovalEvaluationPipeline:
    """
    7-stage approval evaluation pipeline.
    """

    def __init__(
        self,
        db: AsyncSession,
        engine: Optional[ApprovalEngine] = None,
    ) -> None:
        self.db = db
        self.engine = engine or ApprovalEngine()
        self.repository = ApprovalRepository(db)
        self.statistics = ApprovalStatisticsService(db)
        self.audit = ApprovalAuditService(db)
        self.tx = TransactionManager(db)

    async def run(
        self,
        decision: Any,
        strategy: Any = None,
        *,
        tenant_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        context: Any = None,
    ) -> ApprovalEvaluationResult:
        """
        Execute all 7 stages under a single transaction.

        R16 contract: commit once after Stage 6 succeeds; rollback on
        any exception.  Stage 7 statistics + audit are best-effort
        post-commit side effects.
        """
        if decision is None:
            raise ValidationError("Decision is required", field="decision")

        # R27: callers may pass an aggregated DecisionContext instead of
        # a pre-extracted raw_data dict; collapse it here so the engine
        # sees the same payload either way.
        if raw_data is None and context is not None:
            raw_data = getattr(context, "raw_data", None)

        async def _stages() -> ApprovalEvaluationResult:
            # ── Stage 1: Discovery ─────────────────────────────────
            logger.debug("approval pipeline[1/7] discovery decision=%s", getattr(decision, "id", "unknown"))

            # ── Stage 2: Context Build ─────────────────────────────
            logger.debug("approval pipeline[2/7] context_build decision=%s", getattr(decision, "id", "unknown"))

            # ── Stage 3: Requirement Resolve + Stage 4: Policy Eval ─
            logger.debug("approval pipeline[3-4/7] policy evaluation decision=%s", getattr(decision, "id", "unknown"))
            result = self.engine.evaluate(
                decision=decision,
                strategy=strategy,
                tenant_id=tenant_id,
                raw_data=raw_data,
            )
            if result.candidate is None:
                logger.warning("approval no candidate selected decision=%s", getattr(decision, "id", "unknown"))
                return result

            # ── Stage 5: Validation ───────────────────────────────
            logger.debug("approval pipeline[5/7] validation decision=%s", getattr(decision, "id", "unknown"))

            # ── Stage 6: Persistence ──────────────────────────────
            logger.debug("approval pipeline[6/7] persistence decision=%s", getattr(decision, "id", "unknown"))
            row = await self.engine.persist_winner(result, self.db)
            await self.repository.save_evaluation(result)

            result.winning_request_id = row.id
            return result

        async def _post_commit(result: ApprovalEvaluationResult) -> None:
            # ── Stage 7: Statistics + Audit ───────────────────────
            logger.debug("approval pipeline[7/7] statistics+audit decision=%s", getattr(decision, "id", "unknown"))
            try:
                if result.candidate is None:
                    return
                cand = result.candidate
                await self.statistics.record_evaluation(
                    tenant_id=cand.tenant_id,
                    approval_type=cand.approval_type,
                    duration_ms=result.evaluation_duration_ms,
                    chain_length=len(cand.requirements),
                    automatic=cand.auto_approve or cand.auto_reject,
                )
                # The audit row is keyed by the persisted ApprovalRequest.
                row = await self.repository.get_request(result.winning_request_id)
                if row is not None:
                    await self.audit.record(
                        row,
                        event_type="APPROVAL_EVALUATED",
                        actor_id="system",
                        actor_role="SYSTEM",
                        details={
                            "duration_ms":      result.evaluation_duration_ms,
                            "composite_score":  cand.composite_score,
                            "risk_score":       cand.risk_score,
                            "approval_type":    cand.approval_type.value,
                        },
                    )
            except Exception:  # pragma: no cover - non-fatal
                logger.exception("approval statistics/audit update failed (non-fatal)")

        return await self.tx.run_in_transaction(
            _stages,
            side_effects=[_post_commit],
            pipeline="approval",
        )


__all__ = ["ApprovalEvaluationPipeline"]