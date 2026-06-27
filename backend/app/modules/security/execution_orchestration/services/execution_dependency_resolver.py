"""
Execution Dependency Resolver.

Resolves the references the future Remediation Engine will need in
order to act on an `ExecutionPackage` (repository, asset, CVE,
finding, policy, approval, decision, strategy, package, external).

For each `ExecutionDependencyKind` we emit one `ExecutionDependencySpec`
with `is_resolved=True/False`.  Soft references that can't be found
surface as `WARNING` in the readiness engine — they don't block
package construction.

Mirrors `decision_approval/services/approval_resolver.py`.

NO live I/O happens here — the resolver inspects the already-collected
context snapshot.  If a richer implementation wants to query live
services, it should subclass and override `resolve_kind(...)`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..constants import ExecutionDependencyKind
from .execution_interfaces import (
    ExecutionCandidateData,
    ExecutionDependencySpec,
    IExecutionDependencyResolver,
)

logger = logging.getLogger(__name__)


class ExecutionDependencyResolver(IExecutionDependencyResolver):
    """
    Pure deterministic resolver.  For each known dependency kind, asks
    the context snapshot for the corresponding reference.
    """

    _REFERENCE_FIELD_MAP: Dict[ExecutionDependencyKind, str] = {
        ExecutionDependencyKind.REPOSITORY: "repository_id",
        ExecutionDependencyKind.ASSET:      "asset_id",
        ExecutionDependencyKind.CVE:        "cve_id",
        ExecutionDependencyKind.FINDING:    "finding_id",
        ExecutionDependencyKind.POLICY:     "policy_id",
        ExecutionDependencyKind.APPROVAL:   "approval_id",
        ExecutionDependencyKind.DECISION:   "decision_id",
        ExecutionDependencyKind.STRATEGY:   "strategy_id",
        ExecutionDependencyKind.PACKAGE:    "package_id",
        ExecutionDependencyKind.EXTERNAL:   "external_ref",
    }

    async def resolve(
        self,
        candidate: ExecutionCandidateData,
        context: Any,
    ) -> List[ExecutionDependencySpec]:
        started = time.monotonic()
        snapshot: Dict[str, Any] = (
            getattr(context, "context_snapshot", None)
            or (isinstance(context, dict) and context.get("context_snapshot"))
            or {}
        )
        if not isinstance(snapshot, dict):
            snapshot = {}

        specs: List[ExecutionDependencySpec] = []
        for kind, field_name in self._REFERENCE_FIELD_MAP.items():
            ref = self._lookup(candidate, snapshot, field_name, kind)
            specs.append(ExecutionDependencySpec(
                kind=kind,
                reference=ref or f"unresolved:{kind.value}",
                display_name=self._display_name(kind, ref),
                is_resolved=bool(ref),
                notes=None if ref else f"No reference for {kind.value}",
                resolution_ms=0.0,
            ))

        candidate.dependencies = specs
        elapsed_ms = (time.monotonic() - started) * 1000.0
        for spec in specs:
            spec.resolution_ms = elapsed_ms / max(len(specs), 1)
        logger.debug(
            "execution dependency resolution tenant=%s decision=%s resolved=%d/%d in %.2fms",
            candidate.tenant_id, candidate.decision_id,
            sum(1 for s in specs if s.is_resolved), len(specs), elapsed_ms,
        )
        return specs

    # ── helpers ───────────────────────────────────────────────────
    @staticmethod
    def _lookup(
        candidate: ExecutionCandidateData,
        snapshot: Dict[str, Any],
        field_name: str,
        kind: ExecutionDependencyKind,
    ) -> Optional[str]:
        # Strategy/decision/approval/policy ids come from the candidate itself.
        if kind in (
            ExecutionDependencyKind.DECISION,
            ExecutionDependencyKind.STRATEGY,
            ExecutionDependencyKind.APPROVAL,
        ):
            if kind == ExecutionDependencyKind.DECISION:
                return candidate.decision_id or None
            if kind == ExecutionDependencyKind.STRATEGY:
                return candidate.strategy_id or None
            if kind == ExecutionDependencyKind.APPROVAL:
                return candidate.approval_id or None

        # Everything else lives in the snapshot.
        value = snapshot.get(field_name)
        if value is None and hasattr(snapshot, field_name):
            value = getattr(snapshot, field_name, None)
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    @staticmethod
    def _display_name(kind: ExecutionDependencyKind, ref: Optional[str]) -> Optional[str]:
        if not ref:
            return None
        return f"{kind.value}:{ref}"


__all__ = ["ExecutionDependencyResolver"]