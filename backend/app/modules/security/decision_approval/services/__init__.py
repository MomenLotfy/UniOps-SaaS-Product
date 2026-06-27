"""
Approval Engine — services subpackage.

Public surface (mirroring the decision_strategy.services layout):

  Engine + Pipeline:
    ApprovalEngine                  — orchestrator (composition root)
    ApprovalEvaluationPipeline      — 7-stage pipeline

  Composition:
    ApprovalRegistry                — pluggable policy registry (12 defaults)
    ApprovalFactory                 — policy-verdict → ApprovalCandidateData
    ApprovalResolver                — policy discovery + aggregation
    ApprovalScoringEngine           — factor-based composite scoring
    ApprovalCache                   — TTL in-memory cache

  Lifecycle + Versioning:
    ApprovalLifecycleManager        — state transitions + audit
    ApprovalVersionManager          — snapshot rows

  Persistence + Audit:
    ApprovalRepository              — SQLAlchemy persistence
    ApprovalStatisticsService       — per-tenant metrics
    ApprovalAuditService            — append-only audit ledger

  Facade:
    ApprovalContextBuilder          — Decision+Strategy → ApprovalContext
    ApprovalService                 — read-only API facade
    ApprovalManager                 — public lifecycle API
    ApprovalValidator               — request validation

  Notifications:
    ApprovalNotificationService     — notification intent STUB only

  Extension points:
    IApprovalPolicy                 — register new policies
    IApprovalEvaluator              — register new factor evaluators
"""
from __future__ import annotations

# Core
from .approval_interfaces import (
    ApprovalCandidateData,
    ApprovalEvaluationResult,
    ApprovalPolicyResult,
    ApprovalRequirementSpec,
    IApprovalEvaluator,
    IApprovalLifecycleManager,
    IApprovalPolicy,
    IApprovalRegistry,
    IApprovalRepository,
    IApprovalResolver,
    IApprovalValidator,
)

# Composition
from .approval_registry import (
    ApprovalRegistry,
    DEFAULT_APPROVAL_POLICIES,
    bootstrap_default_approval_policies,
)
from .approval_factory import ApprovalFactory
from .approval_resolver import ApprovalResolver
from .approval_evaluator import (
    ApprovalScoringEngine,
    AutomationEvaluator,
    ComplianceEvaluator,
    CriticalityEvaluator,
    DEFAULT_APPROVAL_EVALUATORS,
    HistoryEvaluator,
    OwnerEvaluator,
    RiskEvaluator,
    UrgencyEvaluator,
)
from .approval_cache import ApprovalCache
from .approval_validator import ApprovalValidator

# Context
from .approval_context_builder import ApprovalContext, ApprovalContextBuilder

# Lifecycle + Versioning
from .approval_lifecycle_manager import ApprovalLifecycleManager
from .approval_version_manager import ApprovalVersionManager

# Persistence + Audit
from .approval_repository import ApprovalRepository
from .approval_statistics_service import ApprovalStatisticsService
from .approval_audit_service import ApprovalAuditService
from .approval_notification_service import ApprovalNotificationService

# Serializer
from .approval_serializer import (
    ApprovalSerializer,
    deserialize_candidate,
    serialize_candidate,
)

# Engine + Pipeline + Facade
from .approval_engine import ApprovalEngine
from .approval_pipeline import ApprovalEvaluationPipeline
from .approval_policy_engine import ApprovalPolicyEngine
from .approval_service import ApprovalService
from .approval_manager import ApprovalManager


__all__ = [
    # Interfaces
    "IApprovalPolicy",
    "IApprovalEvaluator",
    "IApprovalResolver",
    "IApprovalValidator",
    "IApprovalRepository",
    "IApprovalLifecycleManager",
    "ApprovalPolicyResult",
    "ApprovalRequirementSpec",
    "ApprovalCandidateData",
    "ApprovalEvaluationResult",

    # Composition
    "ApprovalRegistry",
    "bootstrap_default_approval_policies",
    "DEFAULT_APPROVAL_POLICIES",
    "ApprovalFactory",
    "ApprovalResolver",
    "ApprovalScoringEngine",
    "ApprovalCache",
    "ApprovalValidator",

    # Default evaluators
    "AutomationEvaluator",
    "ComplianceEvaluator",
    "CriticalityEvaluator",
    "DEFAULT_APPROVAL_EVALUATORS",
    "HistoryEvaluator",
    "OwnerEvaluator",
    "RiskEvaluator",
    "UrgencyEvaluator",

    # Context
    "ApprovalContext",
    "ApprovalContextBuilder",

    # Lifecycle + Versioning
    "ApprovalLifecycleManager",
    "ApprovalVersionManager",

    # Persistence + Audit
    "ApprovalRepository",
    "ApprovalStatisticsService",
    "ApprovalAuditService",
    "ApprovalNotificationService",

    # Serializer
    "ApprovalSerializer",
    "serialize_candidate",
    "deserialize_candidate",

    # Engine + Pipeline + Facade
    "ApprovalEngine",
    "ApprovalEvaluationPipeline",
    "ApprovalPolicyEngine",
    "ApprovalService",
    "ApprovalManager",
]   # 17 services + 9 dataclasses / interfaces