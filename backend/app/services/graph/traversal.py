from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.graph.repository import GraphRepository
from app.schemas.graph import EntitySchema, RelationshipSchema, GraphQueryResponse
from app.utils.logger import logger
import time

class GraphTraversalEngine:
    """
    Implements graph traversal queries to uncover hidden dependencies and impact.
    """
    def __init__(self, repository: GraphRepository):
        self.repo = repository

    async def find_affected_assets(self, cve_id: str, tenant_id: str) -> GraphQueryResponse:
        """
        Query: Show everything affected by a CVE.
        Traversal: CVE -> AFFECTS -> Package -> RUNS_ON -> Pod -> BELONGS_TO -> Namespace
        """
        start_time = time.time()
        visited_nodes = []
        relationships = []

        # 1. Start at the CVE entity
        cve_node = await self.repo.get_entity(f"canonical:cve:{cve_id.lower()}", tenant_id)
        if not cve_node:
            return GraphQueryResponse(query_type="affected_assets", results=[], relationships=[], metadata={})

        # 2. Simple BFS Traversal
        queue = [cve_node]
        visited_ids = set()

        while queue:
            current = queue.pop(0)
            if current.id in visited_ids: continue
            visited_ids.add(current.id)
            visited_nodes.append(EntitySchema.from_orm(current))

            # Find all outgoing relationships
            rels = await self.repo.get_relationships(source_id=current.id, tenant_id=tenant_id)
            for rel in rels:
                relationships.append(RelationshipSchema.from_orm(rel))
                target = await self.repo.get_entity(rel.target_id, tenant_id)
                if target:
                    queue.append(target)

        return GraphQueryResponse(
            query_type="affected_assets",
            results=visited_nodes,
            relationships=relationships,
            metadata={
                "traversal_time_ms": (time.time() - start_time) * 1000,
                "nodes_visited": len(visited_nodes),
                "edges_traversed": len(relationships)
            }
        )
