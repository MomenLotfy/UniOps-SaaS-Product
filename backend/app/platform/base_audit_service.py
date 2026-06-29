"""
Sprint 3 R35 — BaseAuditService.

Common audit-row contract.  Concrete audit services
(``ApprovalAuditService`` / ``ExecutionAuditService``) share the same
record shape and tenant scoping rules.  The base centralises:

  - ``correlation_id`` fallback (NOT NULL on every DecisionBase).
  - ``actor_role`` defaulting to ``"SYSTEM"``.
  - ``details`` dict-to-JSON coercion.

It does NOT import the concrete ``ApprovalAudit`` / ``ExecutionAudit``
ORM classes — each concrete service still owns its row schema.
"""

from __future__ import annotations

import json
from typing import Any


class BaseAuditService:
    """
    Reusable audit-row payload assembly.

    Concrete subclasses use ``build_event(...)`` to materialize a dict
    that matches their ORM model fields.  This keeps the row schema
    DRY without forcing a shared base class on the SQLAlchemy models.
    """

    DEFAULT_ACTOR_ROLE = "SYSTEM"

    @staticmethod
    def resolve_correlation_id(
        explicit: str | None,
        *,
        fallback: str,
    ) -> str:
        """
        Never let a NOT NULL correlation_id column receive ``None``.

        The fallback is computed by the caller (typically
        ``f"audit:{tenant_id}:{entity_id}"``); this helper just enforces
        the substitution at the boundary.
        """
        if explicit:
            return explicit
        return fallback

    @staticmethod
    def coerce_details(details: dict[str, Any] | None) -> dict[str, Any]:
        """
        Coerce a details dict into a JSON-safe primitive map.

        Non-JSON-serializable values are stringified; circular
        references fall back to ``{"_unserializable": True}``.
        """
        if not details:
            return {}
        try:
            json.dumps(details)
            return details
        except (TypeError, ValueError):
            try:
                return {str(k): str(v) for k, v in details.items()}
            except Exception:  # pragma: no cover - defensive
                return {"_unserializable": True}

    def build_event(
        self,
        *,
        event_type: str,
        actor_id: str | None = None,
        actor_role: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a dict ready to splat into an audit ORM row."""
        return {
            "event_type": str(event_type),
            "actor_id": actor_id,
            "actor_role": actor_role or self.DEFAULT_ACTOR_ROLE,
            "correlation_id": correlation_id,
            "details": self.coerce_details(details),
        }


__all__ = ["BaseAuditService"]
