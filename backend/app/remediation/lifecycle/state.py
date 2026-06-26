from enum import Enum
from typing import List, Set, Dict

class RemediationState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_FOR_CAPABILITY = "WAITING_FOR_CAPABILITY"
    CAPABILITY_SELECTED = "CAPABILITY_SELECTED"
    WAITING_FOR_VALIDATION = "WAITING_FOR_VALIDATION"
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"

class StateMachine:
    """
    Deterministic state machine for remediation execution.
    Rejects illegal transitions.
    """
    # Define valid transitions: current_state -> set(next_states)
    TRANSITIONS: Dict[RemediationState, Set[RemediationState]] = {
        RemediationState.CREATED: {
            RemediationState.PLANNING,
            RemediationState.CANCELLED
        },
        RemediationState.PLANNING: {
            RemediationState.WAITING_FOR_CAPABILITY,
            RemediationState.FAILED,
            RemediationState.CANCELLED
        },
        RemediationState.WAITING_FOR_CAPABILITY: {
            RemediationState.CAPABILITY_SELECTED,
            RemediationState.FAILED,
            RemediationState.CANCELLED
        },
        RemediationState.CAPABILITY_SELECTED: {
            RemediationState.WAITING_FOR_VALIDATION,
            RemediationState.FAILED,
            RemediationState.CANCELLED
        },
        RemediationState.WAITING_FOR_VALIDATION: {
            RemediationState.READY_FOR_EXECUTION,
            RemediationState.FAILED,
            RemediationState.CANCELLED
        },
        RemediationState.READY_FOR_EXECUTION: {
            RemediationState.EXECUTING,
            RemediationState.CANCELLED
        },
        RemediationState.EXECUTING: {
            RemediationState.COMPLETED,
            RemediationState.FAILED,
            RemediationState.ROLLED_BACK
        },
        RemediationState.COMPLETED: set(), # Terminal
        RemediationState.FAILED: {
            RemediationState.ROLLED_BACK,
            RemediationState.PLANNING # Allow retry from planning
        },
        RemediationState.CANCELLED: set(), # Terminal
        RemediationState.ROLLED_BACK: {
            RemediationState.PLANNING # Allow retry after rollback
        },
    }

    @classmethod
    def validate_transition(cls, current: RemediationState, target: RemediationState) -> bool:
        """Checks if the transition from current to target is legal."""
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def get_valid_next_states(cls, current: RemediationState) -> List[RemediationState]:
        """Returns all legal next states for the current state."""
        return list(cls.TRANSITIONS.get(current, set()))
