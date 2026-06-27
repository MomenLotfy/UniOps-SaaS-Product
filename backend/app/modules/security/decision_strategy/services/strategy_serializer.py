"""
Decision Strategy Serializer.

Pure functions to convert in-memory candidates + decision-strategy rows
into stable, JSON-safe dicts used by versioning, audit, and the API.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..constants import StrategyState, StrategyType
from .strategy_interfaces import StrategyCandidateData


def serialize_candidate(c: StrategyCandidateData) -> Dict[str, Any]:
    rr = c.rejection_reason
    return {
        "type":               c.candidate_type.value if hasattr(c.candidate_type, "value") else str(c.candidate_type),
        "is_valid":           c.is_valid,
        "rejection_reason":   rr.value if hasattr(rr, "value") else (str(rr) if rr else None),
        "rejection_details":  c.rejection_details,
        "feasibility_score":  c.feasibility_score,
        "composite_score":    c.composite_score,
        "expected_downtime_min": c.expected_downtime_min,
        "requires_human_approval": c.requires_human_approval,
        "is_reversible":      c.is_reversible,
        "constraints":        [
            {"type": getattr(x, "type", None), "is_met": getattr(x, "is_met", True)}
            for x in c.constraints
        ],
        "requirements":       [
            {"type": getattr(x, "type", None), "value": getattr(x, "description", None)}
            for x in c.requirements
        ],
        "scores": [
            {
                "dimension":   s.dimension,
                "value":       s.value,
                "weight":      s.weight,
                "contribution": s.contribution,
                "rationale":   s.rationale,
            }
            for s in c.scores
        ],
    }


def serialize_strategy_snapshot(strategy_row: Any) -> Dict[str, Any]:
    """
    Snapshot a `DecisionStrategy` ORM row into a JSON-safe dict suitable
    for `StrategyVersion.snapshot` JSONB storage.
    """
    return {
        "id":                    strategy_row.id,
        "decision_id":           strategy_row.decision_id,
        "plan_id":               strategy_row.plan_id,
        "strategy_type":         strategy_row.strategy_type.value
                                 if hasattr(strategy_row.strategy_type, "value")
                                 else strategy_row.strategy_type,
        "state":                 strategy_row.state.value
                                 if hasattr(strategy_row.state, "value")
                                 else strategy_row.state,
        "priority":              strategy_row.priority,
        "confidence":            strategy_row.confidence,
        "risk_score":            strategy_row.risk_score,
        "feasibility_score":     strategy_row.feasibility_score,
        "composite_score":       strategy_row.composite_score,
        "business_justification": strategy_row.business_justification,
        "technical_justification": strategy_row.technical_justification,
        "selection_reason":      strategy_row.selection_reason,
        "expected_downtime_min": strategy_row.expected_downtime_min,
        "requires_human_approval": strategy_row.requires_human_approval,
        "is_reversible":         strategy_row.is_reversible,
        "constraints": [
            {"type": c.constraint_type, "is_met": c.is_met, "details": c.details}
            for c in (strategy_row.constraints or [])
        ],
        "requirements": [
            {"type": r.requirement_type, "value": r.value}
            for r in (strategy_row.requirements or [])
        ],
        "reasons": [
            {"code": r.reason_code, "description": r.description, "category": r.category}
            for r in (strategy_row.reasons or [])
        ],
    }


def deserialize_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reverse of `serialize_strategy_snapshot` — used by LifecycleManager
    for rollback.  Always returns plain dicts.
    """
    return dict(snap)  # JSONB → dict, primitives only.


def restore_strategy_from_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compatibility shim — the LifecycleManager uses a `snap.get(...)` pattern
    to pull mutable fields back from the snapshot dict.  This helper makes
    that explicit and provides a single audit point for the rollback
    contract.

    Returns a flat dict of mutable fields that `rollback_to_version`
    applies back onto the ORM row.
    """
    return {
        "priority":               snap.get("priority", 100),
        "confidence":             snap.get("confidence", 0.0),
        "risk_score":             snap.get("risk_score", 0.0),
        "feasibility_score":      snap.get("feasibility_score", 0.0),
        "composite_score":        snap.get("composite_score", 0.0),
        "business_justification": snap.get("business_justification"),
        "technical_justification":snap.get("technical_justification"),
        "selection_reason":       snap.get("selection_reason"),
        "expected_downtime_min":  snap.get("expected_downtime_min", 0),
        "requires_human_approval":snap.get("requires_human_approval", False),
        "is_reversible":          snap.get("is_reversible", True),
    }