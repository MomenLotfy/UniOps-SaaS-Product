from __future__ import annotations
"""Company/Tenant service — manages tenant settings, stats, and domain verification."""
import secrets
import hashlib
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.user import User
from app.models.integration import Integration
from app.models.pipeline import Pipeline
from app.models.threat import Threat
from app.models.cost_metric import CostMetric
from app.schemas.company import TenantCreate, TenantUpdate, TenantResponse, TenantStats
from app.core.exceptions import NotFoundError, ConflictError
from app.services.base import BaseService


class CompanyService(BaseService):
    async def get_by_id(self, tenant_id: str) -> TenantResponse:
        tenant = await self._get_by_id(Tenant, tenant_id)
        return TenantResponse.model_validate(tenant)

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def update(self, tenant_id: str, data: TenantUpdate) -> TenantResponse:
        tenant = await self._get_by_id(Tenant, tenant_id)
        update_data = data.model_dump(exclude_none=True)

        if "domain" in update_data and update_data["domain"] != tenant.domain:
            existing = await self.db.execute(
                select(Tenant).where(Tenant.domain == update_data["domain"], Tenant.id != tenant_id)
            )
            if existing.scalar_one_or_none():
                raise ConflictError(f"Domain {update_data['domain']} is already in use")

        await self._update_fields(tenant, update_data)
        return TenantResponse.model_validate(tenant)

    async def get_stats(self, tenant_id: str) -> TenantStats:
        users_r = await self.db.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant_id, User.is_active == True)
        )
        integrations_r = await self.db.execute(
            select(func.count(Integration.id)).where(
                Integration.tenant_id == tenant_id, Integration.is_active == True
            )
        )
        pipelines_r = await self.db.execute(
            select(func.count(Pipeline.id)).where(
                Pipeline.tenant_id == tenant_id, Pipeline.status == "running"
            )
        )
        threats_r = await self.db.execute(
            select(func.count(Threat.id)).where(
                Threat.tenant_id == tenant_id, Threat.status == "open"
            )
        )
        cost_r = await self.db.execute(
            select(func.sum(CostMetric.amount)).where(CostMetric.tenant_id == tenant_id)
        )

        return TenantStats(
            total_users=users_r.scalar() or 0,
            total_integrations=integrations_r.scalar() or 0,
            active_pipelines=pipelines_r.scalar() or 0,
            open_threats=threats_r.scalar() or 0,
            monthly_cost=float(cost_r.scalar() or 0.0),
        )

    async def initiate_domain_verification(self, tenant_id: str, domain: str) -> dict:
        tenant = await self._get_by_id(Tenant, tenant_id)
        token = hashlib.sha256(f"{tenant_id}:{domain}:{secrets.token_hex(16)}".encode()).hexdigest()[:32]
        txt_record = f"uniops-verify={token}"

        settings_update = dict(tenant.settings or {})
        settings_update["domain_verification_token"] = token
        settings_update["pending_domain"] = domain
        tenant.settings = settings_update
        await self.db.flush()

        return {
            "domain": domain,
            "txt_record": txt_record,
            "verified": False,
            "instructions": f"Add a TXT record '{txt_record}' to your DNS for {domain}",
        }

    async def verify_domain(self, tenant_id: str) -> dict:
        tenant = await self._get_by_id(Tenant, tenant_id)
        pending_domain = (tenant.settings or {}).get("pending_domain")
        if not pending_domain:
            raise NotFoundError("Pending domain verification", tenant_id)

        tenant.domain = pending_domain
        settings_update = dict(tenant.settings or {})
        settings_update.pop("domain_verification_token", None)
        settings_update.pop("pending_domain", None)
        tenant.settings = settings_update
        await self.db.flush()

        return {"domain": pending_domain, "verified": True}

    async def update_plan(self, tenant_id: str, plan: str) -> TenantResponse:
        tenant = await self._get_by_id(Tenant, tenant_id)
        tenant.plan = plan
        await self.db.flush()
        return TenantResponse.model_validate(tenant)
