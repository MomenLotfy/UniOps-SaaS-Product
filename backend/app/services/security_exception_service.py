from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_exception import SecurityException
from app.schemas.security_exception import (
    SecurityExceptionCreate, SecurityExceptionUpdate,
    SecurityExceptionReview, SecurityExceptionResponse,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.services.base import BaseService
from app.utils.logger import logger


class SecurityExceptionService(BaseService):

    async def list_exceptions(
        self, tenant_id: str, page: int = 1, page_size: int = 20,
        status: Optional[str] = None,
        exception_type: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        policy_id: Optional[str] = None,
        requested_by: Optional[str] = None,
        approved_by: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        query = select(SecurityException).where(SecurityException.tenant_id == tenant_id)

        if status:
            query = query.where(SecurityException.status == status)
        if exception_type:
            query = query.where(SecurityException.exception_type == exception_type)
        # Category maps to finding_type in the model
        if category:
            query = query.where(SecurityException.finding_type == category)
        if policy_id:
            query = query.where(SecurityException.policy_id == policy_id)
        if requested_by:
            query = query.where(SecurityException.requested_by == requested_by)
        if approved_by:
            query = query.where(SecurityException.approved_by == approved_by)
        # Server-side full-text search across key text fields
        if search:
            q = f"%{search.lower()}%"
            query = query.where(
                or_(
                    SecurityException.title.ilike(q),
                    SecurityException.id.ilike(q),
                    SecurityException.justification.ilike(q),
                    SecurityException.requested_by.ilike(q),
                    SecurityException.approved_by.ilike(q),
                    SecurityException.finding_id.ilike(q),
                    SecurityException.policy_id.ilike(q),
                )
            )
        # severity is stored in tags.severity — use SQLAlchemy's JSON key accessor
        # for deterministic extraction regardless of whitespace/key ordering.
        if severity:
            from sqlalchemy import cast, Text
            query = query.where(
                cast(SecurityException.tags["severity"], Text) == f'"{severity}"'
            )

        total = await self._count(query)
        items = await self._paginate(
            query.order_by(SecurityException.created_at.desc()), page, page_size
        )
        return {
            "data": [SecurityExceptionResponse.model_validate(e) for e in items],
            "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def create_exception(
        self, tenant_id: str, data: SecurityExceptionCreate, requested_by: str,
    ) -> SecurityExceptionResponse:
        exc = SecurityException(
            tenant_id=tenant_id,
            requested_by=requested_by,
            status="pending",
            **data.model_dump(),
        )
        self.db.add(exc)
        await self.db.flush()
        logger.info(f"[exception:create] id={exc.id[:8]} tenant={tenant_id[:8]} by={requested_by[:8]}")
        return SecurityExceptionResponse.model_validate(exc)

    async def get_exception(self, exception_id: str) -> SecurityExceptionResponse:
        exc = await self._get_by_id(SecurityException, exception_id)
        return SecurityExceptionResponse.model_validate(exc)

    async def update_exception(
        self, exception_id: str, data: SecurityExceptionUpdate,
    ) -> SecurityExceptionResponse:
        exc = await self._get_by_id(SecurityException, exception_id)
        if exc.status not in ("pending",):
            raise ValidationError("Only pending exceptions can be updated")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(exc, field, value)
        await self.db.flush()
        return SecurityExceptionResponse.model_validate(exc)

    async def review_exception(
        self, exception_id: str, data: SecurityExceptionReview, reviewer_id: str,
    ) -> SecurityExceptionResponse:
        exc = await self._get_by_id(SecurityException, exception_id)
        if exc.status != "pending":
            raise ValidationError(f"Exception is already {exc.status}")
        if data.action not in ("approve", "reject"):
            raise ValidationError("Action must be 'approve' or 'reject'")
        now = datetime.now(timezone.utc)
        if data.action == "approve":
            exc.status = "approved"
            exc.approved_by = reviewer_id
        else:
            exc.status = "rejected"
            exc.rejected_by = reviewer_id
        exc.reviewer_note = data.reviewer_note
        exc.reviewed_at = now
        await self.db.flush()
        logger.info(
            f"[exception:review] id={exception_id[:8]} action={data.action} "
            f"by={reviewer_id[:8]}"
        )
        return SecurityExceptionResponse.model_validate(exc)

    async def revoke_exception(
        self, exception_id: str, tenant_id: str, revoker_id: str,
    ) -> SecurityExceptionResponse:
        exc = await self._get_by_id(SecurityException, exception_id)
        # Enforce tenant ownership — prevent cross-tenant IDOR
        if exc.tenant_id != tenant_id:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"Exception {exception_id} not found")
        if exc.status not in ("approved", "pending"):
            raise ValidationError(f"Cannot revoke exception with status '{exc.status}'")
        exc.status = "revoked"
        exc.reviewed_at = datetime.now(timezone.utc)
        exc.reviewer_note = f"Revoked by {revoker_id}"
        await self.db.flush()
        logger.info(f"[exception:revoke] id={exception_id[:8]} tenant={tenant_id[:8]} by={revoker_id[:8]}")
        return SecurityExceptionResponse.model_validate(exc)

    async def get_stats(self, tenant_id: str) -> dict:
        status_result = await self.db.execute(
            select(SecurityException.status, func.count(SecurityException.id))
            .where(SecurityException.tenant_id == tenant_id)
            .group_by(SecurityException.status)
        )
        by_status = {r[0]: r[1] for r in status_result.all()}

        type_result = await self.db.execute(
            select(SecurityException.exception_type, func.count(SecurityException.id))
            .where(SecurityException.tenant_id == tenant_id)
            .group_by(SecurityException.exception_type)
        )
        by_type = {r[0]: r[1] for r in type_result.all()}

        category_result = await self.db.execute(
            select(SecurityException.finding_type, func.count(SecurityException.id))
            .where(SecurityException.tenant_id == tenant_id)
            .group_by(SecurityException.finding_type)
        )
        by_category = {(r[0] or "custom"): r[1] for r in category_result.all()}

        total = sum(by_status.values())
        return {
            "total": total,
            "pending": by_status.get("pending", 0),
            "approved": by_status.get("approved", 0),
            "rejected": by_status.get("rejected", 0),
            "expired": by_status.get("expired", 0),
            "revoked": by_status.get("revoked", 0),
            "by_status": by_status,
            "by_type": by_type,
            "by_category": by_category,
        }
