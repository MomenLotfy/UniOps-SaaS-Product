"""
Integration tests for the Decision Approval Pipeline.

Covers the full 7-stage flow with mocked persistence:
  - Discovery → Context Build → Requirement Resolve → Policy Evaluation
    → Validation → Persistence → Statistics + Audit
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.security.decision_approval.services import (
    ApprovalEngine,
    ApprovalEvaluationPipeline,
    ApprovalLifecycleManager,
    ApprovalRepository,
    ApprovalStatisticsService,
    ApprovalAuditService,
)


@pytest.mark.asyncio
async def test_approval_pipeline_persists_request_and_supports():
    # Arrange: in-memory DB stand-in
    db = AsyncMock()

    decision = SimpleNamespace(
        id="dec-1",
        tenant_id="tenant-1",
        plan_id="plan-1",
        final_result="PATCH",
        correlation_id="corr-1",
        trace_id="trace-1",
    )
    context = SimpleNamespace(
        tenant_id="tenant-1",
        raw_data={
            "asset_id": "asset-1",
            "repo_id": "repo-1",
            "fixed_version": "2.0.1",
            "package_name": "lodash",
            "cvss_score": 8.5,
            "epss_score": 0.7,
        },
    )

    # Capture every ORM row that gets `add()`-ed; also fake id population on flush.
    # `db.add` must be a sync MagicMock so we can capture the object;
    # AsyncMock would auto-create an async one returning a coroutine.
    added = []
    db.add = MagicMock(side_effect=lambda obj: added.append(obj))
    counter = {"i": 0}

    async def fake_flush():
        for obj in added:
            if not getattr(obj, "id", None):
                counter["i"] += 1
                obj.id = f"mock-id-{counter['i']}"

    db.flush = fake_flush

    # Stub repository methods that touch the DB
    async def fake_get_statistics(tenant_id):
        return {}
    async def fake_save_evaluation(result):
        return SimpleNamespace(id="eval-1")

    repo = ApprovalRepository(db)
    repo.get_statistics = fake_get_statistics
    repo.save_evaluation = fake_save_evaluation

    stats = ApprovalStatisticsService(db)
    stats.record_evaluation = AsyncMock(return_value=None)
    stats.record_transition = AsyncMock(return_value=None)

    audit = ApprovalAuditService(db)
    audit.record = AsyncMock(return_value=None)

    engine = ApprovalEngine(cache_enabled=False)
    pipeline = ApprovalEvaluationPipeline(db, engine=engine)
    pipeline.repository = repo
    pipeline.statistics = stats
    pipeline.audit = audit

    # Act
    result = await pipeline.run(decision, strategy=None, tenant_id="tenant-1")

    # Assert
    assert result.candidate is not None
    assert result.candidate.requires_approval is True
    assert result.winning_request_id is not None

    # Many rows should have been added
    kinds = [type(obj).__name__ for obj in added]
    assert "ApprovalRequest" in kinds
    assert "ApprovalRequirement" in kinds
    assert "ApprovalConstraint" in kinds
    assert "ApprovalEvidence" in kinds
    assert "ApprovalReason" in kinds
    assert "ApprovalHistory" in kinds
    assert "ApprovalAudit" in kinds


@pytest.mark.asyncio
async def test_approval_pipeline_auto_rejects_critical():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def fake_get_statistics(tenant_id):
        return {}
    async def fake_save_evaluation(result):
        return SimpleNamespace(id="eval-2")

    repo = ApprovalRepository(db)
    repo.get_statistics = fake_get_statistics
    repo.save_evaluation = fake_save_evaluation

    stats = ApprovalStatisticsService(db)
    stats.record_evaluation = AsyncMock(return_value=None)
    audit = ApprovalAuditService(db)
    audit.record = AsyncMock(return_value=None)

    engine = ApprovalEngine(cache_enabled=False)
    pipeline = ApprovalEvaluationPipeline(db, engine=engine)
    pipeline.repository = repo
    pipeline.statistics = stats
    pipeline.audit = audit

    decision = SimpleNamespace(
        id="d-crit", tenant_id="t-crit", plan_id=None,
        final_result="PATCH", correlation_id="c", trace_id="tr",
    )
    result = await pipeline.run(
        decision, strategy=None,
        tenant_id="t-crit",
        raw_data={"cvss_score": 9.9, "business_criticality": 0.5},
    )
    assert result.candidate is not None
    assert result.candidate.auto_reject is True


@pytest.mark.asyncio
async def test_lifecycle_manager_records_history_on_transition():
    from app.modules.security.decision_approval.constants import ApprovalState

    db = AsyncMock()
    db.flush = AsyncMock()

    strategy = SimpleNamespace(
        id="str-1",
        tenant_id="tenant-1",
        approval_state=ApprovalState.WAITING_APPROVAL,
        version=1,
        correlation_id="corr-1",
        trace_id="trace-1",
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = strategy
    db.execute = AsyncMock(return_value=result_mock)

    mgr = ApprovalLifecycleManager(db)
    await mgr.transition_to if False else await mgr.transition(
        strategy_id="str-1",
        to_state=ApprovalState.APPROVED,
        changed_by="tester",
        reason="unit test",
    ) if False else None

    # Use the actual signature: transition(request_id, to_state, ...)
    await mgr.transition(
        request_id="str-1",
        to_state=ApprovalState.APPROVED,
        changed_by="tester",
        reason="unit test",
    )

    added = [c.args[0] for c in db.add.call_args_list]
    assert any(getattr(o, "to_state", None) is not None for o in added)


@pytest.mark.asyncio
async def test_lifecycle_rejects_invalid_transition():
    from app.modules.security.decision_approval.constants import ApprovalState
    db = AsyncMock()
    db.flush = AsyncMock()
    strategy = SimpleNamespace(
        id="str-2",
        tenant_id="tenant-1",
        approval_state=ApprovalState.ARCHIVED,  # terminal
        correlation_id="corr-2",
        trace_id="trace-2",
    )
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = strategy
    db.execute = AsyncMock(return_value=result_mock)

    mgr = ApprovalLifecycleManager(db)
    # R19: typed InvalidApprovalTransitionError (subclasses ValueError).
    from app.core.exceptions import InvalidApprovalTransitionError
    with pytest.raises((ValueError, InvalidApprovalTransitionError)):
        await mgr.transition(
            request_id="str-2",
            to_state=ApprovalState.APPROVED,
            changed_by="tester",
        )


@pytest.mark.asyncio
async def test_pipeline_handles_emergency_override():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def fake_get_statistics(tenant_id):
        return {}
    async def fake_save_evaluation(result):
        return SimpleNamespace(id="eval-3")

    repo = ApprovalRepository(db)
    repo.get_statistics = fake_get_statistics
    repo.save_evaluation = fake_save_evaluation

    stats = ApprovalStatisticsService(db)
    stats.record_evaluation = AsyncMock(return_value=None)
    audit = ApprovalAuditService(db)
    audit.record = AsyncMock(return_value=None)

    engine = ApprovalEngine(cache_enabled=False)
    pipeline = ApprovalEvaluationPipeline(db, engine=engine)
    pipeline.repository = repo
    pipeline.statistics = stats
    pipeline.audit = audit

    decision = SimpleNamespace(
        id="d-em", tenant_id="t-em", plan_id=None,
        final_result="PATCH", correlation_id="c", trace_id="tr",
    )
    result = await pipeline.run(
        decision, strategy=None, tenant_id="t-em",
        raw_data={"cvss_score": 7.0, "emergency": True},
    )
    assert result.candidate is not None
    roles = [r.role.value for r in result.candidate.requirements]
    assert "EMERGENCY_OVERRIDE" in roles
    assert "SECURITY_TEAM" in roles
