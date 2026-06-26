from __future__ import annotations
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.graph import GraphEntity, GraphRelationship, EntityResolutionLog
from app.schemas.graph import EntitySchema, RelationshipSchema
from app.utils.logger import logger

class GraphRepository:
    """
    Data access layer for the Security Knowledge Graph.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_entity(self, entity_data: Dict[str, Any]) -> GraphEntity:
        """
        Inserts or updates a graph entity.
        """
        # Simplified upsert logic
        entity_id = entity_data["id"]
        result = await self.db.execute(select(GraphEntity).where(GraphEntity.id == entity_id))
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            for key, value in entity_data.items():
                setattr(existing, key, value)
            self.db.add(existing)
        else:
            # Create new
            new_entity = GraphEntity(**entity_data)
            self.db.add(new_entity)

        await self.db.flush()
        return existing or new_entity

    async def upsert_relationship(self, rel_data: Dict[str, Any]) -> GraphRelationship:
        """
        Inserts or updates a relationship edge.
        """
        rel_id = rel_data["id"]
        result = await self.db.execute(select(GraphRelationship).where(GraphRelationship.id == rel_id))
        existing = result.scalar_one_or_none()

        if existing:
            for key, value in rel_data.items():
                setattr(existing, key, value)
            self.db.add(existing)
        else:
            new_rel = GraphRelationship(**rel_data)
            self.db.add(new_rel)

        await self.db.flush()
        return existing or new_rel

    async def get_entity(self, entity_id: str, tenant_id: str) -> Optional[GraphEntity]:
        result = await self.db.execute(
            select(GraphEntity).where(GraphEntity.id == entity_id, GraphEntity.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def find_entities_by_type(self, entity_type: str, tenant_id: str) -> List[GraphEntity]:
        result = await self.db.execute(
            select(GraphEntity).where(GraphEntity.entity_type == entity_type, GraphEntity.tenant_id == tenant_id)
        )
        return result.scalars().all()

    async def get_relationships(self, source_id: Optional[str] = None, target_id: Optional[str] = None, tenant_id: str = None) -> List[GraphRelationship]:
        query = select(GraphRelationship).where(GraphRelationship.tenant_id == tenant_id)
        if source_id:
            query = query.where(GraphRelationship.source_id == source_id)
        if target_id:
            query = query.where(GraphRelationship.target_id == target_id)

        result = await self.db.execute(query)
        return result.scalars().all()
