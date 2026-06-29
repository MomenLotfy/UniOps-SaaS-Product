"""
Integration tests for the Execution Orchestration Pipeline.

Covers the full 7-stage flow with mocked persistence:
  - Preparation → Readiness Validation → Dependency Resolution
    → Constraint Validation → Package Build → Statistics Update → Audit
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.security.execution_orchestration.constants import (
    ExecutionPackageState,
    ReadinessFactor,
    ReadinessOutcome,
)
from app.modules.security.execution_orchestration.services import (
    DEFAULT_READINESS_CHECKS,
    ExecutionAuditService,
    ExecutionCache,
    ExecutionConstraintValidator,
    ExecutionDependencyResolver,
    ExecutionLifecycleManager,
    ExecutionPackageBuilder,
    ExecutionPackageFactory,
    ExecutionPackageValidator,
    ExecutionPipeline,
    ExecutionPreparationService,
    ExecutionReadinessEngine,
    ExecutionRepository,
    ExecutionStatisticsService,
    bootstrap_default_readiness_checks,
)


def _make_db_mock():
    """AsyncMock-based DB stand-in with sync `add()` capture + async flush/commit/rollback."""
    db = AsyncMock()
    added = []
    # `db.add` must be a sync MagicMock so we can capture the object;
    # AsyncMock would auto-create an async one returning a coroutine.
    db.add = MagicMock(side_effect=lambda obj: added.append(obj))
    counter = {"i": 0}

    async def fake_flush():
        for obj in added:
            if not getattr(obj, "id", None):
                counter["i"] += 1
                obj.id = f"mock-id-{counter['i']}"
    db.flush = fake_flush
    db.added = added

    # Make `db.execute(...).scalar_one_or_none()` resolve to the most-recently
    # added row matching the WHERE filter — this is how the lifecycle manager
    # loads the current package state during a transition.  We can't fully
    # parse SQLAlchemy's WHERE clauses in tests, so we just return the latest
    # ExecutionPackage row; that is the row the lifecycle manager will be
    # transitioning in the happy path.
    async def fake_execute(*_args, **_kwargs):
        result = MagicMock()
        candidates = [
            o for o in added
            if type(o).__name__ in ("ExecutionPackage",)
            and getattr(o, "id", None)
        ]
        result.scalar_one_or_none.return_value = (
            candidates[-1] if candidates else None
        )
        return result
    db.execute = fake_execute
    return db


def _make_decision(tenant_id="tenant-1", decision_id="dec-1"):
    return SimpleNamespace(
        id=decision_id,
        tenant_id=tenant_id,
        decision_state="READY",
        final_result="PATCH",
        version=3,
        correlation_id="corr-1",
        trace_id="trace-1",
    )


def _make_strategy(tenant_id="tenant-1", strategy_id="str-1"):
    return SimpleNamespace(
        id=strategy_id,
        tenant_id=tenant_id,
        strategy_state="APPROVED",
        version=2,
    )


def _make_approval(tenant_id="tenant-1", approval_id="apr-1"):
    return SimpleNamespace(
        id=approval_id,
        tenant_id=tenant_id,
        approval_state="APPROVED",
        version=1,
    )


# ─────────────────────────────────────────────────────────────────────
#  Service construction + readiness defaults
# ─────────────────────────────────────────────────────────────────────
def test_all_twelve_readiness_factors_have_default_checks():
    """Every ReadinessFactor value must have a default check."""
    assert len(DEFAULT_READINESS_CHECKS) == 12
    factors = set(DEFAULT_READINESS_CHECKS.keys())
    expected = set(ReadinessFactor)
    assert factors == expected, f"Missing factors: {expected - factors}"


def test_pipeline_default_construction_smoke():
    db = _make_db_mock()
    pipeline = ExecutionPipeline(db)
    assert pipeline.readiness_engine is not None
    assert pipeline.dependency_resolver is not None
    assert pipeline.constraint_validator is not None
    assert pipeline.package_validator is not None
    assert pipeline.package_factory is not None
    assert pipeline.package_builder is not None
    assert pipeline.repository is not None
    assert pipeline.lifecycle_manager is not None
    assert pipeline.version_manager is not None
    assert pipeline.statistics_service is not None
    assert pipeline.audit_service is not None
    assert pipeline.cache is not None


# ─────────────────────────────────────────────────────────────────────
#  Preparation service
# ─────────────────────────────────────────────────────────────────────
def test_preparation_service_flags_missing_fields():
    svc = ExecutionPreparationService()
    bad_decision = SimpleNamespace(id=None, tenant_id="t1")
    snapshot = svc.prepare(bad_decision)
    assert snapshot.is_complete is False
    assert any("decision.id" in m for m in snapshot.missing_fields)


def test_preparation_service_happy_path():
    svc = ExecutionPreparationService()
    snapshot = svc.prepare(_make_decision(), _make_strategy(), _make_approval())
    assert snapshot.is_complete is True
    assert snapshot.tenant_id == "tenant-1"
    assert snapshot.decision_id == "dec-1"
    assert snapshot.strategy_id == "str-1"
    assert snapshot.approval_id == "apr-1"
    assert snapshot.decision_snapshot.get("tenant_id") == "tenant-1"
    assert snapshot.strategy_snapshot.get("strategy_state") == "APPROVED"


# ─────────────────────────────────────────────────────────────────────
#  Readiness engine — runs all 12 checks
# ─────────────────────────────────────────────────────────────────────
def test_readiness_engine_emits_one_verdict_per_factor():
    engine = bootstrap_default_readiness_checks(ExecutionReadinessEngine())
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionCandidateData,
    )
    candidate = ExecutionCandidateData(tenant_id="t1", decision_id="d1")
    context = SimpleNamespace(
        decision_state="READY",
        strategy_state="APPROVED",
        approval_state="APPROVED",
        tenant_id="t1",
        decision_snapshot={"tenant_id": "t1"},
    )
    verdicts = engine.run(candidate, context)
    assert len(verdicts) == 12
    assert candidate.readiness_total == 12


# ─────────────────────────────────────────────────────────────────────
#  Constraint validator — 12 constraints
# ─────────────────────────────────────────────────────────────────────
def test_constraint_validator_emits_one_constraint_per_type():
    validator = ExecutionConstraintValidator()
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionCandidateData,
        ReadinessFactorResult,
    )
    candidate = ExecutionCandidateData(tenant_id="t1", decision_id="d1")
    candidate.readiness_factors = [
        ReadinessFactorResult(
            factor=f,
            outcome=ReadinessOutcome.PASSED,
            rationale="ok",
        )
        for f in ReadinessFactor
    ]
    specs = validator.validate(candidate, SimpleNamespace())
    assert len(specs) == 12
    assert all(s.is_met for s in specs)


# ─────────────────────────────────────────────────────────────────────
#  Factory + Validator
# ─────────────────────────────────────────────────────────────────────
def test_factory_rejects_when_snapshot_incomplete():
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionPreparationSnapshot,
    )
    factory = ExecutionPackageFactory()
    snapshot = ExecutionPreparationSnapshot(
        tenant_id="t1", decision_id="", is_complete=False, missing_fields=["decision.id"],
    )
    candidate = factory.build_candidate(snapshot)
    assert candidate.is_valid is False
    assert candidate.rejection_reason is not None


def test_factory_builds_candidate_when_complete():
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionPreparationSnapshot,
    )
    factory = ExecutionPackageFactory()
    snapshot = ExecutionPreparationSnapshot(
        tenant_id="t1", decision_id="d1", strategy_id="s1", approval_id="a1",
        decision_snapshot={"version": 1, "correlation_id": "corr"},
        strategy_snapshot={"version": 2},
        approval_snapshot={"version": 3},
        is_complete=True,
    )
    candidate = factory.build_candidate(
        snapshot,
        metadata=[("rollback_strategy", "git revert")],
        requirements=[],
        summary="A test summary",
    )
    assert candidate.is_valid is True
    assert candidate.decision_version == 1
    assert candidate.strategy_version == 2
    assert candidate.approval_version == 3
    assert ("rollback_strategy", "git revert") in candidate.metadata


def test_validator_flags_failed_readiness():
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionCandidateData,
        ReadinessFactorResult,
    )
    from app.modules.security.execution_orchestration.constants import (
        ExecutionRejectionReason,
    )
    candidate = ExecutionCandidateData(tenant_id="t1", decision_id="d1")
    candidate.readiness_factors = [
        ReadinessFactorResult(
            factor=ReadinessFactor.TENANT_ISOLATION,
            outcome=ReadinessOutcome.FAILED,
            rationale="tenant mismatch",
        )
    ]
    errs = ExecutionPackageValidator().validate(candidate)
    assert ExecutionRejectionReason.TENANT_ISOLATION_BROKEN.value in errs


# ─────────────────────────────────────────────────────────────────────
#  Serializer round-trip
# ─────────────────────────────────────────────────────────────────────
def test_serializer_round_trip_preserves_candidate():
    from app.modules.security.execution_orchestration.services import (
        ExecutionPackageSerializer,
    )
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionCandidateData,
        ReadinessFactorResult,
    )
    cand = ExecutionCandidateData(
        tenant_id="t1", decision_id="d1", strategy_id="s1", approval_id="a1",
        decision_version=1, summary="hello",
    )
    cand.readiness_factors = [
        ReadinessFactorResult(
            factor=ReadinessFactor.DECISION_READY,
            outcome=ReadinessOutcome.PASSED,
            rationale="ok",
        )
    ]
    # Serializer reads candidate.readiness_total/passed/etc which are
    # normally populated by the readiness engine; for the round-trip
    # test we set them explicitly.
    cand.readiness_total = 1
    cand.readiness_passed = 1
    cand.readiness_warned = 0
    cand.readiness_failed = 0
    payload = ExecutionPackageSerializer().to_dict(cand)
    assert payload["decision_id"] == "d1"
    assert payload["readiness"]["total"] == 1
    assert payload["readiness"]["verdicts"][0]["factor"] == "DECISION_READY"


# ─────────────────────────────────────────────────────────────────────
#  Cache
# ─────────────────────────────────────────────────────────────────────
def test_cache_get_put_invalidate():
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionEvaluationResult,
    )
    cache = ExecutionCache(ttl_seconds=60)
    result = ExecutionEvaluationResult(tenant_id="t1", decision_id="d1")
    cache.put("t1", "d1", SimpleNamespace(raw_data={"a": 1}), result)
    cached = cache.get("t1", "d1", SimpleNamespace(raw_data={"a": 1}))
    assert cached is result
    cache.invalidate("t1")
    assert cache.get("t1", "d1", SimpleNamespace(raw_data={"a": 1})) is None


# ─────────────────────────────────────────────────────────────────────
#  Lifecycle transitions
# ─────────────────────────────────────────────────────────────────────
def test_lifecycle_transitions_are_validated():
    from app.modules.security.execution_orchestration.constants import (
        ExecutionPackageState,
    )
    db = MagicMock()
    mgr = ExecutionLifecycleManager(db)
    assert mgr.can_transition(ExecutionPackageState.CREATED, ExecutionPackageState.READINESS_VALIDATING)
    assert not mgr.can_transition(ExecutionPackageState.ARCHIVED, ExecutionPackageState.READY)
    assert not mgr.can_transition(ExecutionPackageState.READY, ExecutionPackageState.CREATED)


# ─────────────────────────────────────────────────────────────────────
#  Pipeline — happy path persists all 12 model types
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pipeline_happy_path_persists_all_models():
    db = _make_db_mock()

    # Stub external services to avoid touching DB.
    repo = ExecutionRepository(db)
    repo.get_statistics = AsyncMock(return_value={})
    repo.list_history = AsyncMock(return_value=[])
    repo.list_audit = AsyncMock(return_value=[])

    stats = ExecutionStatisticsService(db)
    stats.record = AsyncMock(return_value=None)

    audit = ExecutionAuditService(db)
    audit.record = AsyncMock(return_value=None)

    pipeline = ExecutionPipeline(
        db,
        package_builder=ExecutionPackageBuilder(db),
        repository=repo,
        statistics_service=stats,
        audit_service=audit,
        cache=ExecutionCache(),  # ensure cache enabled but disabled below
    )

    decision = _make_decision()
    strategy = _make_strategy()
    approval = _make_approval()

    result = await pipeline.run(
        decision, strategy=strategy, approval=approval,
        raw_data={
            "repository_id": "repo-1",
            "asset_id": "asset-1",
            "policy_compliance": "PASSED",
            "environment": "PROD",
            "target_environment": "PROD",
            "execution_window_open": True,
        },
        metadata=[("rollback_strategy", "git revert"), ("owner", "sec-team")],
        summary="Test summary",
    )

    assert result.candidate is not None
    assert result.package_id is not None
    assert result.final_state in (
        ExecutionPackageState.READY, ExecutionPackageState.REJECTED,
    )

    added = db.added
    kinds = {type(obj).__name__ for obj in added}
    expected = {
        "ExecutionPackage",
        "ExecutionPreparation",
        "ExecutionReadiness",
        "ExecutionDependency",
        "ExecutionConstraint",
        "ExecutionRequirement",
        "ExecutionMetadata",
        "ExecutionHistory",
        "ExecutionAudit",
        "ExecutionSummary",
    }
    missing = expected - kinds
    assert not missing, f"Missing model rows: {missing}"


# ─────────────────────────────────────────────────────────────────────
#  Pipeline — rejection path persists a rejected package
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pipeline_rejects_when_tenant_mismatch():
    db = _make_db_mock()

    repo = ExecutionRepository(db)
    repo.get_statistics = AsyncMock(return_value={})
    stats = ExecutionStatisticsService(db)
    stats.record = AsyncMock(return_value=None)
    audit = ExecutionAuditService(db)
    audit.record = AsyncMock(return_value=None)

    # Build a custom readiness engine that fails TENANT_ISOLATION always.
    class AlwaysFailTenant(ExecutionReadinessEngine):
        def __init__(self):
            super().__init__(checks=dict(DEFAULT_READINESS_CHECKS))
        def run(self, candidate, context):  # override entire flow
            from app.modules.security.execution_orchestration.services.execution_interfaces import (
                ReadinessFactorResult,
            )
            from app.modules.security.execution_orchestration.constants import (
                ReadinessFactor, ReadinessOutcome,
            )
            verdicts = []
            for f in ReadinessFactor:
                outcome = (
                    ReadinessOutcome.FAILED
                    if f == ReadinessFactor.TENANT_ISOLATION
                    else ReadinessOutcome.PASSED
                )
                verdicts.append(ReadinessFactorResult(
                    factor=f, outcome=outcome, rationale="forced",
                ))
            candidate.readiness_factors = verdicts
            candidate.readiness_total = len(verdicts)
            candidate.readiness_failed = 1
            return verdicts

    pipeline = ExecutionPipeline(
        db,
        readiness_engine=AlwaysFailTenant(),
        repository=repo,
        statistics_service=stats,
        audit_service=audit,
    )

    decision = _make_decision(tenant_id="t1")
    strategy = _make_strategy(tenant_id="t1")
    approval = _make_approval(tenant_id="t1")

    result = await pipeline.run(decision, strategy=strategy, approval=approval)
    assert result.final_state == ExecutionPackageState.REJECTED
    assert result.package_id is not None  # rejected packages still get persisted