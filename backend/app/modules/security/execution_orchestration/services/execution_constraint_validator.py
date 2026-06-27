"""
Execution Constraint Validator.

Validates the 12 hard `ExecutionConstraintType` values before the
package is allowed to transition READY.

Mirrors `decision_approval/services/approval_validator.py`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..constants import ExecutionConstraintType, ReadinessFactor, ReadinessOutcome
from .execution_interfaces import (
    ExecutionCandidateData,
    ExecutionConstraintSpec,
    IExecutionConstraintValidator,
    ReadinessFactorResult,
)

logger = logging.getLogger(__name__)


# Map each hard `ExecutionConstraintType` to the readiness factor it
# mirrors.  Keeping this as a class constant makes it trivially
# auditable: 1-to-1 correspondence with the spec.
_CONSTRAINT_TO_FACTOR: Dict[ExecutionConstraintType, ReadinessFactor] = {
    ExecutionConstraintType.DECISION_READY:        ReadinessFactor.DECISION_READY,
    ExecutionConstraintType.APPROVAL_APPROVED:     ReadinessFactor.APPROVAL_COMPLETE,
    ExecutionConstraintType.STRATEGY_APPROVED:     ReadinessFactor.STRATEGY_SELECTED,
    ExecutionConstraintType.REPOSITORY_PRESENT:    ReadinessFactor.REPOSITORY_AVAILABLE,
    ExecutionConstraintType.ASSET_PRESENT:         ReadinessFactor.ASSET_AVAILABLE,
    ExecutionConstraintType.DEPENDENCY_RESOLVED:   ReadinessFactor.DEPENDENCY_GRAPH_VALID,
    ExecutionConstraintType.METADATA_COMPLETE:     ReadinessFactor.REQUIRED_METADATA,
    ExecutionConstraintType.TENANT_MATCH:          ReadinessFactor.TENANT_ISOLATION,
    ExecutionConstraintType.POLICY_PASSED:         ReadinessFactor.POLICY_COMPLIANCE,
    ExecutionConstraintType.ENVIRONMENT_MATCH:     ReadinessFactor.ENVIRONMENT_COMPAT,
    ExecutionConstraintType.EXECUTION_WINDOW_OPEN: ReadinessFactor.EXECUTION_WINDOW,
    ExecutionConstraintType.ROLLBACK_PLANNED:      ReadinessFactor.ROLLBACK_METADATA,
}


class ExecutionConstraintValidator(IExecutionConstraintValidator):
    """
    Pure deterministic validator.  Reads the candidate's readiness
    verdicts (already computed by `ExecutionReadinessEngine`) and
    emits one `ExecutionConstraintSpec` per `ExecutionConstraintType`.
    """

    def validate(
        self,
        candidate: ExecutionCandidateData,
        context: Any,
    ) -> List[ExecutionConstraintSpec]:
        started = time.monotonic()
        verdicts = {v.factor: v for v in candidate.readiness_factors}

        def _passed(factor: ReadinessFactor) -> bool:
            v: Optional[ReadinessFactorResult] = verdicts.get(factor)
            return v is not None and v.outcome == ReadinessOutcome.PASSED

        specs: List[ExecutionConstraintSpec] = []
        for constraint_type, factor in _CONSTRAINT_TO_FACTOR.items():
            specs.append(ExecutionConstraintSpec(
                constraint_type=constraint_type,
                is_met=_passed(factor),
                severity="HARD",
                details=f"Mirrors readiness.{factor.value}",
            ))

        candidate.constraints = specs
        elapsed_ms = (time.monotonic() - started) * 1000.0
        unmet = sum(1 for s in specs if not s.is_met)
        logger.debug(
            "execution constraint validation tenant=%s decision=%s met=%d/%d in %.2fms",
            candidate.tenant_id, candidate.decision_id,
            len(specs) - unmet, len(specs), elapsed_ms,
        )
        return specs


__all__ = ["ExecutionConstraintValidator"]