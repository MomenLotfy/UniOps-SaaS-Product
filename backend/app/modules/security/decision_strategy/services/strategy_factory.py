"""
Decision Strategy Factory.

The Factory composes a fresh `StrategyCandidateData` for a given
descriptor + decision + context.  It does NOT validate or score — those
are separate concerns owned by the Validator and ScoringEngine.
"""
from __future__ import annotations

from typing import Any

from ..constants import StrategyType
from .strategy_interfaces import IStrategyDescriptor, StrategyCandidateData


# Default metadata for the 17 strategies — expressed as data, not
# hard-coded in the engine.  Engine reads these tables to populate
# downstream scores.
#
# These defaults apply UNLESS the context overrides them with explicit
# values (e.g. downtime minutes, requires_approval).
_STRATEGY_DEFAULT_DOWN_MIN: dict = {
    StrategyType.PATCH_EXISTING_VERSION:    5,
    StrategyType.UPGRADE_PACKAGE:          15,
    StrategyType.DOWNGRADE_PACKAGE:        30,
    StrategyType.REPLACE_DEPENDENCY:       60,
    StrategyType.DISABLE_FEATURE:           2,
    StrategyType.CONFIGURATION_CHANGE:      5,
    StrategyType.INFRASTRUCTURE_CHANGE:   120,
    StrategyType.CONTAINER_UPDATE:         30,
    StrategyType.OS_PACKAGE_UPDATE:        20,
    StrategyType.IMAGE_REPLACEMENT:        45,
    StrategyType.SECRET_ROTATION:           5,
    StrategyType.CERTIFICATE_ROTATION:     10,
    StrategyType.POLICY_CHANGE:             0,
    StrategyType.TEMPORARY_MITIGATION:      2,
    StrategyType.MANUAL_REVIEW_REQUIRED:    0,
    StrategyType.VENDOR_PATCH_REQUIRED:     0,
    StrategyType.NO_ACTION:                 0,
}

_STRATEGY_REQUIRES_APPROVAL: dict = {
    StrategyType.INFRASTRUCTURE_CHANGE:    True,
    StrategyType.REPLACE_DEPENDENCY:       True,
    StrategyType.POLICY_CHANGE:            True,
    StrategyType.VENDOR_PATCH_REQUIRED:    True,
    StrategyType.MANUAL_REVIEW_REQUIRED:   True,
}

_STRATEGY_IS_REVERSIBLE: dict = {
    StrategyType.DISABLE_FEATURE:          True,
    StrategyType.CONFIGURATION_CHANGE:     True,
    StrategyType.POLICY_CHANGE:            True,
    StrategyType.TEMPORARY_MITIGATION:     True,
    StrategyType.NO_ACTION:                True,
    StrategyType.IMAGE_REPLACEMENT:        True,
    StrategyType.CONTAINER_UPDATE:         True,
    StrategyType.OS_PACKAGE_UPDATE:        True,
    StrategyType.PATCH_EXISTING_VERSION:   True,
    StrategyType.UPGRADE_PACKAGE:          True,
    StrategyType.DOWNGRADE_PACKAGE:        True,
    StrategyType.SECRET_ROTATION:          True,
    StrategyType.CERTIFICATE_ROTATION:     True,
    StrategyType.REPLACE_DEPENDENCY:       False,   # may break API
    StrategyType.INFRASTRUCTURE_CHANGE:    False,
    StrategyType.MANUAL_REVIEW_REQUIRED:   True,
    StrategyType.VENDOR_PATCH_REQUIRED:    True,
}


class DecisionStrategyFactory:
    """Composes in-memory candidate objects."""

    def build_candidate(
        self,
        descriptor: IStrategyDescriptor,
        decision: Any,
        context: Any,
    ) -> StrategyCandidateData:
        """
        Build a candidate.  The descriptor contributes:
          - hard constraints
          - base requirements
        Static defaults for downtime / reversibility come from the
        canonical tables above.
        """
        cand = StrategyCandidateData(candidate_type=descriptor.strategy_type)

        cand.constraints  = list(descriptor.hard_constraints(decision, context))
        cand.requirements = list(descriptor.base_requirements(decision, context))

        cand.expected_downtime_min = _STRATEGY_DEFAULT_DOWN_MIN.get(
            descriptor.strategy_type, 0
        )
        cand.requires_human_approval = _STRATEGY_REQUIRES_APPROVAL.get(
            descriptor.strategy_type, False
        )
        cand.is_reversible = _STRATEGY_IS_REVERSIBLE.get(
            descriptor.strategy_type, True
        )

        return cand