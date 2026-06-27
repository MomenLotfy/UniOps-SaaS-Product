"""
Execution Package Builder.

Converts the in-memory `ExecutionCandidateData` into the canonical
ORM rows that make up an `ExecutionPackage` and all of its
supporting detail tables.

Mirrors `ApprovalEngine.persist_winner(...)` in
`decision_approval/services/approval_engine.py`.

This is the LAST pure transformation before persistence — it does
NOT commit the transaction; the caller owns the boundary.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import (
    ExecutionAuditEvent,
    ExecutionPackageState,
    ReadinessOutcome,
)
from ..models.execution import (
    ExecutionAudit,
    ExecutionConstraint,
    ExecutionDependency,
    ExecutionHistory,
    ExecutionMetadata,
    ExecutionPackage,
    ExecutionPreparation,
    ExecutionReadiness,
    ExecutionRequirement,
    ExecutionSummary,
)
from .execution_interfaces import ExecutionCandidateData, ExecutionPreparationSnapshot

logger = logging.getLogger(__name__)


def _payload_hash(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _estimate_kb(payload: Dict[str, Any]) -> float:
    return round(len(json.dumps(payload, default=str).encode("utf-8")) / 1024.0, 3)


class ExecutionPackageBuilder:
    """Single entry point: candidate → fully-populated ORM rows."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build(
        self,
        candidate: ExecutionCandidateData,
        snapshot: ExecutionPreparationSnapshot,
        *,
        target_state: ExecutionPackageState = ExecutionPackageState.READY,
        actor_id: str = "system",
    ) -> ExecutionPackage:
        if candidate is None:
            raise ValueError("ExecutionCandidateData is required")

        # ── 1. ExecutionPackage (root) ────────────────────────────
        package = ExecutionPackage(
            tenant_id=candidate.tenant_id,
            decision_id=candidate.decision_id,
            strategy_id=candidate.strategy_id,
            approval_id=candidate.approval_id,
            package_state=ExecutionPackageState.CREATED,
            package_version=1,
            is_immutable=False,
            is_ready=False,
            is_rejected=bool(candidate.rejection_reason),
            rejection_reason=(candidate.rejection_reason or "")[:1000] or None,
            decision_version=candidate.decision_version,
            strategy_version=candidate.strategy_version,
            approval_version=candidate.approval_version,
            summary=candidate.summary,
            correlation_id=candidate.correlation_id,
            trace_id=candidate.trace_id,
            dependency_count=len(candidate.dependencies),
            constraint_count=len(candidate.constraints),
            metadata_count=len(candidate.metadata),
        )
        self.db.add(package)
        await self.db.flush()

        # ── 2. ExecutionPreparation (snapshot) ────────────────────
        prep = ExecutionPreparation(
            tenant_id=candidate.tenant_id,
            package_id=package.id,
            decision_id=candidate.decision_id,
            decision_snapshot=snapshot.decision_snapshot or {},
            strategy_snapshot=snapshot.strategy_snapshot or {},
            approval_snapshot=snapshot.approval_snapshot or {},
            context_snapshot=snapshot.context_snapshot or {},
            is_complete=bool(snapshot.is_complete),
            missing_fields=", ".join(snapshot.missing_fields)[:4000] or None,
            correlation_id=candidate.correlation_id,
            trace_id=candidate.trace_id,
        )
        self.db.add(prep)

        # ── 3. ExecutionReadiness (per-factor verdicts) ───────────
        readiness = ExecutionReadiness(
            tenant_id=candidate.tenant_id,
            package_id=package.id,
            outcome=(
                ReadinessOutcome.PASSED
                if candidate.readiness_failed == 0
                else ReadinessOutcome.FAILED
            ),
            factors_total=candidate.readiness_total,
            factors_passed=candidate.readiness_passed,
            factors_warned=candidate.readiness_warned,
            factors_failed=candidate.readiness_failed,
            validation_ms=float(candidate.readiness_ms),
            verdicts=json.dumps(
                [
                    {
                        "factor":    v.factor.value if hasattr(v.factor, "value") else str(v.factor),
                        "outcome":   v.outcome.value if hasattr(v.outcome, "value") else str(v.outcome),
                        "rationale": v.rationale,
                        "details":   v.details,
                        "latency_ms": v.latency_ms,
                    }
                    for v in candidate.readiness_factors
                ],
                default=str,
            )[:8000] or None,
            correlation_id=candidate.correlation_id,
            trace_id=candidate.trace_id,
        )
        self.db.add(readiness)

        # ── 4. ExecutionDependency rows ───────────────────────────
        for dep in candidate.dependencies:
            self.db.add(ExecutionDependency(
                tenant_id=candidate.tenant_id,
                package_id=package.id,
                kind=dep.kind,
                reference=dep.reference[:255],
                display_name=(dep.display_name or "")[:500] or None,
                is_resolved=bool(dep.is_resolved),
                resolution_ms=float(dep.resolution_ms),
                notes=(dep.notes or "")[:2000] or None,
                correlation_id=candidate.correlation_id,
                trace_id=candidate.trace_id,
            ))

        # ── 5. ExecutionConstraint rows ───────────────────────────
        for c in candidate.constraints:
            self.db.add(ExecutionConstraint(
                tenant_id=candidate.tenant_id,
                package_id=package.id,
                constraint_type=c.constraint_type,
                is_met=bool(c.is_met),
                severity=(c.severity or "HARD")[:20],
                details=(c.details or "")[:2000] or None,
                correlation_id=candidate.correlation_id,
                trace_id=candidate.trace_id,
            ))

        # ── 6. ExecutionRequirement rows ──────────────────────────
        for r in candidate.requirements:
            self.db.add(ExecutionRequirement(
                tenant_id=candidate.tenant_id,
                package_id=package.id,
                requirement_type=r.requirement_type[:100],
                value=(r.value or "")[:2000] or None,
                is_mandatory=bool(r.is_mandatory),
                description=(r.description or "")[:2000] or None,
                correlation_id=candidate.correlation_id,
                trace_id=candidate.trace_id,
            ))

        # ── 7. ExecutionMetadata rows ─────────────────────────────
        for k, v in candidate.metadata:
            self.db.add(ExecutionMetadata(
                tenant_id=candidate.tenant_id,
                package_id=package.id,
                key=str(k)[:128],
                value=str(v)[:4000],
                correlation_id=candidate.correlation_id,
                trace_id=candidate.trace_id,
            ))

        # ── 8. Payload hash + size ────────────────────────────────
        payload = self._serialize_candidate_for_hash(candidate)
        package.payload_hash = _payload_hash(payload)
        package.package_size_kb = _estimate_kb(payload)
        candidate.payload_hash = package.payload_hash
        candidate.package_size_kb = package.package_size_kb

        # ── 9. Initial history row ────────────────────────────────
        self.db.add(ExecutionHistory(
            tenant_id=candidate.tenant_id,
            package_id=package.id,
            from_state=None,
            to_state=ExecutionPackageState.CREATED,
            changed_by=actor_id,
            change_reason="Package created from upstream decision + strategy + approval",
            changed_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            correlation_id=candidate.correlation_id,
            trace_id=candidate.trace_id,
        ))

        # ── 10. Seed audit ledger ─────────────────────────────────
        self.db.add(ExecutionAudit(
            tenant_id=candidate.tenant_id,
            package_id=package.id,
            event_type=ExecutionAuditEvent.PACKAGE_CREATED.value,
            actor_id=actor_id,
            actor_role="SYSTEM",
            details={
                "decision_id": candidate.decision_id,
                "strategy_id": candidate.strategy_id,
                "approval_id": candidate.approval_id,
                "is_valid":    candidate.is_valid,
                "rejection_reason": candidate.rejection_reason,
            },
            occurred_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            correlation_id=candidate.correlation_id,
            trace_id=candidate.trace_id,
        ))

        # ── 11. Denormalised summary ──────────────────────────────
        constraint_passed = sum(1 for c in candidate.constraints if c.is_met)
        constraint_failed = sum(1 for c in candidate.constraints if not c.is_met)
        self.db.add(ExecutionSummary(
            tenant_id=candidate.tenant_id,
            package_id=package.id,
            readiness_status=readiness.outcome.value,
            validation_results={
                "total":  candidate.readiness_total,
                "passed": candidate.readiness_passed,
                "warned": candidate.readiness_warned,
                "failed": candidate.readiness_failed,
            },
            selected_strategy=str(candidate.strategy_id) if candidate.strategy_id else None,
            approval_status="UNKNOWN",  # populated by pipeline from the snapshot
            dependency_count=len(candidate.dependencies),
            constraint_passed=constraint_passed,
            constraint_failed=constraint_failed,
            package_metadata={k: v for (k, v) in candidate.metadata},
            package_timeline=[],
            correlation_id=candidate.correlation_id,
            trace_id=candidate.trace_id,
        ))

        await self.db.flush()
        logger.info(
            "execution package built tenant=%s decision=%s id=%s deps=%d cons=%d",
            candidate.tenant_id, candidate.decision_id, package.id,
            len(candidate.dependencies), len(candidate.constraints),
        )
        return package

    # ── helpers ───────────────────────────────────────────────────
    @staticmethod
    def _serialize_candidate_for_hash(candidate: ExecutionCandidateData) -> Dict[str, Any]:
        return {
            "tenant_id":      candidate.tenant_id,
            "decision_id":    candidate.decision_id,
            "strategy_id":    candidate.strategy_id,
            "approval_id":    candidate.approval_id,
            "decision_version": candidate.decision_version,
            "strategy_version": candidate.strategy_version,
            "approval_version": candidate.approval_version,
            "dependencies": [
                {"kind": d.kind.value, "reference": d.reference, "is_resolved": d.is_resolved}
                for d in candidate.dependencies
            ],
            "constraints": [
                {"type": c.constraint_type.value, "is_met": c.is_met}
                for c in candidate.constraints
            ],
            "requirements": [
                {"type": r.requirement_type, "value": r.value, "is_mandatory": r.is_mandatory}
                for r in candidate.requirements
            ],
            "metadata": [{"key": k, "value": v} for (k, v) in candidate.metadata],
            "summary": candidate.summary,
        }


__all__ = ["ExecutionPackageBuilder"]