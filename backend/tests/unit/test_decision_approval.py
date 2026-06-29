"""
Unit tests for the Decision Approval Engine.

Covers:
  - Constants + state-transition matrix
  - Registry + 12 default policies
  - Resolver + scoring engine
  - Validator
  - Cache
  - Serializer round-trip
  - Engine end-to-end (in-memory)
  - Context builder
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.security.decision_approval.constants import (
    AUTOMATIC_APPROVAL_THRESHOLD,
    AUTOMATIC_REJECTION_THRESHOLD,
    ApprovalActorRole,
    ApprovalOutcome,
    ApprovalRequirementMode,
    ApprovalState,
    ApprovalType,
    VALID_APPROVAL_TRANSITIONS,
)
from app.modules.security.decision_approval.services import (
    ApprovalCache,
    ApprovalContext,
    ApprovalContextBuilder,
    ApprovalEngine,
    ApprovalFactory,
    ApprovalPolicyEngine,
    ApprovalRegistry,
    ApprovalResolver,
    ApprovalScoringEngine,
    ApprovalValidator,
    ApprovalLifecycleManager,
    AutomationEvaluator,
    ComplianceEvaluator,
    CriticalityEvaluator,
    HistoryEvaluator,
    OwnerEvaluator,
    RiskEvaluator,
    UrgencyEvaluator,
    DEFAULT_APPROVAL_EVALUATORS,
    DEFAULT_APPROVAL_POLICIES,
    bootstrap_default_approval_policies,
    deserialize_candidate,
    serialize_candidate,
)
from app.modules.security.decision_approval.services.approval_interfaces import (
    ApprovalCandidateData,
    ApprovalEvaluationResult,
    ApprovalPolicyResult,
)


# ─────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────
def test_approval_state_enum_has_nine_states():
    assert {s.name for s in ApprovalState} == {
        "CREATED", "VALIDATING", "WAITING_APPROVAL", "PARTIALLY_APPROVED",
        "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", "ARCHIVED",
    }


def test_valid_approval_transitions_matrix_completeness():
    # Every state except ARCHIVED must have at least one valid next state.
    for state in ApprovalState:
        if state == ApprovalState.ARCHIVED:
            assert VALID_APPROVAL_TRANSITIONS[state] == []
        else:
            assert len(VALID_APPROVAL_TRANSITIONS[state]) > 0
    # None entry must produce CREATED.
    assert VALID_APPROVAL_TRANSITIONS[None] == [ApprovalState.CREATED]


def test_thresholds_are_in_unit_interval():
    assert 0.0 <= AUTOMATIC_APPROVAL_THRESHOLD < AUTOMATIC_REJECTION_THRESHOLD <= 1.0


# ─────────────────────────────────────────────────────────────────────
#  Registry + policies
# ─────────────────────────────────────────────────────────────────────
def test_registry_bootstrap_registers_twelve_policies():
    registry = ApprovalRegistry()
    bootstrap_default_approval_policies(registry)
    assert len(registry.all()) == 12
    assert "default" in registry.names()
    assert "high_risk_security" in registry.names()
    assert "emergency" in registry.names()


def test_registry_register_rejects_blank_name():
    registry = ApprovalRegistry()

    class _Blank:
        name = ""
        version = 1
        description = ""
        def is_applicable(self, ctx): return False
        def requires_approval(self, ctx): return False
        def required_approvers(self, ctx): return []
        def evaluate(self, ctx): return ApprovalPolicyResult(requires_approval=False)

    # R19: now raises the typed ValidationError (which is also a
    # ValueError via project exception hierarchy).
    from app.core.exceptions import ValidationError as _ValidationError
    with pytest.raises((ValueError, _ValidationError)):
        registry.register(_Blank())


def test_registry_unregister_removes_policy():
    registry = ApprovalRegistry()
    bootstrap_default_approval_policies(registry)
    registry.unregister("default")
    assert "default" not in registry.names()


def test_registry_applicable_filters_by_context():
    registry = ApprovalRegistry()
    bootstrap_default_approval_policies(registry)
    ctx = SimpleNamespace(raw_data={"cvss_score": 8.5, "environment": "production"})
    applicable = registry.applicable(ctx)
    # high_risk_security, production_environment, default all apply for high CVSS in production
    names = [p.name for p in applicable]
    assert "high_risk_security" in names
    assert "production_environment" in names


# ─────────────────────────────────────────────────────────────────────
#  Resolver + scoring
# ─────────────────────────────────────────────────────────────────────
def test_resolver_aggregate_unions_roles():
    registry = ApprovalRegistry()
    bootstrap_default_approval_policies(registry)
    resolver = ApprovalResolver(registry)
    a = ApprovalPolicyResult(requires_approval=True, required_roles=[ApprovalActorRole.SECURITY_TEAM])
    b = ApprovalPolicyResult(requires_approval=True, required_roles=[ApprovalActorRole.PLATFORM_TEAM])
    agg = resolver.aggregate([a, b])
    assert ApprovalActorRole.SECURITY_TEAM in agg.required_roles
    assert ApprovalActorRole.PLATFORM_TEAM in agg.required_roles
    assert agg.requires_approval is True


def test_resolver_aggregate_auto_rejection_wins():
    resolver = ApprovalResolver(ApprovalRegistry())
    a = ApprovalPolicyResult(requires_approval=True,  required_roles=[ApprovalActorRole.SECURITY_TEAM])
    b = ApprovalPolicyResult(requires_approval=False, required_roles=[], auto_reject=True)
    agg = resolver.aggregate([a, b])
    assert agg.auto_reject is True
    assert agg.requires_approval is False


def test_scoring_engine_returns_classification():
    engine = ApprovalScoringEngine()
    ctx = SimpleNamespace(raw_data={"cvss_score": 9.0, "business_criticality": 0.9})
    result = engine.score(ctx)
    assert "composite" in result
    assert result["classification"] in {"AUTO_REJECT", "REQUIRES_APPROVAL", "AUTO_APPROVE"}


def test_scoring_engine_low_risk_auto_approves():
    engine = ApprovalScoringEngine()
    # Override history so it stays low, and force urgency = 0 via emergency=False.
    ctx = SimpleNamespace(raw_data={"cvss_score": 0.0, "business_criticality": 0.0, "emergency": False, "compliance_required": False})
    # Force history evaluator to 0
    for ev in engine._evaluators:
        if hasattr(ev, "set_history"):
            ev.set_history(0.0)
    result = engine.score(ctx)
    assert result["classification"] in {"AUTO_APPROVE", "REQUIRES_APPROVAL"}
    assert result["composite"] < AUTOMATIC_REJECTION_THRESHOLD


def test_default_evaluators_present():
    names = {e.name for e in DEFAULT_APPROVAL_EVALUATORS}
    assert names == {"risk", "criticality", "compliance", "urgency", "history", "automation", "owner"}


def test_history_evaluator_can_be_recalibrated():
    ev = HistoryEvaluator(history_score=0.5)
    ctx = SimpleNamespace(raw_data={})
    assert ev.evaluate(ctx) == 0.5
    ev.set_history(0.8)
    assert ev.evaluate(ctx) == 0.8


# ─────────────────────────────────────────────────────────────────────
#  Validator
# ─────────────────────────────────────────────────────────────────────
def test_validator_flags_missing_decision():
    v = ApprovalValidator()
    cand = ApprovalCandidateData(
        decision_id="",
        strategy_id=None,
        tenant_id="t",
        approval_type=ApprovalType.SECURITY,
        requirement_mode=ApprovalRequirementMode.SINGLE,
    )
    errors = v.validate(cand, None)
    assert "MISSING_DECISION" in errors


def test_validator_flags_missing_approver():
    v = ApprovalValidator()
    cand = ApprovalCandidateData(
        decision_id="d",
        strategy_id=None,
        tenant_id="t",
        approval_type=ApprovalType.SECURITY,
        requirement_mode=ApprovalRequirementMode.SINGLE,
        requires_approval=True,
        requirements=[],
    )
    errors = v.validate(cand, None)
    assert "MISSING_APPROVER" in errors


def test_validator_passes_valid_candidate():
    v = ApprovalValidator()
    from app.modules.security.decision_approval.services.approval_interfaces import ApprovalRequirementSpec
    cand = ApprovalCandidateData(
        decision_id="d",
        strategy_id=None,
        tenant_id="t",
        approval_type=ApprovalType.SECURITY,
        requirement_mode=ApprovalRequirementMode.SINGLE,
        requirements=[ApprovalRequirementSpec(role=ApprovalActorRole.SECURITY_TEAM)],
    )
    assert v.validate(cand, None) == []


# ─────────────────────────────────────────────────────────────────────
#  Cache
# ─────────────────────────────────────────────────────────────────────
def test_cache_round_trip():
    cache = ApprovalCache(ttl_seconds=60)
    result = ApprovalEvaluationResult(
        tenant_id="t", decision_id="d", strategy_id=None,
        candidate=None, evaluation_duration_ms=0,
    )
    cache.put("t", "d", SimpleNamespace(raw_data={}), result)
    hit = cache.get("t", "d", SimpleNamespace(raw_data={}))
    assert hit is result


def test_cache_invalidate_by_tenant():
    cache = ApprovalCache(ttl_seconds=60)
    cache.put("t1", "d", SimpleNamespace(raw_data={}), ApprovalEvaluationResult(tenant_id="t1", decision_id="d", strategy_id=None, candidate=None))
    cache.put("t2", "d", SimpleNamespace(raw_data={}), ApprovalEvaluationResult(tenant_id="t2", decision_id="d", strategy_id=None, candidate=None))
    cache.invalidate("t1")
    assert cache.get("t1", "d", SimpleNamespace(raw_data={})) is None
    assert cache.get("t2", "d", SimpleNamespace(raw_data={})) is not None


# ─────────────────────────────────────────────────────────────────────
#  Serializer
# ─────────────────────────────────────────────────────────────────────
def test_serializer_round_trip():
    from app.modules.security.decision_approval.services.approval_interfaces import ApprovalRequirementSpec
    cand = ApprovalCandidateData(
        decision_id="d",
        strategy_id="s",
        tenant_id="t",
        approval_type=ApprovalType.SECURITY,
        requirement_mode=ApprovalRequirementMode.SEQUENTIAL,
        requirements=[
            ApprovalRequirementSpec(role=ApprovalActorRole.SECURITY_TEAM, sequence_order=1),
            ApprovalRequirementSpec(role=ApprovalActorRole.PLATFORM_TEAM, sequence_order=2),
        ],
        reasons=[("CODE", "desc")],
        constraints=[("C", True, "ok")],
        evidence=[("E", "v")],
        risk_score=0.7,
        criticality_score=0.8,
        composite_score=0.5,
        confidence=0.9,
        requires_approval=True,
        correlation_id="corr",
        trace_id="trace",
    )
    blob = serialize_candidate(cand)
    restored = deserialize_candidate(blob)
    assert restored.decision_id == cand.decision_id
    assert restored.tenant_id == cand.tenant_id
    assert restored.requirement_mode == cand.requirement_mode
    assert len(restored.requirements) == 2
    assert restored.risk_score == cand.risk_score


# ─────────────────────────────────────────────────────────────────────
#  Context builder
# ─────────────────────────────────────────────────────────────────────
def test_context_builder_uses_decision_tenant():
    cb = ApprovalContextBuilder()
    decision = SimpleNamespace(id="d", tenant_id="T1", raw_data={"cvss_score": 5.0})
    ctx = cb.build(decision)
    assert isinstance(ctx, ApprovalContext)
    assert ctx.tenant_id == "T1"
    assert ctx.raw_data["cvss_score"] == 5.0


def test_context_builder_derives_approval_type():
    cb = ApprovalContextBuilder()
    d_patch  = SimpleNamespace(id="d", tenant_id="T", final_result="PATCH")
    d_mit    = SimpleNamespace(id="d", tenant_id="T", final_result="MITIGATE")
    d_review = SimpleNamespace(id="d", tenant_id="T", final_result="REVIEW")
    assert cb.derive_approval_type(d_patch, None)  == ApprovalType.SECURITY
    assert cb.derive_approval_type(d_mit, None)    == ApprovalType.PLATFORM
    assert cb.derive_approval_type(d_review, None) == ApprovalType.BUSINESS


# ─────────────────────────────────────────────────────────────────────
#  Engine end-to-end
# ─────────────────────────────────────────────────────────────────────
def test_engine_selects_high_risk_security_policy_for_high_cvss():
    engine = ApprovalEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d1", tenant_id="t1", plan_id="p1", final_result="PATCH", correlation_id="c", trace_id="tr")
    context = SimpleNamespace(tenant_id="t1", raw_data={"cvss_score": 8.0, "epss_score": 0.9})
    result = engine.evaluate(decision, context=context, raw_data={"cvss_score": 8.0})
    assert result.candidate is not None
    assert result.candidate.requires_approval is True
    roles = [r.role for r in result.candidate.requirements]
    assert ApprovalActorRole.SECURITY_TEAM in roles
    assert ApprovalActorRole.PLATFORM_TEAM in roles


def test_engine_auto_approves_low_risk():
    engine = ApprovalEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d2", tenant_id="t2", plan_id=None, final_result="PATCH")
    # Truly low-risk: cvss below 0.4 and crit below 0.3 → low_risk_automatic applies
    result = engine.evaluate(
        decision,
        raw_data={"cvss_score": 0.1, "business_criticality": 0.05, "environment": "development"},
    )
    assert result.candidate is not None
    assert result.candidate.requires_approval is False
    assert result.candidate.auto_approve is True


def test_engine_auto_rejects_critical_risk():
    engine = ApprovalEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d3", tenant_id="t3", plan_id=None, final_result="PATCH")
    result = engine.evaluate(
        decision,
        raw_data={"cvss_score": 9.8, "business_criticality": 0.5},
    )
    assert result.candidate is not None
    assert result.candidate.auto_reject is True


def test_engine_emergency_requires_override_approver():
    engine = ApprovalEngine(cache_enabled=False)
    decision = SimpleNamespace(id="d4", tenant_id="t4", plan_id=None, final_result="PATCH")
    result = engine.evaluate(
        decision,
        raw_data={"cvss_score": 7.0, "emergency": True},
    )
    assert result.candidate is not None
    roles = [r.role for r in result.candidate.requirements]
    assert ApprovalActorRole.EMERGENCY_OVERRIDE in roles
    assert ApprovalActorRole.SECURITY_TEAM in roles


def test_engine_cache_hit_returns_same_result():
    engine = ApprovalEngine(cache_enabled=True)
    decision = SimpleNamespace(id="d5", tenant_id="t5", plan_id=None, final_result="PATCH")
    raw = {"cvss_score": 5.0, "business_criticality": 0.5}
    ctx = SimpleNamespace(tenant_id="t5", raw_data=raw)
    first = engine.evaluate(decision, context=ctx, raw_data=raw)
    second = engine.evaluate(decision, context=ctx, raw_data=raw)
    assert first is second


# ─────────────────────────────────────────────────────────────────────
#  Policy engine
# ─────────────────────────────────────────────────────────────────────
def test_policy_engine_returns_all_applicable_policies():
    pe = ApprovalPolicyEngine()
    ctx = SimpleNamespace(raw_data={"cvss_score": 9.5, "environment": "production"})
    policies = pe.applicable_policies(ctx)
    names = [p.name for p in policies]
    assert "high_risk_security" in names
    assert "production_environment" in names


def test_factory_build_candidate_populates_requirements():
    factory = ApprovalFactory()
    decision = SimpleNamespace(id="d", tenant_id="t", correlation_id="c", trace_id="tr")
    ctx = SimpleNamespace(raw_data={}, tenant_id="t")
    verdict = ApprovalPolicyResult(
        requires_approval=True,
        required_roles=[ApprovalActorRole.SECURITY_TEAM, ApprovalActorRole.PLATFORM_TEAM],
        requirement_mode=ApprovalRequirementMode.SEQUENTIAL,
        risk_score=0.5,
        criticality_score=0.7,
        confidence=0.9,
        reasons=[("R", "desc")],
    )
    cand = factory.build_candidate(decision, ctx, verdict, approval_type=ApprovalType.SECURITY, scoring={"composite": 0.6})
    assert len(cand.requirements) == 2
    assert cand.requirement_mode == ApprovalRequirementMode.SEQUENTIAL