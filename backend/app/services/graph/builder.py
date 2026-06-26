from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.graph.repository import GraphRepository
from app.services.graph.resolver import EntityResolver
from app.schemas.graph import EntitySchema, RelationshipSchema
from app.utils.logger import logger
import uuid

class GraphBuilder:
    """
    Implements the incremental construction of the security graph.
    """
    def __init__(self, repository: GraphRepository, resolver: EntityResolver):
        self.repo = repository
        self.resolver = resolver

    async def add_entity(self, tenant_id: str, entity_type: str, identifiers: Dict[str, Any], metadata: Dict[str, Any] = {}) -> str:
        """
        Resolves and inserts a graph entity.
        """
        canonical_id = self.resolver.resolve_id(entity_type, identifiers)

        entity_data = {
            "id": canonical_id,
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "canonical_id": canonical_id,
            "metadata": metadata,
            "provenance": {"resolved_via": "EntityResolver"}
        }

        entity = await self.repo.upsert_entity(entity_data)
        return entity.id

    async def add_relationship(self, tenant_id: str, source_id: str, target_id: str, rel_type: str, evidence: Optional[str] = None) -> str:
        """
        Inserts a relationship between two entities.
        """
        rel_id = f"rel_{uuid.uuid4().hex[:16]}"
        rel_data = {
            "id": rel_id,
            "tenant_id": tenant_id,
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": rel_type,
            "evidence": evidence,
            "provenance": {"resolved_via": "GraphBuilder"}
        }

        await self.repo.upsert_relationship(rel_data)
        return rel_id
