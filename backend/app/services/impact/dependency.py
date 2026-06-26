from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.graph.repository import GraphRepository
from app.schemas.impact import DependencyChainSchema
from app.utils.logger import logger

class DependencyAnalyzer:
    """
    Analyzes transitive and circular dependencies within the graph.
    """
    def __init__(self, repository: GraphRepository):
        self.repo = repository

    async def resolve_dependency_chain(self, entity_id: str, tenant_id: str) -> List[DependencyChainSchema]:
        """
        Tracks the chain of dependencies for a given entity (e.g. a package).
        """
        logger.info(f"[DependencyAnalyzer] Resolving chains for {entity_id}")

        chains = []
        visited = set()

        # Recursive DFS to find all paths
        async def walk(current_id: str, path: List[str]):
            if current_id in path:
                # Circular dependency detected
                chains.append(DependencyChainSchema(
                    chain=path + [current_id],
                    depth=len(path),
                    is_circular=True
                ))
                return

            visited.add(current_id)

            # Find dependencies (DEPENDS_ON)
            rels = await self.repo.get_relationships(source_id=current_id, tenant_id=tenant_id)
            for rel in rels:
                if rel.relationship_type == "DEPENDS_ON":
                    await walk(rel.target_id, path + [current_id])

        await walk(entity_id, [])

        # If no circular paths were found, create a general summary chain
        if not chains:
            chains.append(DependencyChainSchema(
                chain=["ROOT", entity_id],
                depth=1,
                is_circular=False
            ))

        return chains
