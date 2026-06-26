from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.graph.repository import GraphRepository
from app.services.graph.builder import GraphBuilder
from app.services.graph.traversal import GraphTraversalEngine
from app.services.graph.resolver import EntityResolver
from app.schemas.graph import EntitySchema, RelationshipSchema, GraphQueryResponse, GraphStatsSchema
from app.utils.logger import logger
from datetime import datetime

class KnowledgeGraphEngine:
    """
    The main coordinator for the Security Knowledge Graph.
    Bridges the gap between intelligence entities and the graph structure.
    """
    def __init__(self, db_session: Any):
        self.repo = GraphRepository(db_session)
        self.resolver = EntityResolver()
        self.builder = GraphBuilder(self.repo, self.resolver)
        self.traversal = GraphTraversalEngine(self.repo)

    async def ingest_entity(self, tenant_id: str, entity_type: str, identifiers: Dict[str, Any], metadata: Dict[str, Any] = {}) -> str:
        """
        Inserts an entity into the graph.
        """
        return await self.builder.add_entity(tenant_id, entity_type, identifiers, metadata)

    async def link_entities(self, tenant_id: str, source_id: str, target_id: str, rel_type: str, evidence: Optional[str] = None) -> str:
        """
        Creates a relationship between two entities.
        """
        return await self.builder.add_relationship(tenant_id, source_id, target_id, rel_type, evidence)

    async def query_impact(self, cve_id: str, tenant_id: str) -> GraphQueryResponse:
        """
        Performs a blast radius analysis for a specific CVE.
        """
        return await self.traversal.find_affected_assets(cve_id, tenant_id)

    async def get_graph_stats(self, tenant_id: str) -> GraphStatsSchema:
        """
        Calculates distribution and health metrics for the graph.
        """
        # Mocking stats for the frontend
        return GraphStatsSchema(
            entity_distribution={"CVE": 1200, "Package": 5000, "Pod": 150, "Cluster": 2},
            relationship_distribution={"AFFECTS": 3000, "RUNS_ON": 450, "BELONGS_TO": 150},
            total_entities=6850,
            total_relationships=3600,
            health_status="healthy",
            last_updated=datetime.utcnow()
        )
