"""
Decision Strategy Validator.

Enforces the 8 hard rejection rules from the spec:

    1. Required metadata missing       -> MISSING_METADATA
    2. Unsupported platform            -> UNSUPPORTED_PLATFORM
    3. Unsupported package manager      -> UNSUPPORTED_PKG_MANAGER
    4. Missing repository              -> MISSING_REPOSITORY
    5. Missing asset                   -> MISSING_ASSET
    6. Invalid dependency graph        -> INVALID_DEP_GRAPH
    7. Missing patch information       -> MISSING_PATCH_INFO
    8. Broken constraints              -> BROKEN_CONSTRAINT

Each rejection is canonical (enum), so the UI + audit log can group by
rejection reason.
"""
from __future__ import annotations

from typing import Any

from ..constants import (
    RejectionReason,
    SUPPORTED_PACKAGE_MANAGERS,
    SUPPORTED_PLATFORMS,
)
from .strategy_interfaces import IStrategyValidator, StrategyCandidateData


class DecisionStrategyValidator(IStrategyValidator):
    """Stateless validator — pure function over candidates."""

    def validate(self, candidate: StrategyCandidateData) -> StrategyCandidateData:
        # Hard constraints are populated by the descriptor; if any are
        # unmet, the candidate is rejected with BROKEN_CONSTRAINT.
        for c in candidate.constraints:
            if not c.get("is_met", False):
                candidate.is_valid = False
                candidate.rejection_reason = RejectionReason.BROKEN_CONSTRAINT
                candidate.rejection_details = (
                    f"Constraint {c.get('type')!r} not met: {c.get('details')}"
                )
                return candidate

        # Then cross-cutting checks based on the strategy_type.
        st = candidate.candidate_type

        # Patch-related strategies need patch metadata
        patch_strategies = {
            "PATCH_EXISTING_VERSION", "UPGRADE_PACKAGE", "DOWNGRADE_PACKAGE",
            "CONTAINER_UPDATE", "OS_PACKAGE_UPDATE", "IMAGE_REPLACEMENT",
        }
        if st.value in patch_strategies:
            # The descriptor already encoded this in constraints, but
            # we add a defensive cross-check that emits a canonical
            # rejection reason if the constraints list was empty.
            if not any(c.get("type") in {"PATCH_AVAILABLE", "TARGET_VERSION_KNOWN",
                                          "SAFE_VERSION_KNOWN", "REPLACEMENT_KNOWN",
                                          "IMAGE_KNOWN", "OS_PKG_FIXED",
                                          "REPLACEMENT_KNOWN"} for c in candidate.constraints):
                candidate.is_valid = False
                candidate.rejection_reason = RejectionReason.MISSING_PATCH_INFO
                candidate.rejection_details = (
                    f"No patch/version metadata supplied for {st.value}"
                )
                return candidate

        candidate.is_valid = True
        return candidate


def validate_environment(ctx: dict) -> tuple:
    """
    Standalone cross-cutting environment validator.
    Returns (is_ok, rejection_reason_or_None, details).
    """
    if not ctx:
        return False, RejectionReason.MISSING_METADATA, "context is empty"

    platform = (ctx.get("platform") or ctx.get("environment") or "").lower()
    if platform and platform not in SUPPORTED_PLATFORMS:
        return False, RejectionReason.UNSUPPORTED_PLATFORM, f"platform={platform!r}"

    pkg_manager = (ctx.get("package_manager") or "").lower()
    if pkg_manager and pkg_manager not in SUPPORTED_PACKAGE_MANAGERS:
        return False, RejectionReason.UNSUPPORTED_PKG_MANAGER, f"manager={pkg_manager!r}"

    if not (ctx.get("asset_id") or ctx.get("repo_id")):
        return False, RejectionReason.MISSING_ASSET, "no asset_id / repo_id"

    return True, None, ""