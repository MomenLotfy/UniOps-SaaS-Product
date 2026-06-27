"""
Approval Serializer.

Round-trips ApprovalCandidateData → dict → ApprovalCandidateData for
snapshotting + restoration.  Mirrors `strategy_serializer.py`.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

from ..constants import ApprovalActorRole, ApprovalRequirementMode, ApprovalType
from .approval_interfaces import ApprovalCandidateData, ApprovalRequirementSpec


def serialize_candidate(candidate: ApprovalCandidateData) -> Dict[str, Any]:
    """Convert in-memory candidate to a JSON-safe dict."""
    return {
        "decision_id":            candidate.decision_id,
        "strategy_id":            candidate.strategy_id,
        "tenant_id":              candidate.tenant_id,
        "approval_type":          candidate.approval_type.value,
        "requirement_mode":       candidate.requirement_mode.value,
        "requirements": [
            {
                "role":           r.role.value,
                "sequence_order": r.sequence_order,
                "is_mandatory":   r.is_mandatory,
                "description":    r.description,
            }
            for r in candidate.requirements
        ],
        "reasons":   [list(r) for r in candidate.reasons],
        "constraints": [list(c) for c in candidate.constraints],
        "evidence":  [list(e) for e in candidate.evidence],
        "risk_score":        candidate.risk_score,
        "criticality_score": candidate.criticality_score,
        "composite_score":   candidate.composite_score,
        "confidence":        candidate.confidence,
        "requires_approval": candidate.requires_approval,
        "auto_approve":      candidate.auto_approve,
        "auto_reject":       candidate.auto_reject,
        "is_valid":          candidate.is_valid,
        "rejection_reason":  candidate.rejection_reason,
        "business_justification":  candidate.business_justification,
        "technical_justification": candidate.technical_justification,
        "is_emergency":      candidate.is_emergency,
        "correlation_id":    candidate.correlation_id,
        "trace_id":          candidate.trace_id,
    }


def deserialize_candidate(payload: Dict[str, Any]) -> ApprovalCandidateData:
    """Inverse of `serialize_candidate`.  Defensive — does not mutate input."""
    return ApprovalCandidateData(
        decision_id=payload["decision_id"],
        strategy_id=payload.get("strategy_id"),
        tenant_id=payload["tenant_id"],
        approval_type=ApprovalType(payload["approval_type"]),
        requirement_mode=ApprovalRequirementMode(payload["requirement_mode"]),
        requirements=[
            ApprovalRequirementSpec(
                role=ApprovalActorRole(r["role"]),
                sequence_order=int(r.get("sequence_order", i + 1)),
                is_mandatory=bool(r.get("is_mandatory", True)),
                description=r.get("description"),
            )
            for i, r in enumerate(payload.get("requirements", []))
        ],
        reasons=[tuple(r) for r in payload.get("reasons", [])],
        constraints=[tuple(c) for c in payload.get("constraints", [])],
        evidence=[tuple(e) for e in payload.get("evidence", [])],
        risk_score=float(payload.get("risk_score", 0.0)),
        criticality_score=float(payload.get("criticality_score", 0.0)),
        composite_score=float(payload.get("composite_score", 0.0)),
        confidence=float(payload.get("confidence", 0.0)),
        requires_approval=bool(payload.get("requires_approval", True)),
        auto_approve=bool(payload.get("auto_approve", False)),
        auto_reject=bool(payload.get("auto_reject", False)),
        is_valid=bool(payload.get("is_valid", True)),
        rejection_reason=payload.get("rejection_reason"),
        business_justification=payload.get("business_justification"),
        technical_justification=payload.get("technical_justification"),
        is_emergency=bool(payload.get("is_emergency", False)),
        correlation_id=payload.get("correlation_id"),
        trace_id=payload.get("trace_id"),
    )


__all__ = [
    "ApprovalSerializer",
    "serialize_candidate",
    "deserialize_candidate",
]


class ApprovalSerializer:
    """
    Convenience facade over the module-level serialize/deserialize
    functions.  Exists primarily so callers can refer to the
    serializer as a class — matching the spec's
    `ApprovalSerializer` service name.
    """

    @staticmethod
    def serialize(candidate):
        return serialize_candidate(candidate)

    @staticmethod
    def deserialize(payload):
        return deserialize_candidate(payload)
