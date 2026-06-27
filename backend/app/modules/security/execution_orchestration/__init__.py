"""
Execution Orchestration Engine (Module 0 / Part 6).

Prepares approved decisions for future execution by the Remediation
Engine.  This module DOES NOT execute remediation — it produces
immutable, deterministic `ExecutionPackage` artifacts ready for
hand-off.

High-level flow:
  Security Finding → Decision Context → Rule Engine → Decision Plan →
  Strategy → Approval → Execution Orchestrator → Execution Package →
  Future Remediation Engine.

Public entry points:
  - `ExecutionOrchestrator.orchestrate(...)`  → produce a package
  - `ExecutionPipeline.run(...)`               → 7-stage pipeline
  - `ExecutionService`                          → read-only API facade
"""
from __future__ import annotations

from .constants import (
    EXECUTION_CACHE_TTL_SECONDS,
    ExecutionAuditEvent,
    ExecutionConstraintType,
    ExecutionDependencyKind,
    ExecutionPackageState,
    ExecutionPipelineStage,
    ExecutionRejectionReason,
    ReadinessFactor,
    ReadinessOutcome,
    TERMINAL_EXECUTION_STATES,
    VALID_EXECUTION_TRANSITIONS,
)
from .models import (
    ExecutionAudit,
    ExecutionConstraint,
    ExecutionDependency,
    ExecutionHistory,
    ExecutionMetadata,
    ExecutionPackage,
    ExecutionPreparation,
    ExecutionReadiness,
    ExecutionRequirement,
    ExecutionStatistics,
    ExecutionSummary,
    ExecutionVersion,
)
from .services import (
    DEFAULT_READINESS_CHECKS,
    ApprovalCompleteCheck,
    AssetAvailableCheck,
    DecisionReadyCheck,
    DependencyGraphValidCheck,
    EnvironmentCompatibilityCheck,
    ExecutionAuditService,
    ExecutionCache,
    ExecutionConstraintValidator,
    ExecutionDependencyResolver,
    ExecutionLifecycleManager,
    ExecutionOrchestrator,
    ExecutionPackageBuilder,
    ExecutionPackageFactory,
    ExecutionPackageSerializer,
    ExecutionPackageValidator,
    ExecutionPipeline,
    ExecutionPreparationService,
    ExecutionReadinessEngine,
    ExecutionRepository,
    ExecutionRequirementSpec,
    ExecutionService,
    ExecutionStatisticsService,
    ExecutionVersionManager,
    PolicyComplianceCheck,
    RepositoryAvailableCheck,
    RequiredMetadataCheck,
    RollbackMetadataCheck,
    StrategySelectedCheck,
    TenantIsolationCheck,
    ExecutionCandidateData,
    ExecutionConstraintSpec,
    ExecutionDependencySpec,
    ExecutionEvaluationResult,
    ExecutionPreparationSnapshot,
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
    ExecutionWindowCheck,
    bootstrap_default_readiness_checks,
    deserialize_candidate,
    serialize_candidate,
    serialize_result,
)
from .api import router as execution_router


__all__ = [
    # Constants
    "EXECUTION_CACHE_TTL_SECONDS",
    "ExecutionAuditEvent",
    "ExecutionConstraintType",
    "ExecutionDependencyKind",
    "ExecutionPackageState",
    "ExecutionPipelineStage",
    "ExecutionRejectionReason",
    "ReadinessFactor",
    "ReadinessOutcome",
    "TERMINAL_EXECUTION_STATES",
    "VALID_EXECUTION_TRANSITIONS",

    # Models (12)
    "ExecutionAudit",
    "ExecutionConstraint",
    "ExecutionDependency",
    "ExecutionHistory",
    "ExecutionMetadata",
    "ExecutionPackage",
    "ExecutionPreparation",
    "ExecutionReadiness",
    "ExecutionRequirement",
    "ExecutionStatistics",
    "ExecutionSummary",
    "ExecutionVersion",

    # Services (16)
    "DEFAULT_READINESS_CHECKS",
    "ApprovalCompleteCheck",
    "AssetAvailableCheck",
    "DecisionReadyCheck",
    "DependencyGraphValidCheck",
    "EnvironmentCompatibilityCheck",
    "ExecutionAuditService",
    "ExecutionCache",
    "ExecutionConstraintValidator",
    "ExecutionDependencyResolver",
    "ExecutionLifecycleManager",
    "ExecutionOrchestrator",
    "ExecutionPackageBuilder",
    "ExecutionPackageFactory",
    "ExecutionPackageSerializer",
    "ExecutionPackageValidator",
    "ExecutionPipeline",
    "ExecutionPreparationService",
    "ExecutionReadinessEngine",
    "ExecutionRepository",
    "ExecutionService",
    "ExecutionStatisticsService",
    "ExecutionVersionManager",
    "PolicyComplianceCheck",
    "RepositoryAvailableCheck",
    "RequiredMetadataCheck",
    "RollbackMetadataCheck",
    "StrategySelectedCheck",
    "TenantIsolationCheck",
    "ExecutionWindowCheck",
    "bootstrap_default_readiness_checks",

    # Data + Interfaces
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
    "deserialize_candidate",
    "serialize_candidate",
    "serialize_result",

    # API
    "execution_router",
]   # 12 models + 16 services + 12 readiness checks + 10 interfaces