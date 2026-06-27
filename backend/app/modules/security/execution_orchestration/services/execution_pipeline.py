"""
Execution Orchestration Pipeline.

7-stage pipeline that takes a Decision + Strategy + Approval (the
"winning chain") and produces a fully populated `ExecutionPackage`.

Stages:
  1. Preparation           — snapshot the upstream inputs
  2. Readiness Validation  — run the 12 readiness checks
  3. Dependency Resolution — resolve every dependency reference
  4. Constraint Validation — verify the 12 hard constraints
  5. Package Build         — persist ExecutionPackage + detail rows
  6. Statistics Update     — record per-tenant metrics
  7. Audit                 — append ledger entries

Mirrors `decision_approval/services/approval_pipeline.py`.

All stages run inside a single transaction owned by the caller.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import (
    ExecutionAuditEvent,
    ExecutionPackageState,
    ReadinessOutcome,
    VALID_EXECUTION_TRANSITIONS,
)
from ..models.execution import ExecutionPackage
from .execution_audit_service import ExecutionAuditService
from .execution_cache import ExecutionCache
from .execution_constraint_validator import ExecutionConstraintValidator
from .execution_dependency_resolver import ExecutionDependencyResolver
from .execution_interfaces import (
    ExecutionCandidateData,
    ExecutionEvaluationResult,
    ExecutionPreparationSnapshot,
    IExecutionRepository,
)
from .execution_lifecycle_manager import ExecutionLifecycleManager
from .execution_package_builder import ExecutionPackageBuilder
from .execution_package_factory import ExecutionPackageFactory
from .execution_package_validator import ExecutionPackageValidator
from .execution_preparation_service import ExecutionPreparationService
from .execution_readiness_engine import (
    ExecutionReadinessEngine,
    bootstrap_default_readiness_checks,
)
from .execution_repository import ExecutionRepository
from .execution_statistics_service import ExecutionStatisticsService
from .execution_version_manager import ExecutionVersionManager

logger = logging.getLogger(__name__)


class ExecutionPipeline:
    """Composition root for the execution orchestration flow."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        preparation_service: Optional[ExecutionPreparationService] = None,
        readiness_engine: Optional[ExecutionReadinessEngine] = None,
        dependency_resolver: Optional[ExecutionDependencyResolver] = None,
        constraint_validator: Optional[ExecutionConstraintValidator] = None,
        package_validator: Optional[ExecutionPackageValidator] = None,
        package_factory: Optional[ExecutionPackageFactory] = None,
        package_builder: Optional[ExecutionPackageBuilder] = None,
        repository: Optional[IExecutionRepository] = None,
        lifecycle_manager: Optional[ExecutionLifecycleManager] = None,
        version_manager: Optional[ExecutionVersionManager] = None,
        statistics_service: Optional[ExecutionStatisticsService] = None,
        audit_service: Optional[ExecutionAuditService] = None,
        cache: Optional[ExecutionCache] = None,
    ) -> None:
        self.db = db
        self.preparation_service = preparation_service or ExecutionPreparationService()
        self.readiness_engine = readiness_engine or bootstrap_default_readiness_checks(
            ExecutionReadinessEngine()
        )
        self.dependency_resolver = dependency_resolver or ExecutionDependencyResolver()
        self.constraint_validator = constraint_validator or ExecutionConstraintValidator()
        self.package_validator = package_validator or ExecutionPackageValidator()
        self.package_factory = package_factory or ExecutionPackageFactory()
        self.package_builder = package_builder or ExecutionPackageBuilder(db)
        self.repository = repository or ExecutionRepository(db)
        self.lifecycle_manager = lifecycle_manager or ExecutionLifecycleManager(db)
        self.version_manager = version_manager or ExecutionVersionManager(db)
        self.statistics_service = statistics_service or ExecutionStatisticsService(db)
        self.audit_service = audit_service or ExecutionAuditService(db)
        self.cache = cache or ExecutionCache()

    # ── Public entry ──────────────────────────────────────────────
    async def run(
        self,
        decision: Any,
        strategy: Any = None,
        approval: Any = None,
        *,
        tenant_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[List] = None,
        requirements: Optional[List] = None,
        summary: Optional[str] = None,
        actor_id: str = "system",
    ) -> ExecutionEvaluationResult:
        """
        Execute all 7 stages.  Always returns an `ExecutionEvaluationResult`
        even when the candidate is rejected — the result carries the
        rejection reason so the API can surface it.
        """
        if decision is None:
            raise ValueError("Decision is required")

        overall_started = time.monotonic()

        # ── Stage 1: Preparation ──────────────────────────────────
        logger.debug("execution pipeline[1/7] preparation decision=%s", getattr(decision, "id", "?"))
        snapshot: ExecutionPreparationSnapshot = self.preparation_service.prepare(
            decision=decision,
            strategy=strategy,
            approval=approval,
            tenant_id=tenant_id,
            raw_data=raw_data,
        )

        # Cache lookup — only if the upstream is buildable
        if snapshot.is_complete:
            cached = self.cache.get(snapshot.tenant_id, snapshot.decision_id, snapshot)
            if cached is not None and cached.package_id:
                logger.debug(
                    "execution cache hit tenant=%s decision=%s",
                    snapshot.tenant_id, snapshot.decision_id,
                )
                return cached

        candidate: ExecutionCandidateData = self.package_factory.build_candidate(
            snapshot,
            metadata=metadata,
            requirements=requirements,
            summary=summary,
        )
        if not candidate.is_valid:
            return self._build_rejection_result(candidate, snapshot, overall_started)

        # Build a context object the readiness + dependency + constraint
        # stages can read.  This mirrors the way `ApprovalContext` is
        # assembled in the approval engine.
        context = self._build_context(snapshot, decision, strategy, approval, raw_data)

        # ── Stage 2: Readiness Validation ────────────────────────
        logger.debug("execution pipeline[2/7] readiness_validation decision=%s", candidate.decision_id)
        readiness_started = time.monotonic()
        self.readiness_engine.run(candidate, context)
        readiness_ms = (time.monotonic() - readiness_started) * 1000.0
        candidate.readiness_ms = readiness_ms

        # ── Stage 3: Dependency Resolution ───────────────────────
        logger.debug("execution pipeline[3/7] dependency_resolution decision=%s", candidate.decision_id)
        await self.dependency_resolver.resolve(candidate, context)

        # ── Stage 4: Constraint Validation ───────────────────────
        logger.debug("execution pipeline[4/7] constraint_validation decision=%s", candidate.decision_id)
        self.constraint_validator.validate(candidate, context)

        # ── Pre-flight validation ─────────────────────────────────
        errors = self.package_validator.validate(candidate)
        if errors or candidate.readiness_failed > 0:
            candidate.is_valid = False
            candidate.rejection_reason = candidate.rejection_reason or errors[0] if errors else "READINESS_FAILED"
            return await self._persist_rejected(
                candidate, snapshot, context, overall_started, actor_id,
            )

        # ── Stage 5: Package Build ────────────────────────────────
        logger.debug("execution pipeline[5/7] package_build decision=%s", candidate.decision_id)
        package = await self.package_builder.build(
            candidate, snapshot, target_state=ExecutionPackageState.BUILT, actor_id=actor_id,
        )

        # Drive the package through CREATED → READINESS_* → BUILT → READY.
        await self._drive_package(package, candidate, context, actor_id)

        # ── Stage 6: Statistics Update ───────────────────────────
        logger.debug("execution pipeline[6/7] statistics_update package=%s", package.id)
        try:
            duration_ms = (time.monotonic() - overall_started) * 1000.0
            candidate.evaluation_duration_ms = int(duration_ms)
            await self.statistics_service.record(
                package,
                duration_ms=duration_ms,
                size_kb=package.package_size_kb,
                rejected=package.is_rejected,
                ready=package.is_ready,
            )
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("execution statistics update failed (non-fatal)")

        # ── Stage 7: Audit ────────────────────────────────────────
        logger.debug("execution pipeline[7/7] audit package=%s", package.id)
        try:
            await self.audit_service.record(
                package,
                event_type=(
                    ExecutionAuditEvent.PACKAGE_READY.value
                    if package.is_ready
                    else ExecutionAuditEvent.PACKAGE_PERSISTED.value
                ),
                actor_id=actor_id,
                actor_role="SYSTEM",
                details={
                    "duration_ms":    candidate.evaluation_duration_ms,
                    "dependencies":   len(candidate.dependencies),
                    "constraints":    len(candidate.constraints),
                    "metadata_count": len(candidate.metadata),
                    "size_kb":        package.package_size_kb,
                    "package_state":  package.package_state.value,
                },
            )
        except Exception:  # pragma: no cover - non-fatal
            logger.exception("execution audit update failed (non-fatal)")

        result = ExecutionEvaluationResult(
            tenant_id=candidate.tenant_id,
            decision_id=candidate.decision_id,
            candidate=candidate,
            package_id=package.id,
            final_state=package.package_state,
            ranking_stable=True,
            evaluation_duration_ms=candidate.evaluation_duration_ms,
            rejection_reason=None,
        )

        # Cache only READY packages — partial states shouldn't be served
        # from cache.
        if package.is_ready and snapshot.is_complete:
            self.cache.put(snapshot.tenant_id, snapshot.decision_id, snapshot, result)

        return result

    # ── Internal helpers ──────────────────────────────────────────
    async def _drive_package(
        self,
        package: ExecutionPackage,
        candidate: ExecutionCandidateData,
        context: Any,
        actor_id: str,
    ) -> None:
        """Apply the legal CREATED → … → READY transitions in order."""
        all_met = all(c.is_met for c in candidate.constraints)
        ordered_states = [
            ExecutionPackageState.READINESS_VALIDATING,
            ExecutionPackageState.READINESS_PASSED if all_met else ExecutionPackageState.READINESS_FAILED,
        ]
        if all_met:
            ordered_states.extend([
                ExecutionPackageState.BUILDING,
                ExecutionPackageState.BUILT,
                ExecutionPackageState.READY,
            ])
            package.is_ready = True
            package.is_immutable = True
        else:
            package.is_rejected = True
            candidate.is_valid = False
            ordered_states.append(ExecutionPackageState.REJECTED)

        for to_state in ordered_states:
            if not VALID_EXECUTION_TRANSITIONS.get(package.package_state, []):
                break
            if to_state not in VALID_EXECUTION_TRANSITIONS.get(package.package_state, []):
                # Skip illegal intermediate steps but allow the natural
                # progression by collapsing the path.
                continue
            await self.lifecycle_manager.transition(
                package.id,
                to_state,
                changed_by=actor_id,
                reason=f"Automated progression by execution pipeline",
            )
            package.package_state = to_state

    def _build_context(
        self,
        snapshot: ExecutionPreparationSnapshot,
        decision: Any,
        strategy: Any,
        approval: Any,
        raw_data: Optional[Dict[str, Any]],
    ) -> Any:
        """
        Build a simple namespace object the readiness / dependency /
        constraint stages can read.  Mirrors `ApprovalContext`.
        """
        class _Ctx:
            pass

        ctx = _Ctx()
        ctx.tenant_id = snapshot.tenant_id
        ctx.decision_id = snapshot.decision_id
        ctx.strategy_id = snapshot.strategy_id
        ctx.approval_id = snapshot.approval_id
        ctx.decision_snapshot = snapshot.decision_snapshot or {}
        ctx.strategy_snapshot = snapshot.strategy_snapshot or {}
        ctx.approval_snapshot = snapshot.approval_snapshot or {}
        ctx.context_snapshot = dict(snapshot.context_snapshot or {})

        # Pass through the upstream object's commonly-needed attrs.
        ctx.decision_state = (
            snapshot.decision_snapshot.get("decision_state")
            if isinstance(snapshot.decision_snapshot, dict) else None
        )
        ctx.strategy_state = (
            snapshot.strategy_snapshot.get("strategy_state")
            if isinstance(snapshot.strategy_snapshot, dict) else None
        )
        ctx.approval_state = (
            snapshot.approval_snapshot.get("approval_state")
            if isinstance(snapshot.approval_snapshot, dict) else None
        )

        # Optional inputs pulled from raw_data
        if isinstance(raw_data, dict):
            for k in (
                "repository_id", "asset_id", "cve_id", "finding_id",
                "policy_id", "policy_compliance",
                "environment", "target_environment",
                "execution_window_open",
            ):
                if k in raw_data:
                    setattr(ctx, k, raw_data[k])

        return ctx

    def _build_rejection_result(
        self,
        candidate: ExecutionCandidateData,
        snapshot: ExecutionPreparationSnapshot,
        started: float,
    ) -> ExecutionEvaluationResult:
        return ExecutionEvaluationResult(
            tenant_id=candidate.tenant_id,
            decision_id=candidate.decision_id,
            candidate=candidate,
            package_id=None,
            final_state=ExecutionPackageState.REJECTED,
            ranking_stable=True,
            evaluation_duration_ms=int((time.monotonic() - started) * 1000.0),
            rejection_reason=candidate.rejection_reason,
        )

    async def _persist_rejected(
        self,
        candidate: ExecutionCandidateData,
        snapshot: ExecutionPreparationSnapshot,
        context: Any,
        started: float,
        actor_id: str,
    ) -> ExecutionEvaluationResult:
        """Persist a minimal rejected package so the rejection is auditable."""
        try:
            package = await self.package_builder.build(
                candidate, snapshot, target_state=ExecutionPackageState.REJECTED, actor_id=actor_id,
            )
            package.is_rejected = True
            package.is_immutable = True
            await self.lifecycle_manager.transition(
                package.id,
                ExecutionPackageState.READINESS_VALIDATING,
                changed_by=actor_id,
                reason="Pre-flight rejection",
            )
            await self.lifecycle_manager.transition(
                package.id,
                ExecutionPackageState.READINESS_FAILED,
                changed_by=actor_id,
                reason=candidate.rejection_reason or "READINESS_FAILED",
            )
            await self.lifecycle_manager.transition(
                package.id,
                ExecutionPackageState.REJECTED,
                changed_by=actor_id,
                reason=candidate.rejection_reason or "READINESS_FAILED",
            )
            try:
                await self.statistics_service.record(
                    package,
                    duration_ms=(time.monotonic() - started) * 1000.0,
                    size_kb=package.package_size_kb,
                    rejected=True,
                    ready=False,
                )
            except Exception:  # pragma: no cover
                logger.exception("execution statistics update failed on rejection (non-fatal)")
            try:
                await self.audit_service.record(
                    package,
                    event_type=ExecutionAuditEvent.PACKAGE_REJECTED.value,
                    actor_id=actor_id,
                    actor_role="SYSTEM",
                    details={
                        "reason": candidate.rejection_reason,
                        "errors": candidate.rejection_details,
                    },
                )
            except Exception:  # pragma: no cover
                logger.exception("execution audit update failed on rejection (non-fatal)")

            return ExecutionEvaluationResult(
                tenant_id=candidate.tenant_id,
                decision_id=candidate.decision_id,
                candidate=candidate,
                package_id=package.id,
                final_state=ExecutionPackageState.REJECTED,
                ranking_stable=True,
                evaluation_duration_ms=int((time.monotonic() - started) * 1000.0),
                rejection_reason=candidate.rejection_reason,
            )
        except Exception:  # pragma: no cover
            logger.exception("execution rejection persistence failed (non-fatal)")
            return self._build_rejection_result(candidate, snapshot, started)


__all__ = ["ExecutionPipeline"]