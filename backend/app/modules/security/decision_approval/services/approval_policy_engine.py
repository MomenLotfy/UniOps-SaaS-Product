"""
Approval Policy Engine.

Orchestrates the registry + resolver + scoring engine to produce a
single deterministic verdict for a given context.  Mirrors the role
of `DecisionStrategyEngine` but at a higher level (policy evaluation
vs. candidate selection).
"""
from __future__ import annotations

from typing import Any, List

from ..constants import ApprovalActorRole
from .approval_evaluator import ApprovalScoringEngine
from .approval_factory import ApprovalFactory
from .approval_interfaces import (
    ApprovalCandidateData,
    ApprovalPolicyResult,
    IApprovalPolicy,
)
from .approval_registry import ApprovalRegistry, bootstrap_default_approval_policies
from .approval_resolver import ApprovalResolver


class ApprovalPolicyEngine:
    """
    Pure-function policy evaluator.

    Composition root holds:
      - registry (12 policies by default)
      - resolver
      - scoring engine
      - factory (verdict → candidate)
    """

    def __init__(
        self,
        registry: ApprovalRegistry = None,
        scoring: ApprovalScoringEngine = None,
        resolver: ApprovalResolver = None,
        factory: ApprovalFactory = None,
    ) -> None:
        self._registry = registry or ApprovalRegistry()
        if not registry:
            bootstrap_default_approval_policies(self._registry)
        self._resolver = resolver or ApprovalResolver(self._registry)
        self._scoring = scoring or ApprovalScoringEngine()
        self._factory = factory or ApprovalFactory()

    # ── Discovery ────────────────────────────────────────────────────
    def applicable_policies(self, context: Any) -> List[IApprovalPolicy]:
        return self._resolver.resolve(context)

    # ── Evaluation ───────────────────────────────────────────────────
    def evaluate_policies(self, context: Any) -> ApprovalPolicyResult:
        applicable = self._resolver.resolve(context)
        if not applicable:
            return ApprovalPolicyResult(requires_approval=False)
        results = [p.evaluate(context) for p in applicable]
        return self._resolver.aggregate(results)

    # ── End-to-end: policy → candidate ──────────────────────────────
    def build_candidate(
        self,
        decision: Any,
        context: Any,
        *,
        approval_type,
    ) -> ApprovalCandidateData:
        verdict = self.evaluate_policies(context)
        scoring = self._scoring.score(context)
        return self._factory.build_candidate(
            decision=decision,
            context=context,
            verdict=verdict,
            approval_type=approval_type,
            scoring=scoring,
        )


__all__ = ["ApprovalPolicyEngine"]