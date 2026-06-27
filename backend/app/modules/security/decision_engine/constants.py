from enum import Enum

class DecisionState(str, Enum):
    """
    Deterministic lifecycle states for a Security Decision.
    """
    CREATED = "CREATED"
    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"

class DecisionPipelineStage(str, Enum):
    """
    Sequential stages of the Decision Engine pipeline.
    """
    CONTEXT_BUILD \
        = "CONTEXT_BUILD"
    VALIDATION \
        = "VALIDATION"
    METADATA_ENRICHMENT \
        = "METADATA_ENRICHMENT"
    POLICY_LOADING \
        = "POLICY_LOADING"
    DECISION_CREATION \
        = "DECISION_CREATION"
    PERSISTENCE \
        = "PERSISTENCE"
    STATISTICS_UPDATE \
        = "STATISTICS_UPDATE"

# Valid state transitions to ensure deterministic lifecycle
VALID_TRANSITIONS = {
    None: [DecisionState.CREATED],
    DecisionState.CREATED: [DecisionState.CONTEXT_BUILDING],
    DecisionState.CONTEXT_BUILDING: [DecisionState.VALIDATING],
    DecisionState.VALIDATING: [DecisionState.READY, DecisionState.REJECTED],
    DecisionState.READY: [DecisionState.ARCHIVED],
    DecisionState.REJECTED: [DecisionState.ARCHIVED],
    DecisionState.ARCHIVED: [],
}
