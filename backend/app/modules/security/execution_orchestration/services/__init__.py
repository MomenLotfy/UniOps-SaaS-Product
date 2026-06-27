"""
Execution Orchestration Engine — services subpackage.

Public surface (mirroring the decision_approval.services layout):

  Composition:
    ExecutionPreparationService     — snapshot Decision+Strategy+Approval+Context
    ExecutionPackageFactory         — snapshot → ExecutionCandidateData
    ExecutionPackageBuilder         — candidate → ORM rows
    ExecutionPackageValidator       — pre-build deterministic validation
    ExecutionPackageSerializer      — JSON-friendly (de)serialization

  Readiness + Constraints:
    ExecutionReadinessEngine        — coordinates the 12 pluggable checks
    ExecutionDependencyResolver     — resolves 10 dependency kinds
    ExecutionConstraintValidator    — validates 12 hard constraints

  Lifecycle + Versioning:
    ExecutionLifecycleManager       — state transitions + audit
    ExecutionVersionManager         — snapshot rows

  Persistence + Audit:
    ExecutionRepository             — SQLAlchemy persistence
    ExecutionStatisticsService      — per-tenant metrics
    ExecutionAuditService           — append-only ledger

  Caching:
    ExecutionCache                  — TTL in-memory cache

  Pipeline + Facade:
    ExecutionPipeline               — 7-stage orchestrator
    ExecutionOrchestrator           — high-level public façade
    ExecutionService                — read-only API facade
"""
from __future__ import annotations

# Composition
from .execution_preparation_service import ExecutionPreparationService
from .execution_package_factory import ExecutionPackageFactory
from .execution_package_builder import ExecutionPackageBuilder
from .execution_package_validator import ExecutionPackageValidator
from .execution_package_serializer import (
    ExecutionPackageSerializer,
    deserialize_candidate,
    serialize_candidate,
    serialize_result,
)

# Readiness + Constraints
from .execution_readiness_engine import (
    DEFAULT_READINESS_CHECKS,
    ApprovalCompleteCheck,
    AssetAvailableCheck,
    DecisionReadyCheck,
    DependencyGraphValidCheck,
    EnvironmentCompatibilityCheck,
    ExecutionReadinessEngine,
    ExecutionWindowCheck,
    PolicyComplianceCheck,
    RepositoryAvailableCheck,
    RequiredMetadataCheck,
    RollbackMetadataCheck,
    StrategySelectedCheck,
    TenantIsolationCheck,
    bootstrap_default_readiness_checks,
)
from .execution_dependency_resolver import ExecutionDependencyResolver
from .execution_constraint_validator import ExecutionConstraintValidator

# Lifecycle + Versioning
from .execution_lifecycle_manager import ExecutionLifecycleManager
from .execution_version_manager import ExecutionVersionManager

# Persistence + Audit
from .execution_repository import ExecutionRepository
from .execution_statistics_service import ExecutionStatisticsService
from .execution_audit_service import ExecutionAuditService

# Cache
from .execution_cache import ExecutionCache

# Pipeline + Facade
from .execution_pipeline import ExecutionPipeline
from .execution_orchestrator import ExecutionOrchestrator
from .execution_service import ExecutionService

# Interfaces
from .execution_interfaces import (
    ExecutionCandidateData,
    ExecutionConstraintSpec,
    ExecutionDependencySpec,
    ExecutionEvaluationResult,
    ExecutionPreparationSnapshot,
    ExecutionRequirementSpec,
    IExecutionCache,
    IExecutionConstraintValidator,
    IExecutionDependencyResolver,
    IExecutionLifecycleManager,
    IExecutionPreparationService,
    IExecutionReadinessCheck,
    IExecutionReadinessEngine,
    IExecutionRepository,
    IExecutionValidator,
    ReadinessFactorResult,
)


__all__ = [
    # Composition
    "ExecutionPreparationService",
    "ExecutionPackageFactory",
    "ExecutionPackageBuilder",
    "ExecutionPackageValidator",
    "ExecutionPackageSerializer",
    "serialize_candidate",
    "deserialize_candidate",
    "serialize_result",

    # Readiness
    "DEFAULT_READINESS_CHECKS",
    "DecisionReadyCheck",
    "ApprovalCompleteCheck",
    "StrategySelectedCheck",
    "RepositoryAvailableCheck",
    "AssetAvailableCheck",
    "DependencyGraphValidCheck",
    "RequiredMetadataCheck",
    "TenantIsolationCheck",
    "PolicyComplianceCheck",
    "EnvironmentCompatibilityCheck",
    "ExecutionWindowCheck",
    "RollbackMetadataCheck",
    "ExecutionReadinessEngine",
    "bootstrap_default_readiness_checks",
    "ExecutionDependencyResolver",
    "ExecutionConstraintValidator",

    # Lifecycle + Versioning
    "ExecutionLifecycleManager",
    "ExecutionVersionManager",

    # Persistence + Audit
    "ExecutionRepository",
    "ExecutionStatisticsService",
    "ExecutionAuditService",

    # Cache
    "ExecutionCache",

    # Pipeline + Facade
    "ExecutionPipeline",
    "ExecutionOrchestrator",
    "ExecutionService",

    # Interfaces
    "ExecutionCandidateData",
    "ExecutionConstraintSpec",
    "ExecutionDependencySpec",
    "ExecutionEvaluationResult",
    "ExecutionPreparationSnapshot",
    "ExecutionRequirementSpec",
    "IExecutionCache",
    "IExecutionConstraintValidator",
    "IExecutionDependencyResolver",
    "IExecutionLifecycleManager",
    "IExecutionPreparationService",
    "IExecutionReadinessCheck",
    "IExecutionReadinessEngine",
    "IExecutionRepository",
    "IExecutionValidator",
    "ReadinessFactorResult",
]   # 16 services + 11 data interfaces + 12 readiness checks