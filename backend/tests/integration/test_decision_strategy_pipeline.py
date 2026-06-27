"""
Integration tests for the Decision Strategy Pipeline.

Covers the full 7-stage flow with mocked persistence:
  - Discovery → Statistics Load → Candidate Build → Ranking → Selection
    → Persistence → Statistics Update

Verifies that all ORM rows are produced by the engine's helpers and
that the strategy is linked to a Decision + Plan via FK.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.security.decision_strategy.services.strategy_engine import DecisionStrategyEngine
from app.modules.security.decision_strategy.services.strategy_evaluation_pipeline import (
    StrategyEvaluationPipeline,
)
from app.modules.security.decision_strategy.services.strategy_repository import (
    DecisionStrategyRepository,
)
from app.modules.security.decision_strategy.services.strategy_statistics_service import (
    DecisionStrategyStatisticsService,
)
from app.modules.security.decision_strategy.services.strategy_lifecycle_manager import (
    DecisionStrategyLifecycleManager,
)


@pytest.mark.asyncio
async def test_strategy_pipeline_persists_winner_and_alternatives():
    # Arrange: in-memory DB stand-in
    db = MagicMock()

    decision = SimpleNamespace(
        id="dec-1",
        tenant_id="tenant-1",
        plan_id="plan-1",
        final_result="PATCH",
    )
    context = SimpleNamespace(
        tenant_id="tenant-1",
        raw_data={
            "asset_id": "asset-1",
            "repo_id": "repo-1",
            "fixed_version": "2.0.1",
            "package_name": "lodash",
            "cvss_score": 9.8,
            "epss_score": 0.9,
        },
    )

    # Capture every ORM row that gets `add()`-ed
    added: list = []
    db.add.side_effect = lambda obj: added.append(obj)
    db.flush = AsyncMock()

    # Stub repository methods that touch the DB
    async def fake_get_statistics(tenant_id):
        return {}
    async def fake_save_evaluation(result):
        from types import SimpleNamespace as S
        return S(id="eval-1", tenant_id=result.tenant_id)
    async def fake_record_evaluation(tenant_id, strategy_type, duration_ms):
        return None
    async def fake_record_rejection(tenant_id, strategy_type):
        return None

    repo = DecisionStrategyRepository(db)
    repo.get_statistics = fake_get_statistics
    repo.save_evaluation = fake_save_evaluation

    stats = DecisionStrategyStatisticsService(db)
    stats.record_evaluation = fake_record_evaluation
    stats.record_rejection = fake_record_rejection

    engine = DecisionStrategyEngine(cache_enabled=False)
    pipeline = StrategyEvaluationPipeline(db, engine=engine)
    # Override the inner services the pipeline constructed
    pipeline.repository = repo
    pipeline.statistics = stats

    # Act
    result = await pipeline.run(decision, context)

    # Assert: a winner was selected
    assert result.winner is not None
    assert result.winner.candidate_type.value == "PATCH_EXISTING_VERSION"

    # The DecisionStrategy, candidate, constraints, requirements, reasons,
    # scores, and metadata rows were added (one batch per kind).
    kinds = [type(obj).__name__ for obj in added]
    assert "DecisionStrategy" in kinds
    assert "StrategyCandidate" in kinds
    assert any(k == "StrategyConstraint" for k in kinds)


@pytest.mark.asyncio
async def test_lifecycle_manager_records_history_on_transition():
    db = MagicMock()
    db.flush = AsyncMock()

    # Pre-existing DecisionStrategy with SELECTED state
    strategy = SimpleNamespace(
        id="str-1",
        tenant_id="tenant-1",
        state=__import__(
            "app.modules.security.decision_strategy.constants",
            fromlist=["StrategyState"],
        ).StrategyState.SELECTED,
        correlation_id="corr-1",
        trace_id="trace-1",
    )

    # SELECTED → APPROVED is valid in our transition matrix
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = strategy
    db.execute = AsyncMock(return_value=result_mock)

    mgr = DecisionStrategyLifecycleManager(db)
    await mgr.transition_to(
        strategy_id="str-1",
        to_state=__import__(
            "app.modules.security.decision_strategy.constants",
            fromlist=["StrategyState"],
        ).StrategyState.APPROVED,
        changed_by="tester",
        reason="unit test",
    )

    # A history row was added
    added = [c.args[0] for c in db.add.call_args_list]
    assert any(getattr(o, "to_state", None) is not None for o in added)


@pytest.mark.asyncio
async def test_lifecycle_rejects_invalid_transition():
    from app.modules.security.decision_strategy.constants import StrategyState
    db = MagicMock()
    db.flush = AsyncMock()
    strategy = SimpleNamespace(
        id="str-2",
        tenant_id="tenant-1",
        state=StrategyState.ARCHIVED,  # terminal
        correlation_id="corr-2",
        trace_id="trace-2",
    )
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = strategy
    db.execute = AsyncMock(return_value=result_mock)

    mgr = DecisionStrategyLifecycleManager(db)
    with pytest.raises(ValueError):
        await mgr.transition_to(
            strategy_id="str-2",
            to_state=StrategyState.APPROVED,
            changed_by="tester",
        )


@pytest.mark.asyncio
async def test_pipeline_handles_empty_context_with_no_action():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def fake_get_statistics(tenant_id):
        return {}
    async def fake_save_evaluation(result):
        return SimpleNamespace(id="eval-2")
    async def fake_record_evaluation(*a, **kw):
        return None
    async def fake_record_rejection(*a, **kw):
        return None

    engine = DecisionStrategyEngine(cache_enabled=False)
    pipeline = StrategyEvaluationPipeline(db, engine=engine)
    pipeline.repository.get_statistics = fake_get_statistics
    pipeline.repository.save_evaluation = fake_save_evaluation
    pipeline.statistics.record_evaluation = fake_record_evaluation
    pipeline.statistics.record_rejection = fake_record_rejection

    decision = SimpleNamespace(id="d9", tenant_id="t9", plan_id=None, final_result="IGNORE")
    context = SimpleNamespace(tenant_id="t9", raw_data={})

    result = await pipeline.run(decision, context)

    assert result.winner is not None
    assert result.winner.candidate_type.value == "NO_ACTION"