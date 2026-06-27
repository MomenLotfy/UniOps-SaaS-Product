"""
Unit tests for the Execution Orchestration Engine.

Covers pure-function behaviour that doesn't need a DB session:
  - constants / state machine
  - dataclass round-trips
  - serializer round-trip
  - cache TTL behaviour
  - dependency resolver field mapping
"""
from types import SimpleNamespace

from app.modules.security.execution_orchestration.constants import (
    ExecutionConstraintType,
    ExecutionDependencyKind,
    ExecutionPackageState,
    ReadinessFactor,
    ReadinessOutcome,
    TERMINAL_EXECUTION_STATES,
    VALID_EXECUTION_TRANSITIONS,
)


# ─────────────────────────────────────────────────────────────────────
#  State machine
# ─────────────────────────────────────────────────────────────────────
def test_state_machine_initial_transition_is_to_created():
    assert VALID_EXECUTION_TRANSITIONS[None] == [ExecutionPackageState.CREATED]


def test_state_machine_terminal_state_is_only_archived():
    assert TERMINAL_EXECUTION_STATES == {ExecutionPackageState.ARCHIVED}
    # Everything else must have a non-empty transition list (or be the
    # terminal state itself).
    for state, transitions in VALID_EXECUTION_TRANSITIONS.items():
        if state is None:
            continue
        if state in TERMINAL_EXECUTION_STATES:
            assert transitions == [], f"{state} should have no outgoing transitions"
        else:
            assert len(transitions) > 0, f"{state} has no outgoing transitions"


def test_state_machine_ready_can_only_archive():
    assert VALID_EXECUTION_TRANSITIONS[ExecutionPackageState.READY] == [
        ExecutionPackageState.ARCHIVED,
    ]


# ─────────────────────────────────────────────────────────────────────
#  Readiness + constraint enums
# ─────────────────────────────────────────────────────────────────────
def test_twelve_readiness_factors():
    assert len(ReadinessFactor) == 12


def test_twelve_constraint_types():
    assert len(ExecutionConstraintType) == 12


def test_ten_dependency_kinds():
    assert len(ExecutionDependencyKind) == 10


def test_one_to_one_constraint_to_factor_mapping():
    from app.modules.security.execution_orchestration.services.execution_constraint_validator import (
        _CONSTRAINT_TO_FACTOR,
    )
    assert len(_CONSTRAINT_TO_FACTOR) == 12
    assert set(_CONSTRAINT_TO_FACTOR.keys()) == set(ExecutionConstraintType)


# ─────────────────────────────────────────────────────────────────────
#  Dependency resolver mapping
# ─────────────────────────────────────────────────────────────────────
def test_dependency_resolver_covers_every_kind():
    from app.modules.security.execution_orchestration.services import (
        ExecutionDependencyResolver,
    )
    expected = set(ExecutionDependencyKind)
    mapped = set(ExecutionDependencyResolver._REFERENCE_FIELD_MAP.keys())
    assert expected == mapped


# ─────────────────────────────────────────────────────────────────────
#  Dataclass round-trips
# ─────────────────────────────────────────────────────────────────────
def test_candidate_data_defaults():
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionCandidateData,
    )
    cand = ExecutionCandidateData()
    assert cand.is_valid is True
    assert cand.rejection_reason is None
    assert cand.dependencies == []
    assert cand.constraints == []


def test_evaluation_result_defaults():
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionEvaluationResult,
    )
    r = ExecutionEvaluationResult(tenant_id="t1", decision_id="d1")
    assert r.package_id is None
    assert r.final_state == ExecutionPackageState.CREATED


# ─────────────────────────────────────────────────────────────────────
#  Serializer
# ─────────────────────────────────────────────────────────────────────
def test_serializer_handles_empty_candidate():
    from app.modules.security.execution_orchestration.services import (
        serialize_candidate, serialize_result,
    )
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionCandidateData, ExecutionEvaluationResult,
    )
    cand_payload = serialize_candidate(ExecutionCandidateData())
    assert cand_payload == {}

    result_payload = serialize_result(ExecutionEvaluationResult(tenant_id="t1", decision_id="d1"))
    assert result_payload["tenant_id"] == "t1"
    assert result_payload["candidate"] is None


# ─────────────────────────────────────────────────────────────────────
#  Cache
# ─────────────────────────────────────────────────────────────────────
def test_cache_miss_returns_none():
    from app.modules.security.execution_orchestration.services import ExecutionCache
    cache = ExecutionCache()
    assert cache.get("t", "d", SimpleNamespace()) is None


def test_cache_invalidate_clears_tenant_scope():
    from app.modules.security.execution_orchestration.services import ExecutionCache
    from app.modules.security.execution_orchestration.services.execution_interfaces import (
        ExecutionEvaluationResult,
    )
    cache = ExecutionCache()
    ctx = SimpleNamespace(raw_data={"x": 1})
    cache.put("t1", "d1", ctx, ExecutionEvaluationResult(tenant_id="t1", decision_id="d1"))
    cache.put("t2", "d2", ctx, ExecutionEvaluationResult(tenant_id="t2", decision_id="d2"))
    cache.invalidate("t1")
    assert cache.get("t1", "d1", ctx) is None
    assert cache.get("t2", "d2", ctx) is not None
    cache.invalidate()  # clear all
    assert cache.get("t2", "d2", ctx) is None