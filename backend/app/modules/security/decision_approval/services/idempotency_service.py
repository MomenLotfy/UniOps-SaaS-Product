"""
Idempotency Service — Sprint 2 R24.

Encapsulates "exactly-once" semantics for mutating endpoints.

Flow:
  1. Client sends POST + ``Idempotency-Key`` header.
  2. We compute ``payload_hash = sha256(json.dumps(body, sort_keys=True))``.
  3. If (tenant_id, key) already exists:
       a. if payload_hash matches → return the stored response (replay).
       b. else → raise ``IdempotencyConflictError``.
  4. Otherwise we run the action, persist (tenant_id, key, payload_hash,
     response_snapshot), and return the response.

Records expire 24 hours after ``created_at`` (best-effort GC).
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IdempotencyConflictError
from ..models.idempotency import IdempotencyRecord

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = timedelta(hours=24)


def _payload_hash(payload: Dict[str, Any]) -> str:
    """Stable SHA-256 of a JSON-compatible payload."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class IdempotencyService:
    """Stateless façade: read / write / replay IdempotencyRecord rows."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def lookup(
        self,
        tenant_id: str,
        key: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Return the stored response if (tenant_id, key) was seen with the same
        payload, otherwise ``None``.  Raises if the same key was used with a
        different payload.
        """
        if not key:
            return None
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.key == key,
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None

        # Expired records are ignored (best-effort GC).
        if record.expires_at and record.expires_at < datetime.now(timezone.utc):
            await self.db.delete(record)
            await self.db.flush()
            return None

        if record.payload_hash != _payload_hash(payload):
            raise IdempotencyConflictError(key)

        logger.info(
            "idempotency replay tenant=%s key=%s request=%s",
            tenant_id, key, record.request_id,
        )
        return dict(record.response_snapshot or {})

    async def store(
        self,
        tenant_id: str,
        key: Optional[str],
        request_id: str,
        payload: Dict[str, Any],
        response_snapshot: Dict[str, Any],
    ) -> None:
        """Persist the idempotency record so future retries can replay it."""
        if not key:
            return
        now = datetime.now(timezone.utc)
        record = IdempotencyRecord(
            id=request_id,
            tenant_id=tenant_id,
            key=key,
            request_id=request_id,
            payload_hash=_payload_hash(payload),
            response_snapshot=response_snapshot,
            created_at=now,
            expires_at=now + IDEMPOTENCY_TTL,
        )
        self.db.add(record)
        await self.db.flush()


__all__ = ["IdempotencyService"]