# Decision Approval Engine

**Module 0 / Part 5** of the EPIC 10 Decision subsystem.

Deterministic evaluation of approval requirements — *not* the
approvals themselves (those happen out-of-band by humans or a
later module).  This module decides **whether** approval is required,
**who** must approve, **which policy** applies, and **whether**
execution is blocked.

## Components

- **15 canonical models** under `models/approval.py`
- **17 service classes** under `services/`
- **12 policy descriptors** registered by default (extensible via
  `ApprovalRegistry.register(...)`)
- **7-dimension factor scoring** with deterministic weighted sum
- **9-state lifecycle** (CREATED → ARCHIVED)
- **7-stage pipeline** (Discovery → Statistics Update)
- **Read-only API** at `/security/decision-approvals/*`

## API

| Endpoint                                        | Description              |
|-------------------------------------------------|--------------------------|
| `GET /security/decision-approvals/`             | List approval requests   |
| `GET /security/decision-approvals/{id}`         | Approval detail          |
| `GET /security/decision-approvals/history/{id}` | State-transition history |
| `GET /security/decision-approvals/statistics`   | Tenant-wide metrics      |
| `GET /security/decision-approvals/policies`     | Registered policies      |

All endpoints are **READ-ONLY**.

## Pipeline usage

```python
from app.modules.security.decision_approval import (
    ApprovalEngine,
    ApprovalEvaluationPipeline,
)

engine = ApprovalEngine(cache_enabled=True)
pipeline = ApprovalEvaluationPipeline(db, engine=engine)
result = await pipeline.run(decision, strategy, tenant_id="t1")
# result.candidate.requires_approval       # True/False
# result.candidate.auto_approve            # True if bypassed
# result.candidate.auto_reject             # True if blocked
# result.winning_request_id                # persisted row id
```

## States

```
NULL → CREATED → VALIDATING → WAITING_APPROVAL
                            ├→ PARTIALLY_APPROVED → APPROVED
                            ├→ REJECTED
                            ├→ EXPIRED
                            └→ CANCELLED
   Any non-terminal → ARCHIVED (terminal)
```

## Approval requirement modes

- `SINGLE` — one approver suffices
- `MULTIPLE` — N approvals, order irrelevant
- `SEQUENTIAL` — fixed order, each must approve
- `PARALLEL` — all may approve independently
- `MAJORITY` — > 50% of the chain
- `AUTOMATIC_APPROVAL` — no human required
- `AUTOMATIC_REJECTION` — auto-rejected without evaluation

## Policy factors

`BUSINESS_CRITICALITY`, `TECHNICAL_RISK`, `CVSS_SCORE`, `EPSS_SCORE`,
`ASSET_CRITICALITY`, `ENVIRONMENT`, `COMPLIANCE_FRAMEWORK`,
`CHANGE_WINDOW`, `MAINTENANCE_WINDOW`, `DEPLOYMENT_ENVIRONMENT`,
`PRODUCTION_STATUS`, `BUSINESS_OWNER`, `APPLICATION_OWNER`,
`REPOSITORY_OWNER`, `SECURITY_TEAM`, `PLATFORM_TEAM`,
`ORG_POLICY`, `TENANT_POLICY`, `EMERGENCY_MODE`, `MANUAL_OVERRIDE`.

## Tests

- `tests/unit/test_decision_approval.py` — 28 tests covering
  registry bootstrap, scoring, validator, cache, serializer, engine
  end-to-end + cache.
- `tests/integration/test_decision_approval_pipeline.py` — 5 tests
  covering the full 7-stage pipeline + lifecycle transitions.

Run:
```bash
pytest tests/unit/test_decision_approval.py -v
pytest tests/integration/test_decision_approval_pipeline.py -v
```

## Migration

`alembic/versions/011_decision_approval_tables.py` creates all 15
tables.  `down_revision = "010_decision_strategy_tables"`.

## Non-goals (deferred to later modules)

- Remediation execution
- Patch generation / Git operations / Pull requests
- Deployment / Rollback execution
- **Human approval UI actions** (this module only persists the
  requirement chain — humans / external systems satisfy them)
- **Notification delivery** (the `ApprovalNotificationService` is a
  STUB that only records intent; no email/Slack is sent)
- AI approval
- Execution logic