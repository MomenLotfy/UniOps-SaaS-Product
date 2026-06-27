"""
Approval Resolver.

Returns the policies that apply to a given context + aggregates the
verdicts into a single deterministic `ApprovalPolicyResult`.

Mirrors `DecisionStrategyResolver`.
"""
from __future__ import annotations

from typing import Any, List

from ..constants import ApprovalActorRole, ApprovalRequirementMode
from .approval_interfaces import (
    ApprovalPolicyResult,
    IApprovalPolicy,
    IApprovalResolver,
)
from .approval_registry import ApprovalRegistry


class ApprovalResolver(IApprovalResolver):
    """Default resolver — uses `ApprovalRegistry.applicable(...)`."""

    def __init__(self, registry: ApprovalRegistry) -> None:
        self._registry = registry

    def resolve(self, context: Any) -> List[IApprovalPolicy]:
        return self._registry.applicable(context)

    def aggregate(self, results: List[ApprovalPolicyResult]) -> ApprovalPolicyResult:
        """
        Merge multiple policy verdicts.

        - `requires_approval` = OR across all
        - `required_roles`    = union (deduplicated, stable order)
        - `requirement_mode`  = highest precedence: SEQUENTIAL > MAJORITY > MULTIPLE > PARALLEL > SINGLE > AUTOMATIC_*
        - `auto_approve`      = AND across all (must every policy agree)
        - `auto_reject`       = OR across all
        - `risk_score`        = max
        - `criticality_score` = max
        - `confidence`        = avg
        - `reasons`           = concatenated
        """
        if not results:
            return ApprovalPolicyResult(requires_approval=False)

        mode_rank = {
            ApprovalRequirementMode.SEQUENTIAL: 5,
            ApprovalRequirementMode.MAJORITY: 4,
            ApprovalRequirementMode.MULTIPLE: 3,
            ApprovalRequirementMode.PARALLEL: 2,
            ApprovalRequirementMode.SINGLE: 1,
            ApprovalRequirementMode.AUTOMATIC_APPROVAL: 0,
            ApprovalRequirementMode.AUTOMATIC_REJECTION: 0,
        }

        requires = any(r.requires_approval for r in results)
        roles: List[ApprovalActorRole] = []
        for r in results:
            for role in r.required_roles:
                if role not in roles:
                    roles.append(role)
        mode = max((r.requirement_mode for r in results), key=lambda m: mode_rank.get(m, 0))
        auto_approve = all(r.auto_approve for r in results)
        auto_reject = any(r.auto_reject for r in results)
        risk = max((r.risk_score for r in results), default=0.0)
        crit = max((r.criticality_score for r in results), default=0.0)
        conf = sum(r.confidence for r in results) / len(results)
        reasons: List = []
        for r in results:
            reasons.extend(r.reasons)
        return ApprovalPolicyResult(
            requires_approval=requires and not auto_reject,
            required_roles=roles if requires and not auto_reject else [],
            requirement_mode=mode,
            auto_approve=auto_approve and not requires,
            auto_reject=auto_reject,
            risk_score=risk,
            criticality_score=crit,
            confidence=conf,
            reasons=reasons,
        )


__all__ = ["ApprovalResolver"]
