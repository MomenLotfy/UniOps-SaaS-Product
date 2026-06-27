"""
Constants for the Decision Strategy Engine.

Mirrors the style of decision_engine/constants.py.
Every constant here is referenced from both services and tests.
"""
from enum import Enum
from typing import Dict


class StrategyType(str, Enum):
    """
    Canonical remediation strategy types.

    New strategies must be added here AND registered via
    `DecisionStrategyRegistry.register(...)`.  The registry is the
    authoritative extension point — the engine itself never hard-codes
    strategy behaviour.
    """
    PATCH_EXISTING_VERSION     = "PATCH_EXISTING_VERSION"
    UPGRADE_PACKAGE            = "UPGRADE_PACKAGE"
    DOWNGRADE_PACKAGE          = "DOWNGRADE_PACKAGE"
    REPLACE_DEPENDENCY         = "REPLACE_DEPENDENCY"
    DISABLE_FEATURE            = "DISABLE_FEATURE"
    CONFIGURATION_CHANGE       = "CONFIGURATION_CHANGE"
    INFRASTRUCTURE_CHANGE      = "INFRASTRUCTURE_CHANGE"
    CONTAINER_UPDATE           = "CONTAINER_UPDATE"
    OS_PACKAGE_UPDATE          = "OS_PACKAGE_UPDATE"
    IMAGE_REPLACEMENT          = "IMAGE_REPLACEMENT"
    SECRET_ROTATION            = "SECRET_ROTATION"
    CERTIFICATE_ROTATION       = "CERTIFICATE_ROTATION"
    POLICY_CHANGE              = "POLICY_CHANGE"
    TEMPORARY_MITIGATION       = "TEMPORARY_MITIGATION"
    MANUAL_REVIEW_REQUIRED     = "MANUAL_REVIEW_REQUIRED"
    VENDOR_PATCH_REQUIRED      = "VENDOR_PATCH_REQUIRED"
    NO_ACTION                  = "NO_ACTION"


# Final-result → preferred strategy types (used as a hint, not a hard rule).
# The Strategy Resolver considers ALL applicable strategies and ranks them.
FINAL_RESULT_TO_STRATEGY_HINTS: Dict[str, list] = {
    "PATCH":         [StrategyType.PATCH_EXISTING_VERSION,
                      StrategyType.UPGRADE_PACKAGE,
                      StrategyType.IMAGE_REPLACEMENT],
    "MITIGATE":      [StrategyType.TEMPORARY_MITIGATION,
                      StrategyType.CONFIGURATION_CHANGE,
                      StrategyType.POLICY_CHANGE],
    "UPGRADE":       [StrategyType.UPGRADE_PACKAGE,
                      StrategyType.CONTAINER_UPDATE,
                      StrategyType.IMAGE_REPLACEMENT],
    "ROTATE":        [StrategyType.SECRET_ROTATION,
                      StrategyType.CERTIFICATE_ROTATION],
    "MONITOR":       [StrategyType.NO_ACTION],
    "IGNORE":        [StrategyType.NO_ACTION],
    "REVIEW":        [StrategyType.MANUAL_REVIEW_REQUIRED,
                      StrategyType.VENDOR_PATCH_REQUIRED],
}


class StrategyState(str, Enum):
    """
    Lifecycle states for a DecisionStrategy entity.

    Mirrors the pattern used by DecisionState.  A strategy moves through:
      NULL → SELECTED → APPROVED → EXECUTING → COMPLETED
                              └→ REJECTED → ARCHIVED (terminal)
      ARCHIVED is reachable from any non-terminal state.
    """
    SELECTED   = "SELECTED"     # chosen by StrategySelector
    APPROVED   = "APPROVED"     # approved (manual or auto) for execution
    EXECUTING  = "EXECUTING"    # execution has started
    COMPLETED  = "COMPLETED"    # execution finished successfully
    FAILED     = "FAILED"       # execution failed
    REJECTED   = "REJECTED"     # manually rejected or no candidate was viable
    ARCHIVED   = "ARCHIVED"     # lifecycle end (terminal)


# Valid state transitions — referenced by DecisionStrategyLifecycleManager.
VALID_STRATEGY_TRANSITIONS = {
    None:                   [StrategyState.SELECTED],
    StrategyState.SELECTED: [StrategyState.APPROVED, StrategyState.REJECTED, StrategyState.ARCHIVED],
    StrategyState.APPROVED: [StrategyState.EXECUTING, StrategyState.REJECTED, StrategyState.ARCHIVED],
    StrategyState.EXECUTING:[StrategyState.COMPLETED, StrategyState.FAILED],
    StrategyState.COMPLETED:[StrategyState.ARCHIVED],
    StrategyState.FAILED:   [StrategyState.ARCHIVED],
    StrategyState.REJECTED: [StrategyState.ARCHIVED],
    StrategyState.ARCHIVED: [],
}


class StrategyPipelineStage(str, Enum):
    """Pipeline stage identifiers — observability + audit."""
    DISCOVERY            = "DISCOVERY"
    CONSTRAINT_EVAL      = "CONSTRAINT_EVALUATION"
    CANDIDATE_GENERATION = "CANDIDATE_GENERATION"
    VALIDATION           = "VALIDATION"
    RANKING              = "RANKING"
    SELECTION            = "SELECTION"
    PERSISTENCE          = "PERSISTENCE"
    STATISTICS           = "STATISTICS"


class RejectionReason(str, Enum):
    """Canonical rejection reasons — stable, queryable strings."""
    MISSING_METADATA         = "MISSING_METADATA"
    UNSUPPORTED_PLATFORM     = "UNSUPPORTED_PLATFORM"
    UNSUPPORTED_PKG_MANAGER  = "UNSUPPORTED_PACKAGE_MANAGER"
    MISSING_REPOSITORY       = "MISSING_REPOSITORY"
    MISSING_ASSET            = "MISSING_ASSET"
    INVALID_DEP_GRAPH        = "INVALID_DEPENDENCY_GRAPH"
    MISSING_PATCH_INFO       = "MISSING_PATCH_INFO"
    BROKEN_CONSTRAINT        = "BROKEN_CONSTRAINT"
    NO_CANDIDATES            = "NO_CANDIDATES"


# Weights for the scoring engine.
# All values 0.0–1.0 and sum to 1.0.  Tunable, but never per-decision.
SCORING_WEIGHTS = {
    "feasibility":          0.18,
    "risk_reduction":       0.18,
    "automation_readiness": 0.12,
    "rollback_difficulty":  0.10,
    "expected_downtime":    0.07,
    "business_impact":      0.10,
    "compliance_impact":    0.08,
    "historical_success":   0.07,
    "cost":                 0.05,
    "complexity":           0.05,
}
assert abs(sum(SCORING_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# Supported platforms + package managers — used by the validator.
# Matches the constants used by the asset + scan subsystems.
SUPPORTED_PLATFORMS = {
    "linux", "darwin", "windows",
    "kubernetes", "ecs", "lambda",
    "aws_ec2", "aws_ecs", "aws_lambda",
    "gcp_compute", "gcp_gke", "azure_vm",
}

SUPPORTED_PACKAGE_MANAGERS = {
    "apt", "yum", "dnf", "apk", "brew", "choco", "pip", "npm",
    "yarn", "pnpm", "maven", "gradle", "go", "cargo", "nuget",
    "composer", "gem", "helm", "docker",
}

# TTL (seconds) for the strategy evaluation cache.  Repeated evaluations
# of the same decision within the TTL reuse the cached result.
STRATEGY_CACHE_TTL_SECONDS = 300
