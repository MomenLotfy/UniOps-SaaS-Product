# Decision Strategy Engine

**Module 0 / Part 4** of the EPIC 10 Decision subsystem.

Deterministic selection of a remediation **strategy** — *not* the
remediation itself.  This module decides *how* a known issue will be
addressed (PATCH_EXISTING_VERSION, UPGRADE_PACKAGE, NO_ACTION, etc.);
actual execution lives in later modules.

## Components

- **13 canonical models** under `models/strategy.py`
- **18 service classes** under `services/`
- **17 strategy types** registered by default (extensible via
  `DecisionStrategyRegistry.register(...)`)
- **10-dimension scoring** with deterministic weighted sum
- **4-step comparator** for stable ranking
- **7-stage pipeline** (Discovery → Selection → Persistence)
- **Read-only API** at `/security/decision-strategies/*`

## API

| Endpoint                                          | Description              |
|---------------------------------------------------|--------------------------|
| `GET /security/decision-strategies/`              | List strategies          |
| `GET /security/decision-strategies/{id}`          | Strategy detail          |
| `GET /security/decision-strategies/statistics`    | Tenant-wide metrics      |
| `GET /security/decision-strategies/history/{id}`  | State-transition history |

All endpoints are **READ-ONLY**.

## Pipeline usage

```python
from app.modules.security.decision_strategy import (
    DecisionStrategyEngine,
    StrategyEvaluationPipeline,
)

engine = DecisionStrategyEngine(cache_enabled=True)
pipeline = StrategyEvaluationPipeline(db, engine=engine)
result = await pipeline.run(decision, context)
# result.winner.candidate_type      # chosen strategy
# result.candidates                 # full ranked list
# result.winning_strategy_id        # persisted row id
```

## Tests

- `tests/unit/test_decision_strategy.py` — 20 tests covering
  registry bootstrap, scoring, comparator, ranking, validator,
  engine end-to-end + cache.
- `tests/integration/test_decision_strategy_pipeline.py` — 4 tests
  covering the full 7-stage pipeline + lifecycle transitions.

Run:
```bash
pytest tests/unit/test_decision_strategy.py -v
pytest tests/integration/test_decision_strategy_pipeline.py -v
```

## Migration

`alembic/versions/010_decision_strategy_tables.py` creates all 13
tables.  `down_revision = "009_detected_by"`.

## Non-goals (deferred to later modules)

- Remediation execution
- Git operations / patch generation
- Pull request creation
- AI-driven decision making
- Approval workflow
- Deployment
- Rollback execution