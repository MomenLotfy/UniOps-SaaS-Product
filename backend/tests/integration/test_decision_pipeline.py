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
        raw_data={"asset_id": "asset-1"}
    )
    context_builder.build_context.return_value = mock_context

    # Mock validator
    validator.validate_request.return_value = (True, None)

    # Mock decision engine result
    mock_decision_obj = Decision(id="dec-1", final_result="MITIGATE", status="READY")
    engine.determine_decision.return_value = (
        mock_decision_obj,
        [],
        [],
        MagicMock(policy_id="pol-1", overridden=True, policy_name="Test Policy", reason="Override")
    )

    # Mock manager
    mock_decision = Decision(id="dec-1")
    manager.create_decision.return_value = mock_decision
    manager.transition_to = AsyncMock()

    pipeline = DecisionPipeline(db, context_builder, validator, engine, manager, stats_service)

    result = await pipeline.execute("tenant-1", "finding-1", "corr-1")

    assert result.final_result == "MITIGATE"
    assert manager.transition_to.called
    assert stats_service.record_decision_stats.called
    assert stats_service.record_policy_stats.called
    assert db.commit.called
