"""
Execution Package Factory.

Builds `ExecutionCandidateData` from a `ExecutionPreparationSnapshot`
and any pre-collected context.  All required fields are filled
deterministically; no I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import ValidationError
from ..constants import ExecutionRejectionReason
from .execution_interfaces import (
    ExecutionCandidateData,
    ExecutionDependencySpec,
    ExecutionPreparationSnapshot,
    ExecutionRequirementSpec,
)


def _stringify(value: Any, max_len: int = 4000) -> str:
    if value is None:
        return ""
    s = str(value)
    return s[:max_len]


class ExecutionPackageFactory:
    """Builds ExecutionCandidateData objects from upstream snapshots."""

    def build_candidate(
        self,
        snapshot: ExecutionPreparationSnapshot,
        *,
        metadata: Optional[List[Tuple[str, str]]] = None,
        requirements: Optional[List[ExecutionRequirementSpec]] = None,
        summary: Optional[str] = None,
    ) -> ExecutionCandidateData:
        if snapshot is None:
            raise ValidationError("ExecutionPreparationSnapshot is required", field="snapshot")

        # If the snapshot was missing mandatory fields, surface that as
        # an immediate rejection reason.
        rejection_reason: Optional[str] = None
        rejection_details: Optional[str] = None
        if not snapshot.is_complete:
            rejection_reason = (
                ExecutionRejectionReason.MISSING_DECISION.value
                if not snapshot.decision_id
                else ExecutionRejectionReason.MISSING_METADATA.value
            )
            rejection_details = (
                f"Missing mandatory fields: {', '.join(snapshot.missing_fields)}"
            )

        # Synthesize baseline requirements from metadata so the package
        # always carries at least the contract implied by its own
        # metadata (e.g. rollback_strategy_present whenever rollback is
        # declared).  Caller-supplied requirements are appended after.
        synthesized: List[ExecutionRequirementSpec] = []
        meta_keys = {str(k) for (k, _) in (metadata or [])}
        if "rollback_strategy" in meta_keys:
            synthesized.append(ExecutionRequirementSpec(
                requirement_type="rollback_strategy_present",
                value="true",
                is_mandatory=True,
                description="A rollback_strategy was declared in package metadata",
            ))

        final_requirements: List[ExecutionRequirementSpec] = list(
            synthesized
        ) + list(requirements or [])

        return ExecutionCandidateData(
            tenant_id=snapshot.tenant_id,
            decision_id=snapshot.decision_id,
            strategy_id=snapshot.strategy_id,
            approval_id=snapshot.approval_id,
            correlation_id=(snapshot.decision_snapshot.get("correlation_id")
                            if isinstance(snapshot.decision_snapshot, dict) else None),
            trace_id=(snapshot.decision_snapshot.get("trace_id")
                      if isinstance(snapshot.decision_snapshot, dict) else None),
            decision_version=(snapshot.decision_snapshot.get("version")
                              if isinstance(snapshot.decision_snapshot, dict) else None),
            strategy_version=(snapshot.strategy_snapshot.get("version")
                              if isinstance(snapshot.strategy_snapshot, dict) else None),
            approval_version=(snapshot.approval_snapshot.get("version")
                              if isinstance(snapshot.approval_snapshot, dict) else None),
            is_valid=bool(snapshot.is_complete),
            rejection_reason=rejection_reason,
            rejection_details=rejection_details,
            dependencies=[],
            constraints=[],
            requirements=final_requirements,
            metadata=list(metadata or []),
            summary=_stringify(summary, max_len=2000) or None,
        )


__all__ = ["ExecutionPackageFactory"]