from __future__ import annotations
from typing import Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from ..models.policy import DecisionPolicy, PolicyVersion

class PolicyVersionManager:
    """
    Manages versioning and snapshots for Enterprise Policies.
    Supports capturing full policy state and rolling back to previous versions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_snapshot(self, policy_id: str) -> PolicyVersion:
        """
        Captures the current state of a policy and stores it as a new version.
        """
        # 1. Fetch current policy
        stmt = select(DecisionPolicy).where(DecisionPolicy.id == policy_id)
        result = await self.db.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        # 2. Determine next version number
        version_stmt = select(PolicyVersion.version_number).where(PolicyVersion.policy_id == policy_id).order_by(desc(PolicyVersion.version_number))
        version_res = await self.db.execute(version_stmt)
        last_version = version_res.scalar_one_or_none()
        next_version = (last_version + 1) if last_version else 1

        # 3. Build the snapshot
        snapshot = {
            "name": policy.name,
            "description": policy.description,
            "category": policy.category,
            "priority": policy.priority,
            "status": policy.status,
            "scope": policy.scope,
            "is_builtin": policy.is_builtin,
            "is_mandatory": policy.is_mandatory
        }

        version = PolicyVersion(
            policy_id=policy_id,
            version_number=next_version,
            config_snapshot=snapshot
        )
        self.db.add(version)
        await self.db.flush()
        return version

    async def rollback_to_version(self, policy_id: str, version_number: int) -> DecisionPolicy:
        """
        Restores a policy's state from a specific version snapshot.
        """
        stmt = select(PolicyVersion).where(
            PolicyVersion.policy_id == policy_id,
            PolicyVersion.version_number == version_number
        )
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()

        if not version:
            raise ValueError(f"Version {version_number} for policy {policy_id} not found")

        snapshot = version.config_snapshot

        # Fetch the current policy
        policy_stmt = select(DecisionPolicy).where(DecisionPolicy.id == policy_id)
        policy_res = await self.db.execute(policy_stmt)
        policy = policy_res.scalar_one_or_none()

        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        # Restore attributes
        policy.name = snapshot["name"]
        policy.description = snapshot["description"]
        policy.category = snapshot["category"]
        policy.priority = snapshot["priority"]
        policy.status = snapshot["status"]
        policy.scope = snapshot["scope"]
        policy.is_builtin = snapshot["is_builtin"]
        policy.is_mandatory = snapshot["is_mandatory"]

        await self.db.flush()
        return policy
