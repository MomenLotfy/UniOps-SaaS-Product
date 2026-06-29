from __future__ import annotations
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.exceptions import DecisionNotFoundError, InvalidStateTransitionError
from app.models.base import BaseModel
from ..constants import DecisionState, VALID_TRANSITIONS
from ..models.decision import Decision

class DecisionManager:
    """
    Handles the deterministic lifecycle and state transitions of a Decision.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def transition_to(self, decision_id: str, to_state: DecisionState, user_id: str = "system", reason: Optional[str] = None) -> Decision:
        """
        Transitions a decision to a new state after validating the transition.
        """
        # 1. Fetch current state
        result = await self.db.execute(select(Decision).where(Decision.id == decision_id))
        decision = result.scalar_one_or_none()

        if not decision:
            raise DecisionNotFoundError(decision_id)

        current_state = decision.status

        # 2. Validate transition
        allowed_next_states = VALID_TRANSITIONS.get(current_state, [])
        if to_state not in allowed_next_states:
            raise InvalidStateTransitionError(
                from_state=str(current_state.value if hasattr(current_state, "value") else current_state),
                to_state=str(to_state.value if hasattr(to_state, "value") else to_state),
                entity="Decision",
            )

        # 3. Update state
        decision.status = to_state

        # 4. Record history
        from ..models.decision import DecisionHistory
        history = DecisionHistory(
            tenant_id=decision.tenant_id,
            decision_id=decision_id,
            from_state=current_state,
            to_state=to_state,
            changed_by=user_id,
            change_reason=reason,
            correlation_id=decision.correlation_id,
            trace_id=decision.trace_id
        )
        self.db.add(history)

        await self.db.flush()
        return decision

    async def create_decision(self, tenant_id: str, correlation_id: str, context_id: str) -> Decision:
        """
        Initializes a new Decision in the CREATED state.
        """
        from ..models.decision import Decision

        decision = Decision(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            context_id=context_id,
            status=DecisionState.CREATED,
            version=1
        )
        self.db.add(decision)
        await self.db.flush()
        return decision
