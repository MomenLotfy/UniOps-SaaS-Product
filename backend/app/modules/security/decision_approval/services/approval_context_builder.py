"""
Approval Context Builder.

Aggregates the data needed for an approval evaluation: decision +
strategy + tenant policies + raw context.  Mirrors `context_build.py`
in the decision_engine module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..constants import ApprovalType


@dataclass
class ApprovalContext:
    """Aggregated view of everything the engine needs to evaluate."""
    decision: Any
    strategy: Optional[Any]
    tenant_id: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None


class ApprovalContextBuilder:
    """
    Builds `ApprovalContext` objects from a Decision + (optional) Strategy.

    The builder is intentionally tolerant — missing fields become
    `None` and the engine handles them gracefully.
    """

    def build(
        self,
        decision: Any,
        strategy: Optional[Any] = None,
        *,
        tenant_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> ApprovalContext:
        context_tenant = (
            tenant_id
            or getattr(decision, "tenant_id", None)
            or (getattr(strategy, "tenant_id", None) if strategy else None)
            or "default"
        )
        merged_raw: Dict[str, Any] = dict(raw_data or {})
        dec_raw = getattr(decision, "raw_data", None) if decision else None
        if isinstance(dec_raw, dict):
            for k, v in dec_raw.items():
                merged_raw.setdefault(k, v)
        strat_meta = getattr(strategy, "metadata_json", None) if strategy else None
        if isinstance(strat_meta, dict):
            for k, v in strat_meta.items():
                merged_raw.setdefault(k, v)
        return ApprovalContext(
            decision=decision,
            strategy=strategy,
            tenant_id=context_tenant,
            raw_data=merged_raw,
            correlation_id=getattr(decision, "correlation_id", None),
            trace_id=getattr(decision, "trace_id", None),
        )

    def derive_approval_type(self, decision: Any, strategy: Optional[Any]) -> ApprovalType:
        """Choose an ApprovalType from the Decision.final_result / Strategy hints."""
        result = (getattr(decision, "final_result", "") or "").upper()
        if result in ("ROTATE",):
            return ApprovalType.SECURITY
        if result in ("PATCH",):
            return ApprovalType.SECURITY
        if result in ("MITIGATE", "UPGRADE"):
            return ApprovalType.PLATFORM
        if result in ("REVIEW",):
            return ApprovalType.BUSINESS
        return ApprovalType.SECURITY


__all__ = ["ApprovalContext", "ApprovalContextBuilder"]