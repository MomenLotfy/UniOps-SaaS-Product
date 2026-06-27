import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.security.decision_engine.services.rule_engine import RuleEngine
from app.modules.security.decision_engine.services.policy_engine import PolicyEngine
from app.modules.security.decision_engine.services.policy_repository import PolicyRepository
from app.modules.security.decision_engine.models.policy import DecisionPolicy, PolicyStatus

@pytest.mark.asyncio
async def test_rule_engine_evaluation():
    # Mock DB and Repository
    db = AsyncMock()
    mock_repo = AsyncMock()

    # Define a mock rule
    mock_rule = MagicMock()
    mock_rule.name = "Test Rule"
    mock_rule.priority = 1
    mock_rule.eval_order = 0
    mock_rule.short_circuit = False

    # Mock condition: risk.score > 10
    mock_cond = MagicMock()
    mock_cond.children = None
    mock_cond.field_path = "risk.score"
    mock_cond.operator = "GT" # RuleOperator.GREATER_THAN
    mock_cond.expected_value = "10"
    mock_rule.conditions = [mock_cond]

    # Mock action: SET_RESULT = MITIGATE
    mock_action = MagicMock()
    mock_action.action_type = "SET_RESULT"
    mock_action.action_value = "MITIGATE"
    mock_rule.actions = [mock_action]

    mock_repo.get_active_rules.return_value = [mock_rule]

    engine = RuleEngine(db, mock_repo)

    # Context data that matches the rule
    context = MagicMock()
    context.tenant_id = "tenant-1"
    context.raw_data = {"risk": {"score": 15}}

    result, plans, reasons = await engine.evaluate(context)

    assert result == "MITIGATE"
    assert len(reasons) == 0 # In the implementation provided, SET_RESULT doesn't add reason

@pytest.mark.asyncio
async def test_policy_engine_override():
    db = AsyncMock()
    mock_repo = AsyncMock()

    # Mock a mandatory policy for critical-infra
    mock_policy = MagicMock()
    mock_policy.id = "pol-1"
    mock_policy.name = "Critical Infra Policy"
    mock_policy.is_mandatory = True
    mock_policy.category = "critical-infra"
    mock_policy.scope = {"type": "tenant", "id": "tenant-1"}

    mock_repo.resolve_effective_policy.return_value = mock_policy

    engine = PolicyEngine(db)
    engine.repository = mock_repo

    context = MagicMock()
    context.tenant_id = "tenant-1"
    context.raw_data = {"asset_id": "asset-1", "org_id": "org-1"}

    # Technical result is MONITOR, but policy is critical-infra -> should override to MITIGATE
    final_result, reasons, resolution = await engine.apply_policy(
        context=context,
        technical_result="MONITOR",
        reasons=[]
    )

    assert final_result == "MITIGATE"
    assert resolution.overridden is True
    assert "Mandatory Infrastructure Policy Override" in resolution.reason
