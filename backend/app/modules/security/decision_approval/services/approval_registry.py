"""
Approval Policy Registry.

Mirrors `DecisionStrategyRegistry`.  Future policies register themselves
via `ApprovalRegistry.register(...)` without engine edits.  This is the
authoritative extension point for the Approval Engine.

Twelve canonical policies are registered by default.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from app.core.exceptions import ValidationError
from ..constants import ApprovalActorRole, ApprovalRequirementMode, PolicyFactor
from .approval_interfaces import IApprovalPolicy, IApprovalRegistry, ApprovalPolicyResult


# ─────────────────────────────────────────────────────────────────────
#  Default policy implementations (12)
# ─────────────────────────────────────────────────────────────────────
class _DefaultPolicy(IApprovalPolicy):
    """Base helper — evaluates factors by reading context.raw_data."""
    name = "default"
    version = 1
    description = "Fallback policy: single security team approval when any risk > 0.4"

    def _cvss(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        try:
            return float(raw.get("cvss_score", 0.0) or 0.0) / 10.0
        except (TypeError, ValueError):
            return 0.0

    def _epss(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        try:
            return float(raw.get("epss_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _criticality(self, context: Any) -> float:
        raw = getattr(context, "raw_data", {}) or {}
        try:
            return float(raw.get("business_criticality", 0.5) or 0.5)
        except (TypeError, ValueError):
            return 0.5

    def _env(self, context: Any) -> str:
        raw = getattr(context, "raw_data", {}) or {}
        return str(raw.get("environment", "production") or "production")

    def _is_emergency(self, context: Any) -> bool:
        raw = getattr(context, "raw_data", {}) or {}
        return bool(raw.get("emergency", False) or raw.get("emergency_mode", False))

    def is_applicable(self, context: Any) -> bool:
        return True

    def requires_approval(self, context: Any) -> bool:
        if self._is_emergency(context):
            return False  # emergency → handled by emergency policy
        return self._cvss(context) > 0.4 or self._criticality(context) > 0.7

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.SECURITY_TEAM]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        risk = max(self._cvss(context), self._epss(context))
        crit = self._criticality(context)
        req = self.requires_approval(context)
        return ApprovalPolicyResult(
            requires_approval=req,
            required_roles=[ApprovalActorRole.SECURITY_TEAM] if req else [],
            requirement_mode=ApprovalRequirementMode.SINGLE,
            auto_approve=not req and risk < 0.05,
            auto_reject=False,
            risk_score=risk,
            criticality_score=crit,
            confidence=0.6,
            reasons=[("POLICY_DEFAULT", "Standard fallback policy evaluated")] if req else [],
        )


class _HighRiskSecurityPolicy(_DefaultPolicy):
    name = "high_risk_security"
    version = 1
    description = "Multi-role approval when CVSS ≥ 7.0"

    def is_applicable(self, context: Any) -> bool:
        return self._cvss(context) >= 0.7

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.SECURITY_TEAM, ApprovalActorRole.PLATFORM_TEAM]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SEQUENTIAL,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.95,
            reasons=[
                ("HIGH_CVSS", f"CVSS={self._cvss(context):.2f} requires multi-role approval"),
            ],
        )


class _BusinessCriticalPolicy(_DefaultPolicy):
    name = "business_critical"
    version = 1
    description = "Business owner approval when criticality ≥ 0.8"

    def is_applicable(self, context: Any) -> bool:
        return self._criticality(context) >= 0.8

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.BUSINESS_OWNER]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SINGLE,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.9,
            reasons=[("BUSINESS_CRITICAL", "Business-critical asset requires owner sign-off")],
        )


class _ProductionEnvironmentPolicy(_DefaultPolicy):
    name = "production_environment"
    version = 1
    description = "Platform team approval for production changes"

    def is_applicable(self, context: Any) -> bool:
        return self._env(context).lower() == "production"

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.PLATFORM_TEAM]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SINGLE,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.85,
            reasons=[("PRODUCTION", "Production deployments require platform team approval")],
        )


class _CompliancePolicy(_DefaultPolicy):
    name = "compliance"
    version = 1
    description = "Compliance officer approval when compliance framework is set"

    def is_applicable(self, context: Any) -> bool:
        raw = getattr(context, "raw_data", {}) or {}
        return bool(raw.get("compliance_framework") or raw.get("compliance_required"))

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.COMPLIANCE_OFFICER]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SINGLE,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.9,
            reasons=[("COMPLIANCE_REQUIRED", "Compliance framework requires officer review")],
        )


class _ApplicationOwnerPolicy(_DefaultPolicy):
    name = "application_owner"
    version = 1
    description = "Application owner approval when asset has an app owner"

    def is_applicable(self, context: Any) -> bool:
        raw = getattr(context, "raw_data", {}) or {}
        return bool(raw.get("application_owner") or raw.get("application_id"))

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.APPLICATION_OWNER]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SINGLE,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.8,
            reasons=[("APP_OWNER", "Application owner must approve")],
        )


class _RepositoryOwnerPolicy(_DefaultPolicy):
    name = "repository_owner"
    version = 1
    description = "Repository owner approval when repo_id is set"

    def is_applicable(self, context: Any) -> bool:
        raw = getattr(context, "raw_data", {}) or {}
        return bool(raw.get("repo_id") or raw.get("repository_owner"))

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.REPOSITORY_OWNER]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SINGLE,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.8,
            reasons=[("REPO_OWNER", "Repository owner must approve")],
        )


class _MaintenanceWindowPolicy(_DefaultPolicy):
    name = "maintenance_window"
    version = 1
    description = "Bypass approval when an explicit maintenance window is active"

    def is_applicable(self, context: Any) -> bool:
        raw = getattr(context, "raw_data", {}) or {}
        return bool(raw.get("in_maintenance_window") or raw.get("maintenance_window_id"))

    def requires_approval(self, context: Any) -> bool:
        return False

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return []

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=False,
            required_roles=[],
            requirement_mode=ApprovalRequirementMode.AUTOMATIC_APPROVAL,
            auto_approve=True,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.95,
            reasons=[("MAINTENANCE_WINDOW", "Active maintenance window permits execution")],
        )


class _EmergencyPolicy(_DefaultPolicy):
    name = "emergency"
    version = 1
    description = "Emergency override: security team approval + audit trail"

    def is_applicable(self, context: Any) -> bool:
        return self._is_emergency(context)

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [ApprovalActorRole.EMERGENCY_OVERRIDE, ApprovalActorRole.SECURITY_TEAM]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.SEQUENTIAL,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=1.0,
            reasons=[("EMERGENCY_MODE", "Emergency override requires security + emergency approver")],
        )


class _LowRiskAutomaticPolicy(_DefaultPolicy):
    name = "low_risk_automatic"
    version = 1
    description = "Auto-approve when risk is negligible"

    def is_applicable(self, context: Any) -> bool:
        return self._cvss(context) < 0.4 and self._criticality(context) < 0.3

    def requires_approval(self, context: Any) -> bool:
        return False

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return []

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=False,
            required_roles=[],
            requirement_mode=ApprovalRequirementMode.AUTOMATIC_APPROVAL,
            auto_approve=True,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.9,
            reasons=[("LOW_RISK", "Risk profile below automatic approval threshold")],
        )


class _HighRiskAutomaticRejectionPolicy(_DefaultPolicy):
    name = "high_risk_automatic_rejection"
    version = 1
    description = "Auto-reject when CVSS ≥ 9.5 and emergency is not set"

    def is_applicable(self, context: Any) -> bool:
        return self._cvss(context) >= 0.95 and not self._is_emergency(context)

    def requires_approval(self, context: Any) -> bool:
        return False

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return []

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=False,
            required_roles=[],
            requirement_mode=ApprovalRequirementMode.AUTOMATIC_REJECTION,
            auto_approve=False,
            auto_reject=True,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=1.0,
            reasons=[("CRITICAL_RISK", "Critical risk with no emergency override → auto-rejected")],
        )


class _MajorityPolicy(_DefaultPolicy):
    name = "majority_approval"
    version = 1
    description = "Majority approval across security + platform + business"

    def is_applicable(self, context: Any) -> bool:
        raw = getattr(context, "raw_data", {}) or {}
        return bool(raw.get("require_majority"))

    def requires_approval(self, context: Any) -> bool:
        return True

    def required_approvers(self, context: Any) -> List[ApprovalActorRole]:
        return [
            ApprovalActorRole.SECURITY_TEAM,
            ApprovalActorRole.PLATFORM_TEAM,
            ApprovalActorRole.BUSINESS_OWNER,
        ]

    def evaluate(self, context: Any) -> ApprovalPolicyResult:
        return ApprovalPolicyResult(
            requires_approval=True,
            required_roles=self.required_approvers(context),
            requirement_mode=ApprovalRequirementMode.MAJORITY,
            auto_approve=False,
            auto_reject=False,
            risk_score=self._cvss(context),
            criticality_score=self._criticality(context),
            confidence=0.85,
            reasons=[("MAJORITY_RULE", "Decision requires majority approval")],
        )


# 12 default policies
DEFAULT_APPROVAL_POLICIES: List[IApprovalPolicy] = [
    _DefaultPolicy(),
    _HighRiskSecurityPolicy(),
    _BusinessCriticalPolicy(),
    _ProductionEnvironmentPolicy(),
    _CompliancePolicy(),
    _ApplicationOwnerPolicy(),
    _RepositoryOwnerPolicy(),
    _MaintenanceWindowPolicy(),
    _EmergencyPolicy(),
    _LowRiskAutomaticPolicy(),
    _HighRiskAutomaticRejectionPolicy(),
    _MajorityPolicy(),
]


# ─────────────────────────────────────────────────────────────────────
#  Registry
# ─────────────────────────────────────────────────────────────────────
class ApprovalRegistry(IApprovalRegistry):
    """Mutable map of policy name → IApprovalPolicy descriptor.

    Sprint 3 R36: thread-safe via ``ThreadSafeRegistry[str, IApprovalPolicy]``
    so concurrent registrations from Celery workers and reads from
    FastAPI handlers don't race.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, IApprovalPolicy] = {}
        self._lock = threading.RLock()

    def register(self, policy: IApprovalPolicy) -> None:
        if not policy.name:
            raise ValidationError("Policy must have a non-empty name", field="name")
        with self._lock:
            self._policies[policy.name] = policy

    def unregister(self, name: str) -> None:
        with self._lock:
            self._policies.pop(name, None)

    def get(self, name: str) -> Optional[IApprovalPolicy]:
        with self._lock:
            return self._policies.get(name)

    def all(self) -> Dict[str, IApprovalPolicy]:
        with self._lock:
            return dict(self._policies)

    def applicable(self, context: Any) -> List[IApprovalPolicy]:
        with self._lock:
            return [p for p in self._policies.values() if p.is_applicable(context)]

    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._policies.keys())


def bootstrap_default_approval_policies(registry: ApprovalRegistry) -> None:
    """Register the 12 default policies if not already registered."""
    for policy in DEFAULT_APPROVAL_POLICIES:
        registry.register(policy)


__all__ = [
    "ApprovalRegistry",
    "DEFAULT_APPROVAL_POLICIES",
    "bootstrap_default_approval_policies",
]
