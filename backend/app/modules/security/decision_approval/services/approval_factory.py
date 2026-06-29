"""
Approval Factory.

Converts an aggregated `ApprovalPolicyResult` into a fully populated
in-memory `ApprovalCandidateData`.  All required fields are filled
deterministically; no I/O happens here.
"""
from __future__ import annotations

from typing import Any, List, Tuple

from ..constants import ApprovalActorRole
from .approval_interfaces import (
    ApprovalCandidateData,
    ApprovalPolicyResult,
    ApprovalRequirementSpec,
)


def _stringify(value: Any, max_len: int = 2000) -> str:
    if value is None:
        return ""
    s = str(value)
    return s[:max_len]


def _extract_metadata(raw_data: Any) -> List[Tuple[str, Any]]:
    """
    Project a context's `raw_data` dict into a list of scalar (key, value)
    pairs suitable for ApprovalMetadata persistence.  Only scalar values
    (str, int, float, bool) are kept — nested dicts/lists are skipped to
    avoid exceeding column widths.
    """
    if not isinstance(raw_data, dict):
        return []
    out: List[Tuple[str, Any]] = []
    for k, v in raw_data.items():
        if isinstance(v, (str, int, float, bool)):
            out.append((str(k), v))
    return out


class ApprovalFactory:
    """Builds ApprovalCandidateData objects from policy verdicts + context."""

    def build_candidate(
        self,
        decision: Any,
        context: Any,
        verdict: ApprovalPolicyResult,
        *,
        approval_type: Any,
        scoring: dict,
        strategy: Any = None,
    ) -> ApprovalCandidateData:
        requirements: List[ApprovalRequirementSpec] = [
            ApprovalRequirementSpec(
                role=role,
                sequence_order=i + 1,
                is_mandatory=True,
                description=f"Required approver: {role.value}",
            )
            for i, role in enumerate(verdict.required_roles)
        ]

        constraints: List = []
        constraints.append((
            "POLICY_EVALUATED",
            True,
            f"{len(verdict.reasons)} policy reason(s) considered",
        ))
        constraints.append((
            "APPROVERS_RESOLVED",
            len(verdict.required_roles) > 0 if verdict.requires_approval else True,
            f"{len(verdict.required_roles)} approver(s) resolved",
        ))

        evidence: List = []
        for code, desc in verdict.reasons:
            evidence.append(("POLICY_REASON", f"{code}: {desc}"))

        # R12: strategy_id must reference the actual Strategy aggregate when
        # supplied; never fall back to decision.plan_id.
        strategy_id: Any = None
        if strategy is not None and getattr(strategy, "id", None) is not None:
            strategy_id = getattr(strategy, "id")
        elif getattr(decision, "strategy_id", None) is not None:
            strategy_id = getattr(decision, "strategy_id")

        return ApprovalCandidateData(
            decision_id=getattr(decision, "id", "unknown"),
            strategy_id=strategy_id,
            tenant_id=getattr(context, "tenant_id", None) or getattr(decision, "tenant_id", "default"),
            approval_type=approval_type,
            requirement_mode=verdict.requirement_mode,
            requirements=requirements,
            reasons=[(r[0], r[1]) for r in verdict.reasons],
            constraints=constraints,
            evidence=evidence,
            metadata=_extract_metadata(getattr(context, "raw_data", {})),
            risk_score=verdict.risk_score,
            criticality_score=verdict.criticality_score,
            composite_score=float(scoring.get("composite", 0.0)),
            confidence=verdict.confidence,
            requires_approval=verdict.requires_approval,
            auto_approve=verdict.auto_approve,
            auto_reject=verdict.auto_reject,
            is_valid=True,
            rejection_reason=None,
            business_justification=_stringify(getattr(context, "raw_data", {}).get("business_justification")),
            technical_justification=_stringify(getattr(context, "raw_data", {}).get("technical_justification")),
            is_emergency=bool(getattr(context, "raw_data", {}).get("emergency") or getattr(context, "raw_data", {}).get("emergency_mode")),
            correlation_id=getattr(decision, "correlation_id", None),
            trace_id=getattr(decision, "trace_id", None),
        )


__all__ = ["ApprovalFactory"]