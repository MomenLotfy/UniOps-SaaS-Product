# Execution Orchestration Engine

**Module 0 / Part 6** of the EPIC 10 Decision subsystem.

Prepares approved decisions for the future Remediation Engine.  This
module **does not** execute remediation — it produces immutable,
deterministic `ExecutionPackage` artifacts ready for hand-off.

High-level flow:

```
Security Finding → Decision Context → Rule Engine → Decision Plan →
Strategy → Approval → Execution Orchestrator → Execution Package →
Future Remediation Engine.
```

Everything stops after producing the `ExecutionPackage`.  No patches,
no git operations, no deployments, no rollbacks, no execution plugins,
no infrastructure changes.

## Components

- **12 canonical models** under `models/execution.py`
- **16 service classes** under `services/`
- **12 readiness checks** registered by default (one per `ReadinessFactor`)
- **10-state lifecycle** (CREATED → ARCHIVED)
- **7-stage pipeline** (Preparation → Audit)
- **Read-only API** at `/security/execution-packages/*`

## API

| Endpoint                                              | Description              |
|-------------------------------------------------------|--------------------------|
| `GET /security/execution-packages/`                   | List packages            |
| `GET /security/execution-packages/{id}`               | Package detail           |
| `GET /security/execution-packages/{id}/preparation`   | Pre-pipeline snapshot    |
| `GET /security/execution-packages/{id}/readiness`     | Readiness verdict        |
| `GET /security/execution-packages/{id}/dependencies`  | Resolved dependencies    |
| `GET /security/execution-packages/{id}/constraints`   | Hard constraints         |
| `GET /security/execution-packages/{id}/requirements`  | Soft requirements        |
| `GET /security/execution-packages/{id}/metadata`      | Free-form metadata       |
| `GET /security/execution-packages/{id}/history`       | State-transition history |
| `GET /security/execution-packages/{id}/audit`         | Append-only ledger       |
| `GET /security/execution-packages/{id}/versions`      | Versioned snapshots      |
| `GET /security/execution-packages/{id}/statistics`    | Per-package metrics      |
| `GET /security/execution-packages/{id}/summary`       | Denormalised summary     |
| `GET /security/execution-packages/statistics`         | Tenant-wide metrics      |

All endpoints are **READ-ONLY**.  Packages are created internally by
the `ExecutionPipeline`.

## Pipeline usage

```python
from app.modules.security.execution_orchestration import (
    ExecutionOrchestrator,
)

orchestrator = ExecutionOrchestrator(db)
result = await orchestrator.orchestrate(
    decision, strategy=strategy, approval=approval,
    tenant_id="t1",
    raw_data={
        "repository_id":        "repo-1",
        "asset_id":             "asset-1",
        "policy_compliance":    "PASSED",
        "environment":          "PROD",
        "target_environment":   "PROD",
        "execution_window_open": True,
    },
    metadata=[("rollback_strategy", "git revert"), ("owner", "sec-team")],
    summary="Apply security patch",
)
# result.package_id                 # persisted row id
# result.final_state                # ExecutionPackageState.READY / REJECTED
# result.candidate.rejection_reason # canonical rejection code, if any
```

## Readiness factors

12 pluggable factors, one per `ReadinessFactor`:

| Factor                   | Default check                  | Severity |
|--------------------------|--------------------------------|----------|
| `DECISION_READY`         | Decision state is buildable    | HARD     |
| `APPROVAL_COMPLETE`      | Approval is APPROVED           | HARD     |
| `STRATEGY_SELECTED`      | Strategy is selected/approved  | HARD     |
| `REPOSITORY_AVAILABLE`   | Repository reference present   | HARD     |
| `ASSET_AVAILABLE`        | Asset reference present        | HARD     |
| `DEPENDENCY_GRAPH_VALID` | No orphan dependencies         | HARD     |
| `REQUIRED_METADATA`      | Required metadata keys present | HARD     |
| `TENANT_ISOLATION`       | Tenant ids match               | HARD     |
| `POLICY_COMPLIANCE`      | Policy verdict is PASSED       | HARD     |
| `ENVIRONMENT_COMPAT`     | Environment matches target     | HARD     |
| `EXECUTION_WINDOW`       | Execution window is open       | HARD     |
| `ROLLBACK_METADATA`      | Rollback strategy captured     | HARD     |

A new factor + check can be added without engine changes by calling
`ExecutionReadinessEngine.register(factor, check)`.

## States

```
NULL → CREATED → READINESS_VALIDATING → READINESS_PASSED
                                       ├→ BUILDING → BUILT → READY
                                       ├→ REJECTED
                                       └→ READINESS_FAILED → REJECTED
   Any non-terminal → ARCHIVED (terminal)
```

## Observability

Per-tenant metrics emitted via `ExecutionStatisticsService`:

| Metric                          | Where it lives                              |
|---------------------------------|---------------------------------------------|
| `Execution Package Creation Time` | `ExecutionStatistics.avg_duration_ms`    |
| `Readiness Validation Duration`   | `ExecutionReadiness.validation_ms`        |
| `Dependency Resolution Duration`  | `ExecutionDependency.resolution_ms` (avg) |
| `Constraint Validation Duration`  | derived from readiness timing             |
| `Rejected Packages`               | `ExecutionStatistics.rejected_count`      |
| `Package Creation Count`          | `ExecutionStatistics.count`               |
| `Average Package Size`            | `ExecutionStatistics.avg_package_size_kb` |
| `Preparation Latency`             | `ExecutionReadiness.validation_ms`        |

## Architecture guarantee

When the future Remediation Engine begins consuming packages, it
will read from these tables only.  No refactoring required.