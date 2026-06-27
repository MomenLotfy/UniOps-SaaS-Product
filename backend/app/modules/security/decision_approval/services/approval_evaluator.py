"""
Approval Scoring Engine.

Computes a deterministic composite score (0.0–1.0) for a context by
combining the registered factor evaluators with `APPROVAL_SCORING_WEIGHTS`.

Mirrors `StrategyScoringEngine`.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..constants import APPROVAL_SCORING_WEIGHTS, AUTOMATIC_APPROVAL_THRESHOLD, AUTOMATIC_REJECTION_THRESHOLD
from .approval_interfaces import IApprovalEvaluator


class RiskEvaluator(IApprovalEvaluator):
    """max(CVSS, EPSS), normalized to [0,1]."""
    name = "risk"

    def evaluate(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        cvss = 0.0
        epss = 0.0
        try:
            cvss = float(raw.get("cvss_score", 0.0) or 0.0) / 10.0
        except (TypeError, ValueError):
            cvss = 0.0
        try:
            epss = float(raw.get("epss_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            epss = 0.0
        return max(0.0, min(1.0, max(cvss, epss)))


class CriticalityEvaluator(IApprovalEvaluator):
    """business_criticality from raw_data, default 0.5."""
    name = "criticality"

    def evaluate(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        try:
            return max(0.0, min(1.0, float(raw.get("business_criticality", 0.5) or 0.5)))
        except (TypeError, ValueError):
            return 0.5


class ComplianceEvaluator(IApprovalEvaluator):
    """1.0 if compliance framework set, else 0.0."""
    name = "compliance"

    def evaluate(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        return 1.0 if (raw.get("compliance_framework") or raw.get("compliance_required")) else 0.0


class UrgencyEvaluator(IApprovalEvaluator):
    """1.0 if emergency, 0.5 otherwise; CVSS boosts it."""
    name = "urgency"

    def evaluate(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        if raw.get("emergency") or raw.get("emergency_mode"):
            return 1.0
        try:
            cvss = float(raw.get("cvss_score", 0.0) or 0.0) / 10.0
        except (TypeError, ValueError):
            cvss = 0.0
        return max(0.0, min(1.0, cvss))


class HistoryEvaluator(IApprovalEvaluator):
    """Tenant's historical approval rate for the same approval_type."""
    name = "history"

    def __init__(self, history_score: float = 0.5) -> None:
        self._history = max(0.0, min(1.0, history_score))

    def set_history(self, score: float) -> None:
        self._history = max(0.0, min(1.0, score))

    def evaluate(self, context: Any) -> float:
        return self._history


class AutomationEvaluator(IApprovalEvaluator):
    """1.0 if strategy is fully automated, 0.0 if manual only."""
    name = "automation"

    def evaluate(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        auto = bool(raw.get("automation_ready") or raw.get("auto_remediation"))
        return 1.0 if auto else 0.0


class OwnerEvaluator(IApprovalEvaluator):
    """1.0 if at least one owner is assigned."""
    name = "owner"

    def evaluate(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        fields = ("business_owner", "application_owner", "repository_owner")
        for f in fields:
            if raw.get(f):
                return 1.0
        return 0.0


DEFAULT_APPROVAL_EVALUATORS: List[IApprovalEvaluator] = [
    RiskEvaluator(),
    CriticalityEvaluator(),
    ComplianceEvaluator(),
    UrgencyEvaluator(),
    HistoryEvaluator(),
    AutomationEvaluator(),
    OwnerEvaluator(),
]


class ApprovalScoringEngine:
    """Weighted-sum scorer — deterministic, no LLM in the loop."""

    def __init__(self, evaluators: List[IApprovalEvaluator] = None) -> None:
        self._evaluators = evaluators or list(DEFAULT_APPROVAL_EVALUATORS)
        self._weights = dict(APPROVAL_SCORING_WEIGHTS)

    def score(self, context: Any) -> Dict[str, float]:
        """Return {evaluator_name: score, composite: float, classification: str}."""
        per_factor: Dict[str, float] = {}
        for ev in self._evaluators:
            try:
                per_factor[ev.name] = float(ev.evaluate(context))
            except Exception:  # pragma: no cover - evaluator failure is non-fatal
                per_factor[ev.name] = 0.0
        composite = sum(
            per_factor.get(name, 0.0) * self._weights.get(name, 0.0)
            for name in self._weights
        )
        composite = max(0.0, min(1.0, composite))
        if composite >= AUTOMATIC_REJECTION_THRESHOLD:
            classification = "AUTO_REJECT"
        elif composite <= AUTOMATIC_APPROVAL_THRESHOLD:
            classification = "AUTO_APPROVE"
        else:
            classification = "REQUIRES_APPROVAL"
        return {**per_factor, "composite": composite, "classification": classification}


__all__ = [
    "ApprovalScoringEngine",
    "AutomationEvaluator",
    "ComplianceEvaluator",
    "CriticalityEvaluator",
    "DEFAULT_APPROVAL_EVALUATORS",
    "HistoryEvaluator",
    "OwnerEvaluator",
    "RiskEvaluator",
    "UrgencyEvaluator",
]
