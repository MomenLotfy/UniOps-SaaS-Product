"""
DecisionEngine — pure deterministic logic.

Sprint 1 R3+R4: This engine NEVER creates a new ``Decision`` aggregate.
The aggregate is owned by ``DecisionManager`` and persisted before this
engine runs.  The engine:

  1. evaluates the context via Rule + Policy engines (immutable),
  2. mutates the existing aggregate (``decision.final_result``),
  3. builds child rows (plans, steps, reasons) that reference the
     *already-persisted* decision.id — never a fresh UUID.

State transitions are delegated to ``DecisionManager.transition_to``,
called from the pipeline.  The engine itself never assigns
``status=READY`` directly.
"""
from __future__ import annotations

from typing import Any, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DecisionInvariantError
from .rule_engine import RuleEngine
from .rule_repository import RuleRepository
from .policy_engine import PolicyEngine
from ..models.decision import Decision
from ..models.plan import DecisionPlan, DecisionStep
from ..models.evidence import DecisionReason
from ..models.context import DecisionContext


class DecisionEngine:
    """
    Deterministic orchestrator: rule evaluation + policy overlay.

    Operates on an already-persisted :class:`Decision` aggregate.
    Never creates a new aggregate; never assigns state directly.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def determine_decision(
        self,
        decision: Decision,
        context: DecisionContext,
    ) -> Tuple[Decision, List[DecisionPlan], List[DecisionReason], Any]:
        """
        Evaluate ``context`` and project the result onto ``decision``.

        Returns:
            (decision, plans, reasons, resolution)

            ``decision`` is the *same* aggregate that was passed in
            (now with ``final_result`` set).  ``plans`` and
            ``reasons`` reference ``decision.id`` and will be valid
            FKs once the aggregate is flushed (which the pipeline
            does before this method returns).

        Raises:
            DecisionInvariantError: if ``decision`` is None or has no ``id``
                (i.e. the caller persisted the aggregate yet).
        """
        if decision is None:
            raise DecisionInvariantError("DecisionEngine requires an existing Decision aggregate")
        if not getattr(decision, "id", None):
            raise DecisionInvariantError(
                "DecisionEngine.determine_decision requires a persisted Decision "
                "(decision.id is missing).  Flush the aggregate before calling."
            )

        # ── 1. Technical evaluation (Rule Engine) ───────────────────────
        rule_repo = RuleRepository(self.db)
        rule_engine = RuleEngine(self.db, rule_repo)
        technical_result, _, matched_reasons_data = await rule_engine.evaluate(context)

        # ── 2. Organizational overlay (Policy Engine) ───────────────────
        policy_engine = PolicyEngine(self.db)
        final_result, updated_reasons_data, resolution = await policy_engine.apply_policy(
            context=context,
            technical_result=technical_result,
            reasons=matched_reasons_data,
        )

        # ── 3. Mutate the existing aggregate (no new Decision) ─────────
        decision.final_result = final_result
        # NOTE: status is left to DecisionManager.transition_to(...).
        # We never assign status="READY" here.

        # ── 4. Build child rows referencing the persisted aggregate ─────
        plan = DecisionPlan(
            decision_id=decision.id,
            execution_order=1,
            tenant_id=decision.tenant_id,
            correlation_id=decision.correlation_id,
        )

        steps = [
            DecisionStep(
                plan_id=plan.id,
                step_type="VERIFY_ASSET_STATE",
                result="Succeeded",
                tenant_id=decision.tenant_id,
                correlation_id=decision.correlation_id,
            ),
            DecisionStep(
                plan_id=plan.id,
                step_type=f"EXECUTE_{final_result}",
                result="Pending",
                tenant_id=decision.tenant_id,
                correlation_id=decision.correlation_id,
            ),
        ]
        # Attach steps via relationship so the FK is filled in after flush.
        plan.steps = steps

        # ── 5. Build reasons referencing the persisted aggregate ────────
        reasons: List[DecisionReason] = [
            DecisionReason(
                decision_id=decision.id,
                reason_code=r["code"],
                description=r["description"],
                tenant_id=decision.tenant_id,
                correlation_id=decision.correlation_id,
            )
            for r in updated_reasons_data
        ]
        reasons.append(
            DecisionReason(
                decision_id=decision.id,
                reason_code="POLICY_RESOLUTION",
                description=f"Resolved via {resolution.policy_name}: {resolution.reason}",
                tenant_id=decision.tenant_id,
                correlation_id=decision.correlation_id,
            )
        )

        return decision, [plan], reasons, resolution
