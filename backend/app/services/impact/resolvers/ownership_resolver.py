from __future__ import annotations
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.impact import OwnershipMapping
from app.models.graph import GraphEntity, GraphRelationship
from app.schemas.impact import OwnershipSchema
from app.utils.logger import logger

class OwnershipResolver:
    """
    Resolves the technical and business ownership of an entity by traversing the graph.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_ownership(self, entity_id: str, tenant_id: str) -> Optional[OwnershipSchema]:
        """
        Determines who owns an entity. If not explicitly mapped, it traverses the
        graph upwards (e.g., Pod -> Namespace -> Cluster -> Account).
        """
        # 1. Check for explicit mapping first
        result = await self.db.execute(
            select(OwnershipMapping).where(
                OwnershipMapping.entity_id == entity_id,
                OwnershipMapping.tenant_id == tenant_id
            )
        )
        mapping = result.scalar_one_or_none()
        if mapping:
            return OwnershipSchema(
                entity_id=entity_id,
                technical_owner=mapping.technical_owner,
                business_owner=mapping.business_owner,
                team=mapping.technical_owner, # Simplified
                escalation_path=mapping.escalation_path
            )

        # 2. Recursive Graph Traversal for ownership
        # Search for "OWNS" or "BELONGS_TO" relationships
        owner_id = await self._traverse_for_owner(entity_id, tenant_id)
        if not owner_id:
            return None

        # In a real system, we'd fetch the owner's metadata from a User/Team service
        return OwnershipSchema(
            entity_id=entity_id,
            technical_owner=owner_id,
            business_owner="Organization Root",
            team="Platform Team",
            escalation_path=[owner_id, "SRE-Lead", "CISO"]
        )

    async def _traverse_for_owner(self, entity_id: str, tenant_id: str) -> Optional[str]:
        """
        Finds the nearest 'owner' entity by traversing relationships.
        """
        # This would use the GraphRepository to find edges like 'BELONGS_TO'
        # For now, we simulate the traversal
        return f"team_{entity_id[-4:]}" # Mock resolution
