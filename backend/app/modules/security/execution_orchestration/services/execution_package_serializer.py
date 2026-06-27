"""
Execution Package Serializer.

Pure functions for converting an `ExecutionCandidateData` /
`ExecutionEvaluationResult` to / from JSON-friendly dicts.  Used
by the API layer and by the persistence layer when constructing
`ExecutionVersion.snapshot` rows.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..constants import (
    ExecutionConstraintType,
    ExecutionDependencyKind,
    ExecutionPackageState,
    ReadinessFactor,
    ReadinessOutcome,
)
from .execution_interfaces import (
    ExecutionCandidateData,
    ExecutionEvaluationResult,
)


def _jsonify(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    # Enums
    if hasattr(value, "value") and hasattr(value, "__class__"):
        try:
            return value.value
        except Exception:  # pragma: no cover - defensive
            pass
    # dicts / lists — recurse
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(v) for v in value]
    # datetimes
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:  # pragma: no cover
            return str(value)
    return str(value)


def serialize_candidate(candidate: ExecutionCandidateData) -> Dict[str, Any]:
    if candidate is None:
        return {}
    return {
        "tenant_id":          candidate.tenant_id,
        "decision_id":        candidate.decision_id,
        "strategy_id":        candidate.strategy_id,
        "approval_id":        candidate.approval_id,
        "correlation_id":     candidate.correlation_id,
        "trace_id":           candidate.trace_id,
        "decision_version":   candidate.decision_version,
        "strategy_version":   candidate.strategy_version,
        "approval_version":   candidate.approval_version,
        "is_valid":           candidate.is_valid,
        "rejection_reason":   candidate.rejection_reason,
        "rejection_details":  candidate.rejection_details,
        "readiness": {
            "total":  candidate.readiness_total,
            "passed": candidate.readiness_passed,
            "warned": candidate.readiness_warned,
            "failed": candidate.readiness_failed,
            "latency_ms": candidate.readiness_ms,
            "verdicts": [
                {
                    "factor":   v.factor.value if hasattr(v.factor, "value") else str(v.factor),
                    "outcome":  v.outcome.value if hasattr(v.outcome, "value") else str(v.outcome),
                    "rationale": v.rationale,
                    "details":  _jsonify(v.details),
                    "latency_ms": v.latency_ms,
                }
                for v in candidate.readiness_factors
            ],
        },
        "dependencies": [
            {
                "kind":         d.kind.value if hasattr(d.kind, "value") else str(d.kind),
                "reference":    d.reference,
                "display_name": d.display_name,
                "is_resolved":  d.is_resolved,
                "notes":        d.notes,
                "resolution_ms": d.resolution_ms,
            }
            for d in candidate.dependencies
        ],
        "constraints": [
            {
                "constraint_type": c.constraint_type.value if hasattr(c.constraint_type, "value") else str(c.constraint_type),
                "is_met":          c.is_met,
                "severity":        c.severity,
                "details":         c.details,
            }
            for c in candidate.constraints
        ],
        "requirements": [
            {
                "requirement_type": r.requirement_type,
                "value":            r.value,
                "is_mandatory":     r.is_mandatory,
                "description":      r.description,
            }
            for r in candidate.requirements
        ],
        "metadata": [
            {"key": k, "value": v}
            for (k, v) in candidate.metadata
        ],
        "summary":            candidate.summary,
        "package_size_kb":    candidate.package_size_kb,
        "payload_hash":       candidate.payload_hash,
        "evaluation_duration_ms": candidate.evaluation_duration_ms,
    }


def serialize_result(result: ExecutionEvaluationResult) -> Dict[str, Any]:
    if result is None:
        return {}
    return {
        "tenant_id":              result.tenant_id,
        "decision_id":            result.decision_id,
        "package_id":             result.package_id,
        "final_state":            result.final_state.value if hasattr(result.final_state, "value") else str(result.final_state),
        "ranking_stable":         result.ranking_stable,
        "evaluation_duration_ms": result.evaluation_duration_ms,
        "rejection_reason":       result.rejection_reason,
        "candidate":              serialize_candidate(result.candidate) if result.candidate else None,
    }


def deserialize_candidate(payload: Dict[str, Any]) -> ExecutionCandidateData:
    """Inverse of `serialize_candidate` — used by version rollback / audit."""
    if not payload:
        return ExecutionCandidateData()
    cand = ExecutionCandidateData(
        tenant_id=payload.get("tenant_id", "default"),
        decision_id=payload.get("decision_id", ""),
        strategy_id=payload.get("strategy_id"),
        approval_id=payload.get("approval_id"),
        correlation_id=payload.get("correlation_id"),
        trace_id=payload.get("trace_id"),
        decision_version=payload.get("decision_version"),
        strategy_version=payload.get("strategy_version"),
        approval_version=payload.get("approval_version"),
        is_valid=payload.get("is_valid", True),
        rejection_reason=payload.get("rejection_reason"),
        rejection_details=payload.get("rejection_details"),
        summary=payload.get("summary"),
        package_size_kb=float(payload.get("package_size_kb", 0.0)),
        payload_hash=payload.get("payload_hash"),
        evaluation_duration_ms=int(payload.get("evaluation_duration_ms", 0)),
    )
    readiness = payload.get("readiness") or {}
    cand.readiness_total = int(readiness.get("total", 0))
    cand.readiness_passed = int(readiness.get("passed", 0))
    cand.readiness_warned = int(readiness.get("warned", 0))
    cand.readiness_failed = int(readiness.get("failed", 0))
    cand.readiness_ms = float(readiness.get("latency_ms", 0.0))

    from .execution_interfaces import ReadinessFactorResult, ExecutionDependencySpec, ExecutionConstraintSpec
    cand.readiness_factors = [
        ReadinessFactorResult(
            factor=ReadinessFactor(v["factor"]),
            outcome=ReadinessOutcome(v["outcome"]),
            rationale=v.get("rationale", ""),
            details=v.get("details") or {},
            latency_ms=float(v.get("latency_ms", 0.0)),
        )
        for v in readiness.get("verdicts", [])
    ]
    cand.dependencies = [
        ExecutionDependencySpec(
            kind=ExecutionDependencyKind(d["kind"]),
            reference=d["reference"],
            display_name=d.get("display_name"),
            is_resolved=bool(d.get("is_resolved", False)),
            notes=d.get("notes"),
            resolution_ms=float(d.get("resolution_ms", 0.0)),
        )
        for d in payload.get("dependencies", [])
    ]
    cand.constraints = [
        ExecutionConstraintSpec(
            constraint_type=ExecutionConstraintType(c["constraint_type"]),
            is_met=bool(c.get("is_met", False)),
            severity=c.get("severity", "HARD"),
            details=c.get("details"),
        )
        for c in payload.get("constraints", [])
    ]
    cand.metadata = [(m["key"], m["value"]) for m in payload.get("metadata", [])]
    return cand


class ExecutionPackageSerializer:
    """Object-oriented façade for the free functions above."""

    def to_dict(self, candidate: ExecutionCandidateData) -> Dict[str, Any]:
        return serialize_candidate(candidate)

    def from_dict(self, payload: Dict[str, Any]) -> ExecutionCandidateData:
        return deserialize_candidate(payload)

    def result_to_dict(self, result: ExecutionEvaluationResult) -> Dict[str, Any]:
        return serialize_result(result)

    def to_json(self, candidate: ExecutionCandidateData) -> str:
        return json.dumps(self.to_dict(candidate), default=str, sort_keys=True)


__all__ = [
    "ExecutionPackageSerializer",
    "deserialize_candidate",
    "serialize_candidate",
    "serialize_result",
]