from __future__ import annotations
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_policy import SecurityPolicy
from app.schemas.security_policy import (
    SecurityPolicyCreate, SecurityPolicyUpdate, SecurityPolicyResponse,
)
from app.core.exceptions import NotFoundError
from app.services.base import BaseService
from app.utils.logger import logger


class SecurityPolicyService(BaseService):

    async def list_policies(
        self, tenant_id: str, page: int = 1, page_size: int = 20,
        category: Optional[str] = None, status: Optional[str] = None,
        severity: Optional[str] = None, enforcement: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> dict:
        query = select(SecurityPolicy).where(SecurityPolicy.tenant_id == tenant_id)
        if category:    query = query.where(SecurityPolicy.category == category)
        if status:      query = query.where(SecurityPolicy.status == status)
        if severity:    query = query.where(SecurityPolicy.severity == severity)
        if enforcement: query = query.where(SecurityPolicy.enforcement == enforcement)

        total = await self._count(query)
        items = await self._paginate(query.order_by(SecurityPolicy.created_at.desc()), page, page_size)
        return {
            "data": [SecurityPolicyResponse.model_validate(p) for p in items],
            "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def create_policy(
        self, tenant_id: str, data: SecurityPolicyCreate, created_by: str,
    ) -> SecurityPolicyResponse:
        policy = SecurityPolicy(
            tenant_id=tenant_id,
            created_by=created_by,
            updated_by=created_by,
            **data.model_dump(),
        )
        self.db.add(policy)
        await self.db.flush()
        logger.info(f"[policy:create] id={policy.id[:8]} tenant={tenant_id[:8]}")
        return SecurityPolicyResponse.model_validate(policy)

    async def get_policy(self, policy_id: str) -> SecurityPolicyResponse:
        policy = await self._get_by_id(SecurityPolicy, policy_id)
        return SecurityPolicyResponse.model_validate(policy)

    async def update_policy(
        self, policy_id: str, data: SecurityPolicyUpdate, updated_by: str,
    ) -> SecurityPolicyResponse:
        policy = await self._get_by_id(SecurityPolicy, policy_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(policy, field, value)
        policy.updated_by = updated_by
        await self.db.flush()
        return SecurityPolicyResponse.model_validate(policy)

    async def delete_policy(self, policy_id: str) -> None:
        policy = await self._get_by_id(SecurityPolicy, policy_id)
        await self.db.delete(policy)

    async def get_stats(self, tenant_id: str) -> dict:
        result = await self.db.execute(
            select(
                func.count(SecurityPolicy.id).label("total"),
                func.sum(
                    func.cast(SecurityPolicy.status == "active", type_=func.count(SecurityPolicy.id).type)
                ).label("active"),
            ).where(SecurityPolicy.tenant_id == tenant_id)
        )
        row = result.first()
        # Count by category
        cat_result = await self.db.execute(
            select(SecurityPolicy.category, func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id)
            .group_by(SecurityPolicy.category)
        )
        by_category = {r[0]: r[1] for r in cat_result.all()}

        # Count by status
        status_result = await self.db.execute(
            select(SecurityPolicy.status, func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id)
            .group_by(SecurityPolicy.status)
        )
        by_status = {r[0]: r[1] for r in status_result.all()}

        # Count by enforcement
        enf_result = await self.db.execute(
            select(SecurityPolicy.enforcement, func.count(SecurityPolicy.id))
            .where(SecurityPolicy.tenant_id == tenant_id)
            .group_by(SecurityPolicy.enforcement)
        )
        by_enforcement = {r[0]: r[1] for r in enf_result.all()}

        total = row[0] if row else 0
        return {
            "total": total,
            "active": by_status.get("active", 0),
            "inactive": by_status.get("inactive", 0),
            "draft": by_status.get("draft", 0),
            "by_category": by_category,
            "by_status": by_status,
            "by_enforcement": by_enforcement,
        }
