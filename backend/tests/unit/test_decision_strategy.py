"""
Unit tests for the Decision Strategy Engine.

Covers:
  - Registry bootstrap (17 default strategies)
  - Scoring engine determinism + value clamping
  - Comparator ordering (composite > feasibility > validity > type)
  - Ranking engine produces 1-based ranks
  - Selector falls back to NO_ACTION
  - Validator emits canonical rejection reasons
  - Full engine.evaluate() end-to-end in-memory

All tests are pure-Python — no DB, no network.
"""
from types import SimpleNamespace

import pytest

from app.modules.security.decision_strategy import (
    DecisionStrategyComparator,
    DecisionStrategyEngine,
    DecisionStrategyRegistry,
    DecisionStrategyValidator,
    StrategyRankingEngine,
    StrategyScoringEngine,
    bootstrap_default_strategies,
)
from app.modules.security.decision_strategy.constants import (
    RejectionReason,
    StrategyState,
    StrategyType,
)
from app.modules.security.decision_strategy.services.strategy_interfaces import (
    StrategyCandidateData,
    StrategyScoreBreakdown,
)


# ── Registry ─────────────────────────────────────────────────────────
def test_bootstrap_registers_all_17_strategies():
    reg = DecisionStrategyRegistry()
    bootstrap_default_strategies(reg)
    assert len(reg.all()) == 17

    # Spot-check canonical names
    assert reg.get(StrategyType.PATCH_EXISTING_VERSION) is not None
    assert reg.get(StrategyType.NO_ACTION) is not None
    assert reg.get(StrategyType.TEMPORARY_MITIGATION) is not None


def test_registry_discover_only_applicable_descriptors():
    reg = DecisionStrategyRegistry()
    bootstrap_default_strategies(reg)

    decision = SimpleNamespace(id="d1", tenant_id="t1", final_result="PATCH")

    # No patch info: only NO_ACTION + MANUAL_REVIEW + TEMPORARY_MITIGATION apply
    context = SimpleNamespace(raw_data={})
    applicable = reg.discover(decision, context)
    types = {d.strategy_type for d in applicable}
    assert StrategyType.NO_ACTION in types
    assert StrategyType.MANUAL_REVIEW_REQUIRED in types
    assert StrategyType.TEMPORARY_MITIGATION in types
    assert StrategyType.PATCH_EXISTING_VERSION not in types


def test_register_custom_strategy():
    """Registry is the documented extension point."""
    reg = DecisionStrategyRegistry()

    class _Custom(IStrategyDescriptor := __import__(
        "app.modules.security.decision_strategy.services.strategy_interfaces",
        fromlist=["IStrategyDescriptor"],
    ).IStrategyDescriptor):
        strategy_type = StrategyType.NO_ACTION  # will be overridden

        def applicable(self, decision, context):
            return True

        def hard_constraints(self, decision, context):
            return []

        def base_requirements(self, decision, context):
            return []

    reg.register(StrategyType.NO_ACTION, _Custom())
    assert reg.get(StrategyType.NO_ACTION) is not None


# ── Scoring ──────────────────────────────────────────────────────────
def test_scoring_engine_produces_10_dimensions():
    engine = StrategyScoringEngine()
    cand = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION)
    ctx = SimpleNamespace(raw_data={"fixed_version": "1.2.3", "asset_id": "a"})
    engine.score(cand, SimpleNamespace(id="d"), ctx, statistics={})

    assert len(cand.scores) == 10
    dimensions = {s.dimension for s in cand.scores}
    expected = {
        "feasibility", "risk_reduction", "automation_readiness",
        "rollback_difficulty", "expected_downtime", "business_impact",
        "compliance_impact", "historical_success", "cost", "complexity",
    }
    assert dimensions == expected
    assert 0.0 <= cand.composite_score <= 1.0
    assert 0.0 <= cand.feasibility_score <= 1.0


def test_scoring_is_deterministic():
    """Same inputs MUST produce the same scores (no randomness/time)."""
    engine = StrategyScoringEngine()
    cand1 = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION)
    cand2 = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION)
    ctx = SimpleNamespace(raw_data={"fixed_version": "1.2.3"})

    engine.score(cand1, SimpleNamespace(id="d"), ctx, statistics={})
    engine.score(cand2, SimpleNamespace(id="d"), ctx, statistics={})

    assert cand1.composite_score == cand2.composite_score
    assert cand1.feasibility_score == cand2.feasibility_score
    assert len(cand1.scores) == len(cand2.scores)


def test_score_breakdown_contribution_property():
    s = StrategyScoreBreakdown(dimension="feasibility", value=0.8, weight=0.5)
    assert s.contribution == pytest.approx(0.4)


def test_no_action_scores_low_risk_reduction():
    engine = StrategyScoringEngine()
    cand = StrategyCandidateData(candidate_type=StrategyType.NO_ACTION)
    ctx = SimpleNamespace(raw_data={"cvss_score": 9.8})
    engine.score(cand, SimpleNamespace(id="d"), ctx, statistics={})
    rr = next(s for s in cand.scores if s.dimension == "risk_reduction")
    assert rr.value < 0.5


# ── Comparator ───────────────────────────────────────────────────────
def test_comparator_orders_by_composite_desc():
    cmp_ = DecisionStrategyComparator()
    a = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION, composite_score=0.9)
    b = StrategyCandidateData(candidate_type=StrategyType.UPGRADE_PACKAGE,       composite_score=0.7)
    assert cmp_.compare(a, b) == -1
    assert cmp_.compare(b, a) == 1


def test_comparator_uses_feasibility_as_first_tiebreaker():
    cmp_ = DecisionStrategyComparator()
    a = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION, composite_score=0.9, feasibility_score=0.6)
    b = StrategyCandidateData(candidate_type=StrategyType.UPGRADE_PACKAGE,       composite_score=0.9, feasibility_score=0.4)
    assert cmp_.compare(a, b) == -1


def test_comparator_uses_validity_as_second_tiebreaker():
    cmp_ = DecisionStrategyComparator()
    a = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION,
                              composite_score=0.9, feasibility_score=0.6, is_valid=True)
    b = StrategyCandidateData(candidate_type=StrategyType.UPGRADE_PACKAGE,
                              composite_score=0.9, feasibility_score=0.6, is_valid=False)
    assert cmp_.compare(a, b) == -1


def test_comparator_breaks_ties_alphabetically():
    cmp_ = DecisionStrategyComparator()
    a = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION,
                              composite_score=0.9, feasibility_score=0.6, is_valid=True)
    b = StrategyCandidateData(candidate_type=StrategyType.UPGRADE_PACKAGE,
                              composite_score=0.9, feasibility_score=0.6, is_valid=True)
    assert cmp_.compare(a, b) == -1   # PATCH_EXISTING_VERSION < UPGRADE_PACKAGE alphabetically


# ── Ranking ──────────────────────────────────────────────────────────
def test_ranking_assigns_one_based_ranks_to_valid_only():
    ranker = StrategyRankingEngine()
    valid   = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION,
                                    composite_score=0.8, is_valid=True)
    invalid = StrategyCandidateData(candidate_type=StrategyType.INFRASTRUCTURE_CHANGE,
                                    composite_score=0.5, is_valid=False,
                                    rejection_reason=RejectionReason.BROKEN_CONSTRAINT)
    out = ranker.rank([invalid, valid])
    assert out[0] is valid
    assert out[0].rank == 1
    assert out[1] is invalid
    assert out[1].rank is None


# ── Validator ────────────────────────────────────────────────────────
def test_validator_marks_broken_constraints():
    validator = DecisionStrategyValidator()
    cand = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION)
    cand.constraints = [{"type": "PATCH_AVAILABLE", "is_met": False}]
    validator.validate(cand)
    assert cand.is_valid is False
    assert cand.rejection_reason == RejectionReason.BROKEN_CONSTRAINT


def test_validator_passes_when_constraints_met():
    validator = DecisionStrategyValidator()
    cand = StrategyCandidateData(candidate_type=StrategyType.PATCH_EXISTING_VERSION)
    cand.constraints = [
        {"type": "PATCH_AVAILABLE",      "is_met": True},
        {"type": "REPOSITORY_PRESENT",   "is_met": True},
    ]
    validator.validate(cand)
    assert cand.is_valid is True
    assert cand.rejection_reason is None


# ── Engine ───────────────────────────────────────────────────────────
def test_engine_picks_patch_when_fixed_version_present():
    engine = DecisionStrategyEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d1", tenant_id="t1", final_result="PATCH", plan_id="p1")
    context = SimpleNamespace(raw_data={
        "asset_id": "a1", "fixed_version": "2.0.1", "package_name": "lodash",
        "cvss_score": 9.8, "epss_score": 0.9,
        "asset_criticality": "critical", "environment": "production",
        "compliance": "pci,soc2",
    })
    result = engine.evaluate(decision, context)
    assert result.winner is not None
    assert result.winner.candidate_type == StrategyType.PATCH_EXISTING_VERSION
    assert result.winner.rank == 1


def test_engine_falls_back_to_no_action():
    engine = DecisionStrategyEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d2", tenant_id="t1", final_result="IGNORE")
    context = SimpleNamespace(raw_data={})
    result = engine.evaluate(decision, context)
    assert result.winner is not None
    assert result.winner.candidate_type == StrategyType.NO_ACTION


def test_engine_returns_invalid_candidates_in_audit():
    """Invalid candidates are kept at the end with rank=None."""
    engine = DecisionStrategyEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d3", tenant_id="t1", final_result="PATCH")
    context = SimpleNamespace(raw_data={"asset_id": "a1"})  # no fixed_version, no package
    result = engine.evaluate(decision, context)
    invalid = [c for c in result.candidates if not c.is_valid]
    assert all(c.rank is None for c in invalid)


def test_engine_cache_returns_same_result():
    engine = DecisionStrategyEngine(cache_enabled=True)
    decision = SimpleNamespace(id="d4", tenant_id="t1", final_result="PATCH", plan_id="p1")
    context = SimpleNamespace(raw_data={
        "asset_id": "a1", "fixed_version": "1.0",
    })
    r1 = engine.evaluate(decision, context)
    r2 = engine.evaluate(decision, context)
    # Same object identity proves the cache short-circuit
    assert r1 is r2


def test_engine_ranking_is_stable_across_calls():
    """Two evaluations of the same context yield the same ranking order."""
    engine = DecisionStrategyEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d5", tenant_id="t1", final_result="PATCH")
    context = SimpleNamespace(raw_data={
        "asset_id": "a1", "fixed_version": "1.0", "package_name": "x",
    })

    r1 = engine.evaluate(decision, context)
    r2 = engine.evaluate(decision, context)

    types1 = [c.candidate_type for c in r1.candidates]
    types2 = [c.candidate_type for c in r2.candidates]
    assert types1 == types2
    assert r1.winner.candidate_type == r2.winner.candidate_type


def test_engine_invalidate_clears_cache():
    engine = DecisionStrategyEngine(cache_enabled=True)
    decision = SimpleNamespace(id="d6", tenant_id="t1", final_result="PATCH", plan_id="p1")
    context = SimpleNamespace(raw_data={"asset_id": "a1", "fixed_version": "1.0"})
    engine.evaluate(decision, context)
    n = engine._cache.invalidate("t1")
    assert n >= 1