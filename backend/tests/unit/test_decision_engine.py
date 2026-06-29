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


# ─────────────────────────────────────────────────────────────────────
#  Sprint 1 R3 — DecisionEngine must never create a new aggregate
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r3_engine_never_creates_new_decision_aggregate():
    """
    R3 contract: ``determine_decision`` MUST mutate the passed-in
    aggregate and return the SAME instance.  It must never construct
    a fresh ``Decision(status="READY", ...)`` row.
    """
    from unittest.mock import patch
    from app.modules.security.decision_engine.services.decision_engine import DecisionEngine
    from app.modules.security.decision_engine.models.decision import Decision
    from app.modules.security.decision_engine.models.context import DecisionContext
    from app.modules.security.decision_engine.models.plan import DecisionPlan
    from app.modules.security.decision_engine.models.evidence import DecisionReason

    db = AsyncMock()

    re_mock = AsyncMock()
    re_mock.evaluate.return_value = ("MITIGATE", [], [])
    pe_mock = AsyncMock()
    pe_mock.apply_policy.return_value = (
        "MITIGATE",
        [],
        MagicMock(policy_id="pol-1", overridden=False,
                  policy_name="P", reason="r"),
    )

    # Patch the imports inside the engine module so the per-call
    # RuleEngine / PolicyEngine instances are our AsyncMocks.
    with patch(
        "app.modules.security.decision_engine.services.decision_engine.RuleEngine",
        return_value=re_mock,
    ), patch(
        "app.modules.security.decision_engine.services.decision_engine.PolicyEngine",
        return_value=pe_mock,
    ):
        engine = DecisionEngine(db)

        existing = Decision(
            id="dec-existing",
            tenant_id="tenant-1",
            correlation_id="corr-1",
            context_id="ctx-1",
        )
        context = DecisionContext(
            id="ctx-1", tenant_id="tenant-1",
            correlation_id="corr-1", raw_data={},
        )

        returned_dec, plans, reasons, _ = await engine.determine_decision(
            existing, context,
        )

    # R3: same aggregate is returned, no orphan
    assert returned_dec is existing
    assert existing.final_result == "MITIGATE"
    # R3: status was NEVER set to READY by the engine
    assert existing.status != "READY"
    # R4: plans/reasons FK the persisted decision
    for p in plans:
        assert isinstance(p, DecisionPlan)
        assert p.decision_id == existing.id
    for r in reasons:
        assert isinstance(r, DecisionReason)
        assert r.decision_id == existing.id
    # The engine must NOT have called db.add for a brand-new Decision
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_r3_engine_rejects_unpersisted_aggregate():
    """
    Guard: if the caller hands the engine a Decision that hasn't
    been flushed (no ``id``), the engine must refuse rather than
    write orphan FKs.
    """
    from unittest.mock import patch
    from app.modules.security.decision_engine.services.decision_engine import DecisionEngine
    from app.modules.security.decision_engine.models.decision import Decision
    from app.modules.security.decision_engine.models.context import DecisionContext

    db = AsyncMock()
    re_mock = AsyncMock()
    pe_mock = AsyncMock()
    with patch(
        "app.modules.security.decision_engine.services.decision_engine.RuleEngine",
        return_value=re_mock,
    ), patch(
        "app.modules.security.decision_engine.services.decision_engine.PolicyEngine",
        return_value=pe_mock,
    ):
        engine = DecisionEngine(db)
        unpersisted = Decision()  # no id, not flushed
        context = DecisionContext(
            id="ctx-1", tenant_id="t", correlation_id="c", raw_data={},
        )

        # R19: engine now raises the project-typed DomainError
        # (DecisionInvariantError is a subclass of ValueError-equivalent
        # in our hierarchy; pytest.raises(ValueError) is preserved for
        # backward compatibility).
        from app.core.exceptions import DecisionInvariantError
        with pytest.raises((ValueError, DecisionInvariantError)):
            await engine.determine_decision(unpersisted, context)


# ─────────────────────────────────────────────────────────────────────
#  Sprint 1 R5 — rejection history survives the rollback
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r5_rejection_path_preserves_history():
    """
    The pipeline's rejection helper must:
      1. rollback the failing transaction,
      2. re-open a fresh transaction to write the REJECTED history row,
      3. commit the history row,
      4. only THEN raise the original exception to the caller.

    Previously the history row was discarded by the rollback that
    tried to "undo" the rejection transition itself.
    """
    from app.modules.security.decision_engine.services.decision_pipeline import DecisionPipeline
    from app.modules.security.decision_engine.constants import DecisionState

    db = AsyncMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()

    manager = AsyncMock()
    manager.transition_to = AsyncMock()

    stats = AsyncMock()
    stats.record_decision_stats = AsyncMock()

    pipeline = DecisionPipeline(
        db=db,
        context_builder=AsyncMock(),
        validator=AsyncMock(),
        engine=AsyncMock(),
        manager=manager,
        stats_service=stats,
    )

    # The helper itself swallows the failure and commits the history row;
    # it does NOT raise.  The pipeline wrapper (execute) is responsible
    # for re-raising the original exception after the helper runs.
    await pipeline._finalise_rejection(
        decision_id="dec-1",
        tenant_id="tenant-1",
        reason="boom",
        started=0.0,
    )

    # R5 contract: in the happy path the helper writes the REJECTED
    # transition + commits it; rollback is only called as a recovery
    # step when commit/transition themselves fail.
    manager.transition_to.assert_awaited_once()
    args, kwargs = manager.transition_to.call_args
    assert args[0] == "dec-1"
    assert args[1] == DecisionState.REJECTED
    assert kwargs.get("reason") == "boom"
    # R5: history was committed, not rolled back
    assert db.commit.called
    # R5: stats were recorded on the now-committed REJECTED state
    stats.record_decision_stats.assert_awaited_once()


@pytest.mark.asyncio
async def test_r5_rejection_path_recovers_via_rollback_on_commit_failure():
    """R5 edge case: when the REJECTED transition's commit raises, the
    helper MUST attempt a rollback so the failing transaction is
    cleaned up before propagating.  Stats are best-effort and must
    still fire even after the rollback."""
    from app.modules.security.decision_engine.services.decision_pipeline import DecisionPipeline
    from app.modules.security.decision_engine.constants import DecisionState

    db = AsyncMock()
    db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    db.rollback = AsyncMock()
    db.flush = AsyncMock()

    manager = AsyncMock()
    manager.transition_to = AsyncMock()

    stats = AsyncMock()
    stats.record_decision_stats = AsyncMock()

    pipeline = DecisionPipeline(
        db=db,
        context_builder=AsyncMock(),
        validator=AsyncMock(),
        engine=AsyncMock(),
        manager=manager,
        stats_service=stats,
    )

    await pipeline._finalise_rejection(
        decision_id="dec-1",
        tenant_id="tenant-1",
        reason="boom",
        started=0.0,
    )

    # R5: when commit fails, rollback is invoked to clean the txn
    assert db.rollback.called
    # R5: stats still recorded (best-effort)
    stats.record_decision_stats.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────
#  Sprint 1 R6 / Sprint 2 R17 — DecisionService must eagerly load
#  relationships via lazy="selectin" set at the model level.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r6_get_decision_detail_uses_selectinload():
    """
    R6/R17 contract: every relationship the detail route reads
    (``plan.steps``, ``reasons``, ``context``, ``policy_ref``,
    ``history``) must be eagerly loaded — either via explicit
    ``selectinload`` on the query OR via ``lazy="selectin"`` declared
    on the relationship at the model level.

    Sprint 2 R17 chose the latter (declarative on the model) so that
    every caller of the relationship gets safe loading without having
    to remember ``.options(...)``.  We verify the model declarative.
    """
    from app.modules.security.decision_engine.models.decision import Decision

    expected_relationships = ("plan", "history", "versions", "reasons", "constraints", "policy_ref", "context")
    from sqlalchemy import inspect as _sa_inspect
    mapper = _sa_inspect(Decision)
    lazy_map = {rel.key: rel.lazy for rel in mapper.relationships}
    for rel_name in expected_relationships:
        loader = lazy_map.get(rel_name)
        assert loader == "selectin", (
            f"Decision.{rel_name} must use lazy='selectin' for R17 "
            f"eager-loading safety; got lazy={loader!r}"
        )


@pytest.mark.asyncio
async def test_r6_list_decisions_uses_selectinload():
    """R17 contract: relationships are eagerly loaded via lazy='selectin'
    declared at the model level — every list-row consumer gets safe
    loading without needing explicit .options() on the query."""
    from app.modules.security.decision_engine.models.decision import Decision
    from sqlalchemy import inspect as _sa_inspect

    # List endpoint reads these relationships; they must all be eager.
    mapper = _sa_inspect(Decision)
    lazy_map = {rel.key: rel.lazy for rel in mapper.relationships}
    for rel_name in ("plan", "reasons"):
        assert lazy_map.get(rel_name) == "selectin", (
            f"Decision.{rel_name} must use lazy='selectin' for R17; "
            f"got lazy={lazy_map.get(rel_name)!r}"
        )
