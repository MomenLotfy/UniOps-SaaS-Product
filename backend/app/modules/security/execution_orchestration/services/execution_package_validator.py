"""
Execution Package Validator.

Returns a list of error codes for the candidate; empty list = valid.
This is the synchronous pre-flight check that runs before the
package is built — it does NOT touch the database.
"""
from __future__ import annotations

from typing import List

from ..constants import ExecutionRejectionReason
from .execution_interfaces import ExecutionCandidateData, IExecutionValidator


class ExecutionPackageValidator(IExecutionValidator):
    """Pure deterministic pre-build validation."""

    def validate(self, candidate: ExecutionCandidateData) -> List[str]:
        errors: List[str] = []

        if not candidate.tenant_id:
            errors.append(ExecutionRejectionReason.MISSING_METADATA.value)

        if not candidate.decision_id:
            errors.append(ExecutionRejectionReason.MISSING_DECISION.value)

        # Hard readiness gates
        for v in candidate.readiness_factors:
            if v.outcome.name == "FAILED":
                # Map known failures back to canonical rejection codes
                from ..constants import ReadinessFactor
                mapping = {
                    ReadinessFactor.DECISION_READY:    ExecutionRejectionReason.DECISION_NOT_READY,
                    ReadinessFactor.APPROVAL_COMPLETE: ExecutionRejectionReason.APPROVAL_NOT_APPROVED,
                    ReadinessFactor.STRATEGY_SELECTED: ExecutionRejectionReason.MISSING_STRATEGY,
                    ReadinessFactor.REPOSITORY_AVAILABLE: ExecutionRejectionReason.REPOSITORY_UNAVAILABLE,
                    ReadinessFactor.ASSET_AVAILABLE:   ExecutionRejectionReason.ASSET_UNAVAILABLE,
                    ReadinessFactor.DEPENDENCY_GRAPH_VALID: ExecutionRejectionReason.INVALID_DEPENDENCY_GRAPH,
                    ReadinessFactor.REQUIRED_METADATA: ExecutionRejectionReason.MISSING_METADATA,
                    ReadinessFactor.TENANT_ISOLATION:  ExecutionRejectionReason.TENANT_ISOLATION_BROKEN,
                    ReadinessFactor.POLICY_COMPLIANCE: ExecutionRejectionReason.POLICY_DENIED,
                    ReadinessFactor.ENVIRONMENT_COMPAT: ExecutionRejectionReason.ENVIRONMENT_INCOMPAT,
                    ReadinessFactor.EXECUTION_WINDOW:  ExecutionRejectionReason.EXECUTION_WINDOW_INVALID,
                    ReadinessFactor.ROLLBACK_METADATA: ExecutionRejectionReason.MISSING_ROLLBACK_METADATA,
                }
                errors.append(mapping.get(v.factor, ExecutionRejectionReason.MISSING_METADATA).value)

        return list(dict.fromkeys(errors))  # deterministic, de-duplicated


__all__ = ["ExecutionPackageValidator"]