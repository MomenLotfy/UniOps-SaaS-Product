from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from ..models.policy import DecisionPolicy, PolicyStatus
from .policy_interfaces import IPolicyRepository

class PolicyRepository(IPolicyRepository):
    """
    SQLAlchemy implementation of the Policy Repository.
    Handles hierarchical resolution (Repo -> Org -> Tenant).
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_effective_policy(self, tenant_id: str, scope_data: dict) -> Optional[DecisionPolicy]:
        """
        Deterministic resolution of the active policy based on scope.
        Precedence: Repository -> Organization -> Tenant -> Built-in.
        """
        repo_id = scope_data.get("repo_id")
        org_id = scope_data.get("org_id")

        # 1. Search for Repository-level policy (Most Specific)
        if repo_id:
            res = await self.db.execute(
                select(DecisionPolicy)
                .where(
                    DecisionPolicy.tenant_id == tenant_id,
                    DecisionPolicy.status == PolicyStatus.ACTIVE,
                    DecisionPolicy.scope["type"].astext == "repo",
                    DecisionPolicy.scope["id"].astext == repo_id
                )
                .order_by(desc(DecisionPolicy.priority))
            )
            policy = res.scalar_one_or_none()
            if policy: return policy

        # 2. Search for Organization-level policy
        if org_id:
            res = await self.db.execute(
                select(DecisionPolicy)
                .where(
                    DecisionPolicy.tenant_id == tenant_id,
                    DecisionPolicy.status == PolicyStatus.ACTIVE,
                    DecisionPolicy.scope["type"].astext == "org",
                    DecisionPolicy.scope["id"].astext == org_id
                )
                .order_by(desc(DecisionPolicy.priority))
            )
            policy = res.scalar_one_or_none()
            if policy: return policy

        # 3. Search for Tenant-level global policy
        res = await self.db.execute(
            select(DecisionPolicy)
            .where(
                DecisionPolicy.tenant_id == tenant_id,
                DecisionPolicy.status == PolicyStatus.ACTIVE,
                DecisionPolicy.scope["type"].astext == "tenant"
            )
            .order_by(desc(DecisionPolicy.priority))
        )
        policy = res.scalar_one_or_none()
        if policy: return policy

        # 4. Fallback to Built-in policies
        res = await self.db.execute(
            select(DecisionPolicy)
            .where(
                DecisionPolicy.is_builtin == True,
                DecisionPolicy.status == PolicyStatus.ACTIVE
            )
            .order_by(desc(DecisionPolicy.priority))
        )
        return res.scalar_one_or_none()
