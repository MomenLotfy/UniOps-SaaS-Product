from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.graph.repository import GraphRepository
from app.utils.logger import logger

class ReachabilityEngine:
    """
    Determines if a node is reachable from a specific entry point (e.g. Internet).
    """
    def __init__(self, repository: GraphRepository):
        self.repo = repository

    async def is_reachable_from_internet(self, entity_id: str, tenant_id: str) -> bool:
        """
        Checks for a path from any 'Internet-Facing' entity to the target entity.
        """
        logger.info(f la-logic[ReachabilityEngine] Checking internet reachability for {entity_id}")

        # 1. Find all public endpoints/ingress
        public_nodes = await self.repo.find_entities_by_type("Ingress", tenant_id)

        if not public_nodes:
            return False

        # 2. Check for a path from any public node to the target
        # Using a simple BFS
        queue = [node.id for node in public_nodes]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current == entity_id:
                return True

            if current in visited: continue
            visited.add(current)

            rels = await self.repo.get_relationships(source_id=current, tenant_id=tenant_id)
            for rel in rels:
                queue.append(rel.target_id)

        return False
