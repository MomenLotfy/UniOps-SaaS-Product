"""
Strategy Scoring Engine.

Pure deterministic scoring across the 10 dimensions defined in
`constants.SCORING_WEIGHTS`.  Each dimension is a small helper that
returns a tuple (value, rationale).

A score of 0.0 means "this strategy is bad along this dimension";
1.0 means "ideal".  Values are clamped to [0.0, 1.0].

The composite score is the weighted sum:
    composite = Σ (weight_i * value_i)

The engine is *stateless* and contains no DB or network code — it
operates entirely on the inputs it is given.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ..constants import SCORING_WEIGHTS, StrategyType
from .strategy_interfaces import (
    IStrategyScoringEngine,
    StrategyCandidateData,
    StrategyScoreBreakdown,
)


# ── Dimension helpers (each returns (value, rationale)) ────────────────────

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def _score_feasibility(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """
    Higher when the strategy is easier to execute:
      - has all hard constraints met
      - has rollback path
      - has known target
    """
    if not c.is_valid:
        return 0.0, "Invalid candidate — constraints broken"

    score = 0.0
    if c.is_reversible:
        score += 0.4
    if ctx.get("fixed_version") or ctx.get("target"):
        score += 0.3
    if ctx.get("asset_id") or ctx.get("repo_id"):
        score += 0.2
    # No human approval -> more feasible
    if not c.requires_human_approval:
        score += 0.1
    return _clamp01(score), "feasibility from reversibility+metadata+automation"


def _score_risk_reduction(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """
    Higher when the strategy is likely to actually reduce risk.

    Sourced from the decision context's risk/severity fields:
      - cvss_score     → normalized 0..10
      - exploitability → 0..1 (EPSS-like)
      - severity       → text bucketed
    """
    cvss = ctx.get("cvss_score")
    if isinstance(cvss, (int, float)) and cvss > 0:
        cvss_norm = _clamp01(float(cvss) / 10.0)
    else:
        cvss_norm = 0.5  # unknown — neutral

    epss = ctx.get("epss_score")
    if isinstance(epss, (int, float)):
        epss_norm = _clamp01(float(epss))
    else:
        epss_norm = 0.3

    # PATCH/UPGRADE removes the vulnerability entirely; mitigation
    # reduces it partially; NO_ACTION removes none.
    if c.candidate_type in {
        StrategyType.PATCH_EXISTING_VERSION,
        StrategyType.UPGRADE_PACKAGE,
        StrategyType.IMAGE_REPLACEMENT,
        StrategyType.OS_PACKAGE_UPDATE,
        StrategyType.CONTAINER_UPDATE,
        StrategyType.REPLACE_DEPENDENCY,
    }:
        base = 0.95
    elif c.candidate_type in {
        StrategyType.CONFIGURATION_CHANGE,
        StrategyType.POLICY_CHANGE,
        StrategyType.SECRET_ROTATION,
        StrategyType.CERTIFICATE_ROTATION,
    }:
        base = 0.75
    elif c.candidate_type == StrategyType.TEMPORARY_MITIGATION:
        base = 0.5
    elif c.candidate_type == StrategyType.NO_ACTION:
        base = 0.0
    else:
        base = 0.4

    value = _clamp01(base * 0.5 + cvss_norm * 0.25 + epss_norm * 0.25)
    return value, f"risk reduction base={base:.2f} cvss={cvss_norm:.2f} epss={epss_norm:.2f}"


def _score_automation_readiness(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """Higher when no human is in the loop."""
    if c.requires_human_approval:
        return 0.2, "Requires human approval"
    if c.candidate_type in {
        StrategyType.MANUAL_REVIEW_REQUIRED, StrategyType.VENDOR_PATCH_REQUIRED
    }:
        return 0.0, "Manual / vendor-driven strategy"
    return 0.95, "Fully automatable"


def _score_rollback_difficulty(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """Inverse of rollback difficulty — higher = easier rollback."""
    if not c.is_reversible:
        return 0.2, "Non-reversible strategy"
    if c.candidate_type in {
        StrategyType.DISABLE_FEATURE, StrategyType.CONFIGURATION_CHANGE,
        StrategyType.POLICY_CHANGE, StrategyType.TEMPORARY_MITIGATION,
    }:
        return 0.95, "Trivially reversible"
    if c.candidate_type in {
        StrategyType.PATCH_EXISTING_VERSION, StrategyType.UPGRADE_PACKAGE,
        StrategyType.OS_PACKAGE_UPDATE, StrategyType.SECRET_ROTATION,
        StrategyType.CERTIFICATE_ROTATION,
    }:
        return 0.85, "Reversible with redeploy"
    return 0.6, "Reversible with effort"


def _score_expected_downtime(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """Inverse of expected downtime in minutes — higher = less downtime."""
    down = c.expected_downtime_min
    if down <= 0:
        return 1.0, "Zero downtime"
    if down <= 5:
        return 0.9, f"{down}min downtime"
    if down <= 15:
        return 0.7, f"{down}min downtime"
    if down <= 30:
        return 0.5, f"{down}min downtime"
    if down <= 60:
        return 0.3, f"{down}min downtime"
    return 0.1, f"{down}min downtime (significant)"


def _score_business_impact(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """
    Higher when business impact (asset criticality × environment) is high,
    because remediation of critical assets should be prioritised.
    """
    crit = (ctx.get("asset_criticality") or "").lower()
    crit_score = {
        "critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2,
    }.get(crit, 0.5)

    env = (ctx.get("environment") or "").lower()
    env_score = {"production": 1.0, "staging": 0.5, "development": 0.2}.get(env, 0.5)

    return _clamp01(crit_score * 0.6 + env_score * 0.4), \
           f"criticality={crit_score:.2f} env={env_score:.2f}"


def _score_compliance_impact(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """
    Higher when compliance frameworks require action.

    ctx.compliance is a comma-separated list of framework names.
    """
    frameworks = ctx.get("compliance") or ""
    if isinstance(frameworks, list):
        names = [x.strip().lower() for x in frameworks]
    else:
        names = [x.strip().lower() for x in str(frameworks).split(",") if x.strip()]

    if not names:
        return 0.4, "No compliance context"

    high_value_frameworks = {"pci", "hipaa", "soc2", "gdpr", "fedramp", "iso27001"}
    hits = sum(1 for n in names if any(h in n for h in high_value_frameworks))
    return _clamp01(0.4 + min(hits, 3) * 0.2), f"frameworks={names}"


def _score_historical_success(c: StrategyCandidateData, ctx: dict,
                              stats: Dict) -> Tuple[float, str]:
    """
    Higher when the same strategy_type has historically performed well.

    `stats[strategy_type] = {"success_rate": 0..1, "count": int}` or empty.
    Cold start (no history) returns 0.5 — neutral prior.
    """
    st = c.candidate_type
    rec = stats.get(st) if stats else None
    if not rec:
        return 0.5, "no historical data"
    rate = float(rec.get("success_rate", 0.5))
    n = int(rec.get("count", 0))
    # Discount when sample is tiny — Bayesian-style shrinkage to 0.5.
    weight = min(1.0, n / 20.0)
    value = 0.5 * (1 - weight) + rate * weight
    return _clamp01(value), f"rate={rate:.2f} n={n}"


def _score_cost(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """
    Inverse of cost.  Lower cost → higher score.
    Cost model is intentionally simple (deterministic, no I/O).
    """
    cost_map = {
        StrategyType.NO_ACTION:                0,
        StrategyType.DISABLE_FEATURE:          1,
        StrategyType.CONFIGURATION_CHANGE:     2,
        StrategyType.POLICY_CHANGE:            2,
        StrategyType.TEMPORARY_MITIGATION:     3,
        StrategyType.SECRET_ROTATION:          3,
        StrategyType.CERTIFICATE_ROTATION:     3,
        StrategyType.PATCH_EXISTING_VERSION:   4,
        StrategyType.UPGRADE_PACKAGE:          5,
        StrategyType.DOWNGRADE_PACKAGE:        5,
        StrategyType.OS_PACKAGE_UPDATE:        5,
        StrategyType.CONTAINER_UPDATE:         6,
        StrategyType.IMAGE_REPLACEMENT:        7,
        StrategyType.REPLACE_DEPENDENCY:       8,
        StrategyType.INFRASTRUCTURE_CHANGE:    9,
        StrategyType.MANUAL_REVIEW_REQUIRED:   6,
        StrategyType.VENDOR_PATCH_REQUIRED:    6,
    }
    cost = cost_map.get(c.candidate_type, 5)
    return _clamp01(1.0 - (cost / 10.0)), f"cost={cost}/10"


def _score_complexity(c: StrategyCandidateData, ctx: dict) -> Tuple[float, str]:
    """
    Inverse of operational complexity — higher = simpler.
    """
    simple_types = {
        StrategyType.NO_ACTION,
        StrategyType.DISABLE_FEATURE,
        StrategyType.CONFIGURATION_CHANGE,
        StrategyType.POLICY_CHANGE,
        StrategyType.SECRET_ROTATION,
        StrategyType.CERTIFICATE_ROTATION,
        StrategyType.PATCH_EXISTING_VERSION,
    }
    if c.candidate_type in simple_types:
        return 0.9, "Low complexity"
    if c.candidate_type in {
        StrategyType.UPGRADE_PACKAGE,
        StrategyType.OS_PACKAGE_UPDATE,
        StrategyType.CONTAINER_UPDATE,
        StrategyType.IMAGE_REPLACEMENT,
        StrategyType.TEMPORARY_MITIGATION,
    }:
        return 0.6, "Moderate complexity"
    return 0.3, "High complexity"


# ── Engine ──────────────────────────────────────────────────────────────────

class StrategyScoringEngine(IStrategyScoringEngine):
    """Stateless — safe to share across requests."""

    DIMENSION_FUNCS = {
        "feasibility":          _score_feasibility,
        "risk_reduction":       _score_risk_reduction,
        "automation_readiness": _score_automation_readiness,
        "rollback_difficulty":  _score_rollback_difficulty,
        "expected_downtime":    _score_expected_downtime,
        "business_impact":      _score_business_impact,
        "compliance_impact":    _score_compliance_impact,
        "historical_success":   _score_historical_success,
        "cost":                 _score_cost,
        "complexity":           _score_complexity,
    }

    def score(
        self,
        candidate: StrategyCandidateData,
        decision: Any,
        context: Any,
        statistics: Dict,
    ) -> StrategyCandidateData:
        ctx = context.raw_data if hasattr(context, "raw_data") else (context or {})

        composite = 0.0
        feasibility = 0.0

        for dimension, weight in SCORING_WEIGHTS.items():
            func = self.DIMENSION_FUNCS[dimension]
            if dimension == "historical_success":
                value, rationale = func(candidate, ctx, statistics)
            else:
                value, rationale = func(candidate, ctx)
            value = _clamp01(value)
            candidate.add_score(
                StrategyScoreBreakdown(
                    dimension=dimension,
                    value=value,
                    weight=weight,
                    rationale=rationale,
                )
            )
            composite += value * weight
            if dimension == "feasibility":
                feasibility = value

        candidate.composite_score   = round(composite, 6)
        candidate.feasibility_score = round(feasibility, 6)
        return candidate