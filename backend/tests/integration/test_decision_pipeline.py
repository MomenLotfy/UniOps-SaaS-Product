"""
Integration tests for the Decision Pipeline.

Sprint 1 R3+R4 update: the engine now operates on the *existing*
aggregate — `engine.determine_decision(decision, context)` mutates
`decision.final_result` in place and returns `(decision, plans,
reasons, resolution)`.  The test stubs that contract by making the
mocked engine set `decision.final_result` as a side effect.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.security.decision_engine.services.decision_pipeline import DecisionPipeline
from app.modules.security.decision_engine.services.context_builder import DecisionContextBuilder
from app.modules.security.decision_engine.services.decision_validator import DecisionValidator
from app.modules.security.decision_engine.services.decision_engine import DecisionEngine
from app.modules.security.decision_engine.services.decision_manager import DecisionManager
from app.modules.security.decision_engine.services.statistics_service import StatisticsService
from app.modules.security.decision_engine.models.decision import Decision
from app.modules.security.decision_engine.models.context import DecisionContext


@pytest.mark.asyncio
async def test_decision_pipeline_full_flow():
    db = AsyncMock()

    # Mock dependencies
    context_builder = AsyncMock(spec=DecisionContextBuilder)
    validator = AsyncMock(spec=DecisionValidator)
    engine = AsyncMock(spec=DecisionEngine)
    manager = AsyncMock(spec=DecisionManager)
    stats_service = AsyncMock(spec=StatisticsService)

    # Mock context
    mock_context = DecisionContext(
        id="ctx-1",
        tenant_id="tenant-1",
        correlation_id="corr-1",
        raw_data={"asset_id": "asset-1"},
    )
    context_builder.build_context.return_value = mock_context

    # Mock validator — accept the request
    validator.validate_request.return_value = (True, None)

    # Mock manager — return a fresh Decision aggregate
    mock_decision = Decision(id="dec-1", tenant_id="tenant-1", correlation_id="corr-1")
    manager.create_decision.return_value = mock_decision
    manager.transition_to = AsyncMock()

    # Mock engine — R3+R4 contract: takes the existing aggregate,
    # mutates it in place, returns it back along with plans/reasons.
    async def fake_determine(decision, context):
        decision.final_result = "MITIGATE"
        # Return a non-empty plan + reasons tuple so the pipeline's
        # Stage 5 (persistence) can add them to the session.
        from app.modules.security.decision_engine.models.plan import DecisionPlan
        from app.modules.security.decision_engine.models.evidence import DecisionReason
        plan = DecisionPlan(
            id="plan-1", decision_id=decision.id, execution_order=1,
            tenant_id=decision.tenant_id, correlation_id=decision.correlation_id,
        )
        reason = DecisionReason(
            id="reason-1", decision_id=decision.id, reason_code="POLICY_RESOLUTION",
            description="Resolved via Test Policy: Override",
            tenant_id=decision.tenant_id, correlation_id=decision.correlation_id,
        )
        return decision, [plan], [reason], MagicMock(
            policy_id="pol-1", overridden=True,
            policy_name="Test Policy", reason="Override",
        )
    engine.determine_decision.side_effect = fake_determine

    pipeline = DecisionPipeline(
        db, context_builder, validator, engine, manager, stats_service,
    )

    result = await pipeline.execute("tenant-1", "finding-1", "corr-1")

    # R4: the returned aggregate is the persisted one with final_result set
    assert result.id == "dec-1"
    assert result.final_result == "MITIGATE"

    # R3: state transitions went through the manager
    assert manager.transition_to.called

    # R4: stats were recorded for the terminal READY state
    assert stats_service.record_decision_stats.called
    assert stats_service.record_policy_stats.called

    # R4: the transaction was committed (not rolled back)
    assert db.commit.called
    assert not db.rollback.called