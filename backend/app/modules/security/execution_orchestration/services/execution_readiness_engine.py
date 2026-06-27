"""
Execution Readiness Engine.

Pluggable registry of `IExecutionReadinessCheck` implementations,
one per `ReadinessFactor`.  The default registry ships with 12
checks — one for every factor defined in `constants.ReadinessFactor`.

New checks can be registered at runtime via `.register(factor, check)`
without engine changes.

Mirrors `decision_approval/services/approval_evaluator.py`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..constants import ReadinessFactor, ReadinessOutcome
from .execution_interfaces import (
    ExecutionCandidateData,
    IExecutionReadinessCheck,
    IExecutionReadinessEngine,
    ReadinessFactorResult,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
#  Per-factor checks
# ─────────────────────────────────────────────────────────────────────
class DecisionReadyCheck(IExecutionReadinessCheck):
    """Verifies that the originating Decision is in a buildable state."""
    factor = ReadinessFactor.DECISION_READY

    _BUILDABLE_STATES = {"READY", "APPROVED", "BUILDABLE", "READY_FOR_EXECUTION"}

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        decision_state = (
            candidate.dependencies and  # type: ignore[truthy-function]
            getattr(context, "decision_state", None)
        ) or ""
        decision_state = str(decision_state).upper() if decision_state else ""

        outcome = (
            ReadinessOutcome.PASSED
            if decision_state in self._BUILDABLE_STATES
            else ReadinessOutcome.FAILED
        )
        rationale = (
            f"Decision state={decision_state or 'UNKNOWN'}"
            + (
                " is buildable"
                if outcome == ReadinessOutcome.PASSED
                else " is not in a buildable state"
            )
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=rationale,
            details={"decision_state": decision_state},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class ApprovalCompleteCheck(IExecutionReadinessCheck):
    """Verifies the upstream Approval is APPROVED."""
    factor = ReadinessFactor.APPROVAL_COMPLETE

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return candidate.approval_id is not None

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        approval_state = str(getattr(context, "approval_state", "") or "").upper()
        outcome = (
            ReadinessOutcome.PASSED
            if approval_state == "APPROVED"
            else ReadinessOutcome.FAILED
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=f"Approval state={approval_state or 'MISSING'}",
            details={"approval_state": approval_state},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class StrategySelectedCheck(IExecutionReadinessCheck):
    """Verifies that a non-rejected Strategy was selected."""
    factor = ReadinessFactor.STRATEGY_SELECTED

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return candidate.strategy_id is not None

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        strategy_state = str(getattr(context, "strategy_state", "") or "").upper()
        outcome = (
            ReadinessOutcome.PASSED
            if strategy_state in {"SELECTED", "APPROVED", "READY", "BUILDABLE"}
            else ReadinessOutcome.FAILED
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=f"Strategy state={strategy_state or 'MISSING'}",
            details={"strategy_state": strategy_state},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class RepositoryAvailableCheck(IExecutionReadinessCheck):
    """Verifies a Repository reference is present on the decision context."""
    factor = ReadinessFactor.REPOSITORY_AVAILABLE

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        repo_id = getattr(context, "repository_id", None) or (
            (getattr(context, "context_snapshot", {}) or {}).get("repository_id")
        )
        outcome = ReadinessOutcome.PASSED if repo_id else ReadinessOutcome.WARNING
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale="Repository reference found" if repo_id else "Repository reference missing (soft)",
            details={"repository_id": repo_id},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class AssetAvailableCheck(IExecutionReadinessCheck):
    """Verifies the target Asset reference is present."""
    factor = ReadinessFactor.ASSET_AVAILABLE

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        asset_id = getattr(context, "asset_id", None) or (
            (getattr(context, "context_snapshot", {}) or {}).get("asset_id")
        )
        outcome = ReadinessOutcome.PASSED if asset_id else ReadinessOutcome.WARNING
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale="Asset reference found" if asset_id else "Asset reference missing (soft)",
            details={"asset_id": asset_id},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class DependencyGraphValidCheck(IExecutionReadinessCheck):
    """Verifies the dependency graph has no orphan references."""
    factor = ReadinessFactor.DEPENDENCY_GRAPH_VALID

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        deps = candidate.dependencies or []
        unresolved = [d for d in deps if not d.is_resolved]
        outcome = (
            ReadinessOutcome.FAILED
            if any(getattr(d, "kind", None) and str(d.kind).endswith("REQUIRED") for d in unresolved)
            else ReadinessOutcome.PASSED
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=(
                f"All {len(deps)} dependencies resolved"
                if not unresolved
                else f"{len(unresolved)} dependency(s) unresolved"
            ),
            details={"total": len(deps), "unresolved": len(unresolved)},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class RequiredMetadataCheck(IExecutionReadinessCheck):
    """Verifies the candidate carries required metadata (rollback, owner, …)."""
    factor = ReadinessFactor.REQUIRED_METADATA

    _REQUIRED_KEYS = ("rollback_strategy", "owner")

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        keys = {k for (k, _) in candidate.metadata}
        missing = [k for k in self._REQUIRED_KEYS if k not in keys]
        outcome = ReadinessOutcome.PASSED if not missing else ReadinessOutcome.WARNING
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=(
                "All required metadata present"
                if not missing
                else f"Missing soft metadata: {', '.join(missing)}"
            ),
            details={"missing": missing},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class TenantIsolationCheck(IExecutionReadinessCheck):
    """Verifies the candidate's tenant_id matches the upstream decision."""
    factor = ReadinessFactor.TENANT_ISOLATION

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        decision_tenant = getattr(context, "tenant_id", None) or (
            (getattr(context, "decision_snapshot", {}) or {}).get("tenant_id")
        )
        outcome = (
            ReadinessOutcome.PASSED
            if decision_tenant is None or str(decision_tenant) == str(candidate.tenant_id)
            else ReadinessOutcome.FAILED
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=(
                f"Tenant match: candidate={candidate.tenant_id} decision={decision_tenant}"
            ),
            details={"candidate_tenant": candidate.tenant_id, "decision_tenant": decision_tenant},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class PolicyComplianceCheck(IExecutionReadinessCheck):
    """Verifies the policy compliance verdict is PASSED."""
    factor = ReadinessFactor.POLICY_COMPLIANCE

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        verdict = str(getattr(context, "policy_compliance", "") or "").upper()
        outcome = (
            ReadinessOutcome.PASSED
            if verdict in {"PASSED", "COMPLIANT", ""}
            else ReadinessOutcome.FAILED
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=f"Policy compliance={verdict or 'UNKNOWN'}",
            details={"policy_compliance": verdict},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class EnvironmentCompatibilityCheck(IExecutionReadinessCheck):
    """Verifies the target environment matches the package target."""
    factor = ReadinessFactor.ENVIRONMENT_COMPAT

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        env = str(getattr(context, "environment", "") or "").upper()
        target_env = str(getattr(context, "target_environment", "") or "").upper()
        if not env or not target_env:
            outcome = ReadinessOutcome.WARNING
        elif env == target_env or target_env in {"ANY", "ALL"}:
            outcome = ReadinessOutcome.PASSED
        else:
            outcome = ReadinessOutcome.FAILED
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=f"env={env or '?'} target={target_env or '?'}",
            details={"environment": env, "target_environment": target_env},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class ExecutionWindowCheck(IExecutionReadinessCheck):
    """Verifies an execution window is set and (if provided) not expired."""
    factor = ReadinessFactor.EXECUTION_WINDOW

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        window_open = getattr(context, "execution_window_open", None)
        if window_open is None:
            outcome = ReadinessOutcome.WARNING
            rationale = "Execution window not specified (soft)"
        elif bool(window_open):
            outcome = ReadinessOutcome.PASSED
            rationale = "Execution window is open"
        else:
            outcome = ReadinessOutcome.FAILED
            rationale = "Execution window is closed"
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=rationale,
            details={"window_open": window_open},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


class RollbackMetadataCheck(IExecutionReadinessCheck):
    """Verifies a rollback strategy was captured."""
    factor = ReadinessFactor.ROLLBACK_METADATA

    def applicable(self, candidate: ExecutionCandidateData, context: Any) -> bool:
        return True

    def evaluate(self, candidate: ExecutionCandidateData, context: Any) -> ReadinessFactorResult:
        started = time.monotonic()
        keys = {k for (k, _) in candidate.metadata}
        outcome = (
            ReadinessOutcome.PASSED
            if "rollback_strategy" in keys
            else ReadinessOutcome.WARNING
        )
        return ReadinessFactorResult(
            factor=self.factor,
            outcome=outcome,
            rationale=(
                "Rollback strategy captured"
                if outcome == ReadinessOutcome.PASSED
                else "Rollback strategy missing (soft)"
            ),
            details={"has_rollback": "rollback_strategy" in keys},
            latency_ms=(time.monotonic() - started) * 1000.0,
        )


# ─────────────────────────────────────────────────────────────────────
#  Default registry (12 checks, one per factor)
# ─────────────────────────────────────────────────────────────────────
DEFAULT_READINESS_CHECKS: Dict[ReadinessFactor, IExecutionReadinessCheck] = {
    ReadinessFactor.DECISION_READY:         DecisionReadyCheck(),
    ReadinessFactor.APPROVAL_COMPLETE:      ApprovalCompleteCheck(),
    ReadinessFactor.STRATEGY_SELECTED:      StrategySelectedCheck(),
    ReadinessFactor.REPOSITORY_AVAILABLE:   RepositoryAvailableCheck(),
    ReadinessFactor.ASSET_AVAILABLE:        AssetAvailableCheck(),
    ReadinessFactor.DEPENDENCY_GRAPH_VALID: DependencyGraphValidCheck(),
    ReadinessFactor.REQUIRED_METADATA:      RequiredMetadataCheck(),
    ReadinessFactor.TENANT_ISOLATION:       TenantIsolationCheck(),
    ReadinessFactor.POLICY_COMPLIANCE:      PolicyComplianceCheck(),
    ReadinessFactor.ENVIRONMENT_COMPAT:     EnvironmentCompatibilityCheck(),
    ReadinessFactor.EXECUTION_WINDOW:       ExecutionWindowCheck(),
    ReadinessFactor.ROLLBACK_METADATA:      RollbackMetadataCheck(),
}


def bootstrap_default_readiness_checks(
    registry: "ExecutionReadinessEngine",
) -> "ExecutionReadinessEngine":
    for factor, check in DEFAULT_READINESS_CHECKS.items():
        registry.register(factor, check)
    return registry


# ─────────────────────────────────────────────────────────────────────
#  Engine
# ─────────────────────────────────────────────────────────────────────
class ExecutionReadinessEngine(IExecutionReadinessEngine):
    """Coordinates the per-factor checks for one ExecutionPackage."""

    def __init__(
        self,
        checks: Optional[Dict[ReadinessFactor, IExecutionReadinessCheck]] = None,
    ) -> None:
        self._checks: Dict[ReadinessFactor, IExecutionReadinessCheck] = (
            dict(checks) if checks else {}
        )

    def register(self, factor: ReadinessFactor, check: IExecutionReadinessCheck) -> None:
        self._checks[factor] = check

    def get(self, factor: ReadinessFactor) -> Optional[IExecutionReadinessCheck]:
        return self._checks.get(factor)

    def all(self) -> Dict[ReadinessFactor, IExecutionReadinessCheck]:
        return dict(self._checks)

    def run(self, candidate: ExecutionCandidateData, context: Any) -> List[ReadinessFactorResult]:
        started = time.monotonic()
        verdicts: List[ReadinessFactorResult] = []
        for factor, check in self._checks.items():
            try:
                if not check.applicable(candidate, context):
                    verdicts.append(ReadinessFactorResult(
                        factor=factor,
                        outcome=ReadinessOutcome.WARNING,
                        rationale="Skipped (not applicable)",
                    ))
                    continue
                verdicts.append(check.evaluate(candidate, context))
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception(
                    "readiness check failed factor=%s", factor,
                )
                verdicts.append(ReadinessFactorResult(
                    factor=factor,
                    outcome=ReadinessOutcome.FAILED,
                    rationale=f"Check raised: {exc!r}"[:500],
                ))

        candidate.readiness_factors = verdicts
        candidate.readiness_total = len(verdicts)
        candidate.readiness_passed = sum(1 for v in verdicts if v.is_passed)
        candidate.readiness_warned = sum(1 for v in verdicts if v.is_warned)
        candidate.readiness_failed = sum(1 for v in verdicts if v.is_failed)
        candidate.readiness_ms = (time.monotonic() - started) * 1000.0
        return verdicts


__all__ = [
    "DEFAULT_READINESS_CHECKS",
    "DecisionReadyCheck",
    "ApprovalCompleteCheck",
    "StrategySelectedCheck",
    "RepositoryAvailableCheck",
    "AssetAvailableCheck",
    "DependencyGraphValidCheck",
    "RequiredMetadataCheck",
    "TenantIsolationCheck",
    "PolicyComplianceCheck",
    "EnvironmentCompatibilityCheck",
    "ExecutionWindowCheck",
    "RollbackMetadataCheck",
    "ExecutionReadinessEngine",
    "bootstrap_default_readiness_checks",
]