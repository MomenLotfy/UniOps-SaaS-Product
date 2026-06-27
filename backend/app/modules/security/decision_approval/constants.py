"""
Constants for the Decision Approval Engine.

Mirrors the pattern used by decision_engine/constants.py and
decision_strategy/constants.py.  Every constant here is referenced
from both services and tests.
"""
from enum import Enum
from typing import Dict, Set


# ─────────────────────────────────────────────────────────────────────
#  Approval State Machine
# ─────────────────────────────────────────────────────────────────────
class ApprovalState(str, Enum):
    """
    Lifecycle states for an ApprovalRequest.

      NULL → CREATED → VALIDATING → WAITING_APPROVAL
                                       ├─→ PARTIALLY_APPROVED → APPROVED
                                       ├─→ REJECTED
                                       ├─→ EXPIRED
                                       └─→ CANCELLED
      Any non-terminal state → ARCHIVED (terminal)
    """
    CREATED             = "CREATED"
    VALIDATING          = "VALIDATING"
    WAITING_APPROVAL    = "WAITING_APPROVAL"
    PARTIALLY_APPROVED  = "PARTIALLY_APPROVED"
    APPROVED            = "APPROVED"
    REJECTED            = "REJECTED"
    EXPIRED             = "EXPIRED"
    CANCELLED           = "CANCELLED"
    ARCHIVED            = "ARCHIVED"


# Valid state transitions — referenced by ApprovalLifecycleManager.
VALID_APPROVAL_TRANSITIONS: Dict = {
    None:                              [ApprovalState.CREATED],
    ApprovalState.CREATED:             [ApprovalState.VALIDATING, ApprovalState.CANCELLED, ApprovalState.ARCHIVED],
    ApprovalState.VALIDATING:          [ApprovalState.WAITING_APPROVAL, ApprovalState.REJECTED, ApprovalState.EXPIRED, ApprovalState.CANCELLED, ApprovalState.ARCHIVED],
    ApprovalState.WAITING_APPROVAL:    [ApprovalState.PARTIALLY_APPROVED, ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.EXPIRED, ApprovalState.CANCELLED, ApprovalState.ARCHIVED],
    ApprovalState.PARTIALLY_APPROVED:  [ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.EXPIRED, ApprovalState.CANCELLED, ApprovalState.ARCHIVED],
    ApprovalState.APPROVED:            [ApprovalState.ARCHIVED],
    ApprovalState.REJECTED:            [ApprovalState.ARCHIVED],
    ApprovalState.EXPIRED:             [ApprovalState.ARCHIVED],
    ApprovalState.CANCELLED:           [ApprovalState.ARCHIVED],
    ApprovalState.ARCHIVED:            [],
}


TERMINAL_APPROVAL_STATES: Set[ApprovalState] = {
    ApprovalState.ARCHIVED,
}


# ─────────────────────────────────────────────────────────────────────
#  Approval Type
# ─────────────────────────────────────────────────────────────────────
class ApprovalType(str, Enum):
    """
    High-level classification of an approval request.

    Drives routing, urgency, and notification rules.
    """
    SECURITY   = "SECURITY"
    PLATFORM   = "PLATFORM"
    BUSINESS   = "BUSINESS"
    COMPLIANCE = "COMPLIANCE"
    EMERGENCY  = "EMERGENCY"
    AUTOMATIC  = "AUTOMATIC"


# ─────────────────────────────────────────────────────────────────────
#  Approval Requirement Modes
# ─────────────────────────────────────────────────────────────────────
class ApprovalRequirementMode(str, Enum):
    """
    How multiple required approvers combine to produce a final decision.
    """
    SINGLE               = "SINGLE"                # one approver suffices
    MULTIPLE              = "MULTIPLE"              # N approvals required, order irrelevant
    SEQUENTIAL            = "SEQUENTIAL"            # fixed order, each must approve
    PARALLEL              = "PARALLEL"              # all may approve independently
    MAJORITY              = "MAJORITY"              # > 50% of the chain
    AUTOMATIC_APPROVAL    = "AUTOMATIC_APPROVAL"    # no human required
    AUTOMATIC_REJECTION   = "AUTOMATIC_REJECTION"   # auto-rejected without evaluation


# ─────────────────────────────────────────────────────────────────────
#  Approval Outcome
# ─────────────────────────────────────────────────────────────────────
class ApprovalOutcome(str, Enum):
    """Outcome of a single approver's decision."""
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ABSTAINED = "ABSTAINED"
    EXPIRED  = "EXPIRED"


# ─────────────────────────────────────────────────────────────────────
#  Actor Role — who is the approver?
# ─────────────────────────────────────────────────────────────────────
class ApprovalActorRole(str, Enum):
    """Who fulfils the approval slot."""
    SECURITY_TEAM   = "SECURITY_TEAM"
    PLATFORM_TEAM   = "PLATFORM_TEAM"
    BUSINESS_OWNER  = "BUSINESS_OWNER"
    APPLICATION_OWNER = "APPLICATION_OWNER"
    REPOSITORY_OWNER = "REPOSITORY_OWNER"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    DELEGATE        = "DELEGATE"
    SYSTEM          = "SYSTEM"     # automatic decisions
    EMERGENCY_OVERRIDE = "EMERGENCY_OVERRIDE"


# ─────────────────────────────────────────────────────────────────────
#  Policy Evaluation Factors
# ─────────────────────────────────────────────────────────────────────
class PolicyFactor(str, Enum):
    """
    Inputs evaluated by an ApprovalPolicy.

    Policies are free to use any subset of these.  New factors are
    added without engine changes — the registry handles them.
    """
    BUSINESS_CRITICALITY    = "BUSINESS_CRITICALITY"
    TECHNICAL_RISK          = "TECHNICAL_RISK"
    CVSS_SCORE              = "CVSS_SCORE"
    EPSS_SCORE              = "EPSS_SCORE"
    ASSET_CRITICALITY       = "ASSET_CRITICALITY"
    ENVIRONMENT             = "ENVIRONMENT"
    COMPLIANCE_FRAMEWORK    = "COMPLIANCE_FRAMEWORK"
    CHANGE_WINDOW           = "CHANGE_WINDOW"
    MAINTENANCE_WINDOW      = "MAINTENANCE_WINDOW"
    DEPLOYMENT_ENVIRONMENT  = "DEPLOYMENT_ENVIRONMENT"
    PRODUCTION_STATUS       = "PRODUCTION_STATUS"
    BUSINESS_OWNER          = "BUSINESS_OWNER"
    APPLICATION_OWNER       = "APPLICATION_OWNER"
    REPOSITORY_OWNER        = "REPOSITORY_OWNER"
    SECURITY_TEAM           = "SECURITY_TEAM"
    PLATFORM_TEAM           = "PLATFORM_TEAM"
    ORG_POLICY              = "ORG_POLICY"
    TENANT_POLICY           = "TENANT_POLICY"
    EMERGENCY_MODE          = "EMERGENCY_MODE"
    MANUAL_OVERRIDE         = "MANUAL_OVERRIDE"


# ─────────────────────────────────────────────────────────────────────
#  Scoring weights for the ApprovalPolicyEngine
# ─────────────────────────────────────────────────────────────────────
APPROVAL_SCORING_WEIGHTS: Dict[str, float] = {
    "risk":        0.25,
    "criticality": 0.20,
    "compliance":  0.15,
    "urgency":     0.15,
    "history":     0.10,
    "automation":  0.10,
    "owner":       0.05,
}
assert abs(sum(APPROVAL_SCORING_WEIGHTS.values()) - 1.0) < 1e-9, "Approval weights must sum to 1.0"


# ─────────────────────────────────────────────────────────────────────
#  Default thresholds
# ─────────────────────────────────────────────────────────────────────
# Score above this ⇒ automatic rejection (no human in the loop).
AUTOMATIC_REJECTION_THRESHOLD = 0.95
# Score below this ⇒ automatic approval (no human required).
AUTOMATIC_APPROVAL_THRESHOLD = 0.05
# Default request TTL in seconds (24 h).
DEFAULT_APPROVAL_TTL_SECONDS = 24 * 60 * 60
# TTL for the in-memory approval evaluation cache.
APPROVAL_CACHE_TTL_SECONDS = 300


# ─────────────────────────────────────────────────────────────────────
#  Rejection reasons
# ─────────────────────────────────────────────────────────────────────
class ApprovalRejectionReason(str, Enum):
    """Canonical rejection reasons — stable, queryable strings."""
    MISSING_DECISION         = "MISSING_DECISION"
    MISSING_STRATEGY         = "MISSING_STRATEGY"
    MISSING_APPROVER         = "MISSING_APPROVER"
    INVALID_CHAIN            = "INVALID_CHAIN"
    POLICY_DENIED            = "POLICY_DENIED"
    BLOCKED_BY_RISK          = "BLOCKED_BY_RISK"
    BLOCKED_BY_COMPLIANCE    = "BLOCKED_BY_COMPLIANCE"
    EXPIRED                  = "EXPIRED"
    CANCELLED                = "CANCELLED"
    AUTOMATIC_REJECTION      = "AUTOMATIC_REJECTION"
    TENANT_POLICY_DENIED     = "TENANT_POLICY_DENIED"
    ORG_POLICY_DENIED        = "ORG_POLICY_DENIED"


# ─────────────────────────────────────────────────────────────────────
#  Pipeline stages
# ─────────────────────────────────────────────────────────────────────
class ApprovalPipelineStage(str, Enum):
    """Pipeline stage identifiers — observability + audit."""
    DISCOVERY             = "DISCOVERY"
    CONTEXT_BUILD         = "CONTEXT_BUILD"
    REQUIREMENT_RESOLVE   = "REQUIREMENT_RESOLVE"
    POLICY_EVALUATION     = "POLICY_EVALUATION"
    CHAIN_RESOLUTION      = "CHAIN_RESOLUTION"
    VALIDATION            = "VALIDATION"
    PERSISTENCE           = "PERSISTENCE"
    STATISTICS            = "STATISTICS"


__all__ = [
    "APPROVAL_CACHE_TTL_SECONDS",
    "APPROVAL_SCORING_WEIGHTS",
    "ApprovalActorRole",
    "ApprovalOutcome",
    "ApprovalPipelineStage",
    "ApprovalRejectionReason",
    "ApprovalRequirementMode",
    "ApprovalState",
    "ApprovalType",
    "AUTOMATIC_APPROVAL_THRESHOLD",
    "AUTOMATIC_REJECTION_THRESHOLD",
    "DEFAULT_APPROVAL_TTL_SECONDS",
    "PolicyFactor",
    "TERMINAL_APPROVAL_STATES",
    "VALID_APPROVAL_TRANSITIONS",
]