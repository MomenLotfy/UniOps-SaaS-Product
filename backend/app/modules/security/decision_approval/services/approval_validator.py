"""
Approval Validator.

Returns a list of error codes (empty list == valid).  Mirrors
`DecisionStrategyValidator`.
"""
from __future__ import annotations

from typing import Any, List

from ..constants import ApprovalRejectionReason
from .approval_interfaces import ApprovalCandidateData, IApprovalValidator


class ApprovalValidator(IApprovalValidator):
    """Deterministic validation of ApprovalCandidateData + Decision + Context."""

    def validate(self, request: Any, context: Any) -> List[str]:
        return self._validate_candidate(request) if isinstance(request, ApprovalCandidateData) \
            else self._validate_persisted(request, context)

    # ── In-memory validation ─────────────────────────────────────────
    def _validate_candidate(self, candidate: ApprovalCandidateData) -> List[str]:
        errors: List[str] = []
        if not candidate.decision_id:
            errors.append(ApprovalRejectionReason.MISSING_DECISION.value)
        if not candidate.tenant_id:
            errors.append("MISSING_TENANT")
        if candidate.auto_reject:
            errors.append(ApprovalRejectionReason.AUTOMATIC_REJECTION.value)
        if candidate.requires_approval and not candidate.requirements:
            errors.append(ApprovalRejectionReason.MISSING_APPROVER.value)
        if candidate.requirement_mode is None:
            errors.append(ApprovalRejectionReason.INVALID_CHAIN.value)
        return errors

    # ── Persisted-request validation ─────────────────────────────────
    def _validate_persisted(self, request: Any, context: Any) -> List[str]:
        errors: List[str] = []
        if request is None:
            errors.append(ApprovalRejectionReason.MISSING_DECISION.value)
            return errors
        if not getattr(request, "decision_id", None):
            errors.append(ApprovalRejectionReason.MISSING_DECISION.value)
        if not getattr(request, "tenant_id", None):
            errors.append("MISSING_TENANT")
        if getattr(request, "blocked", False):
            errors.append(ApprovalRejectionReason.POLICY_DENIED.value)
        return errors


__all__ = ["ApprovalValidator"]
