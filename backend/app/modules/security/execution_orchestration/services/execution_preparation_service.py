"""
Execution Preparation Service.

Snapshots the upstream inputs (Decision + Strategy + Approval + raw
context) into an `ExecutionPreparationSnapshot` before the pipeline
starts.

Mirrors `decision_approval/services/approval_context_builder.py`.

No I/O.  Pure deterministic aggregation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .execution_interfaces import (
    ExecutionPreparationSnapshot,
    IExecutionPreparationService,
)


# Fields that MUST be present on the decision for the package to be
# buildable.  Missing any of these forces an early rejection.
_MANDATORY_DECISION_FIELDS = (
    "id",
    "tenant_id",
    "decision_state",
    "final_result",
)

_MANDATORY_STRATEGY_FIELDS = (
    "id",
    "strategy_state",
)

_MANDATORY_APPROVAL_FIELDS = (
    "id",
    "approval_state",
)


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


class ExecutionPreparationService(IExecutionPreparationService):
    """
    Captures every input the orchestrator needs before any I/O.

    The pipeline calls `.prepare(...)` exactly once.  Downstream
    stages read from the returned `ExecutionPreparationSnapshot`.
    """

    def prepare(
        self,
        decision: Any,
        strategy: Any = None,
        approval: Any = None,
        *,
        tenant_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPreparationSnapshot:
        if decision is None:
            raise ValueError("Decision is required for execution preparation")

        if tenant_id is None:
            tenant_id = _safe_getattr(decision, "tenant_id", "default")

        decision_id = _safe_getattr(decision, "id", "unknown")
        strategy_id = _safe_getattr(strategy, "id", None) if strategy is not None else None
        approval_id = _safe_getattr(approval, "id", None) if approval is not None else None

        missing: List[str] = []

        for field_name in _MANDATORY_DECISION_FIELDS:
            if not _is_present(_safe_getattr(decision, field_name, None)):
                missing.append(f"decision.{field_name}")

        if strategy is not None:
            for field_name in _MANDATORY_STRATEGY_FIELDS:
                if not _is_present(_safe_getattr(strategy, field_name, None)):
                    missing.append(f"strategy.{field_name}")

        if approval is not None:
            for field_name in _MANDATORY_APPROVAL_FIELDS:
                if not _is_present(_safe_getattr(approval, field_name, None)):
                    missing.append(f"approval.{field_name}")

        decision_snapshot = self._snapshot_object(decision)
        strategy_snapshot = self._snapshot_object(strategy) if strategy is not None else {}
        approval_snapshot = self._snapshot_object(approval) if approval is not None else {}
        context_snapshot = dict(raw_data or {})

        return ExecutionPreparationSnapshot(
            tenant_id=str(tenant_id),
            decision_id=str(decision_id),
            strategy_id=str(strategy_id) if strategy_id is not None else None,
            approval_id=str(approval_id) if approval_id is not None else None,
            decision_snapshot=decision_snapshot,
            strategy_snapshot=strategy_snapshot,
            approval_snapshot=approval_snapshot,
            context_snapshot=context_snapshot,
            missing_fields=missing,
            is_complete=len(missing) == 0,
        )

    # ── helpers ───────────────────────────────────────────────────
    @staticmethod
    def _snapshot_object(obj: Any) -> Dict[str, Any]:
        """Convert an arbitrary object into a JSON-friendly dict."""
        if obj is None:
            return {}
        # If already a dict, copy it.
        if isinstance(obj, dict):
            return dict(obj)
        # SQLAlchemy declarative instance — read declared columns.
        out: Dict[str, Any] = {}
        mapper = getattr(obj, "__mapper__", None)
        if mapper is not None:
            for column in mapper.columns:
                value = getattr(obj, column.key, None)
                out[column.key] = ExecutionPreparationService._jsonify(value)
        # Anything else: take __dict__
        if not out:
            for key, value in vars(obj).items():
                if key.startswith("_"):
                    continue
                out[key] = ExecutionPreparationService._jsonify(value)
        return out

    @staticmethod
    def _jsonify(value: Any) -> Any:
        """Recursively convert enums/datetimes to JSON-friendly scalars."""
        # Enums
        if hasattr(value, "value") and hasattr(value, "__class__") and not isinstance(value, (str, int, float, bool)):
            return getattr(value, "value")
        # datetimes
        if hasattr(value, "isoformat") and callable(value.isoformat):
            try:
                return value.isoformat()
            except Exception:  # pragma: no cover - defensive
                return str(value)
        # dicts / lists — recurse
        if isinstance(value, dict):
            return {k: ExecutionPreparationService._jsonify(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [ExecutionPreparationService._jsonify(v) for v in value]
        return value


__all__ = ["ExecutionPreparationService"]