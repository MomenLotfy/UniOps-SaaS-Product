from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.graph.repository import GraphRepository
from app.schemas.investigation import CorrelationLink, CorrelationResponse
from app.utils.logger import logger

class CorrelationEngine:
    """
    The CorrelationEngine identifies deterministic linkages between disparate security entities.
    It leverages the Knowledge Graph to find paths and shared dependencies.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.repo = GraphRepository(db_session)

    async def correlate(self, source_id: str, source_type: str, target_id: Optional[str] = None, target_type: Optional[str] = None, depth: int = 3) -> CorrelationResponse:
        """
        Finds deterministic correlations between entities.
        If target_id is provided, it finds the path between them.
        If not, it finds all highly correlated entities within the specified depth.
        """
        logger.info(f"[CorrelationEngine] Correlating {source_type}:{source_id} "
                    f"{'with ' + target_type + ':' + target_id if target_id else 'globally'}")

        correlations: List[CorrelationLink] = []

        if target_id:
            # Path-finding mode: Deterministic search for a path from source to target
            path = await self._find_path(source_id, target_id, depth)
            if path:
                correlations.append(CorrelationLink(
                    target_id=target_id,
                    target_type=target_type or "Unknown",
                    relationship="CONNECTED_PATH",
                    depth=len(path) - 1,
                    evidence=[f"{p.id} ({p.type})" for p in path]
                ))
        else:
            # Discovery mode: Find all entities within N hops
            correlations = await self._discover_correlations(source_id, depth)

        return CorrelationResponse(
            source_id=source_id,
            correlations=correlations,
            summary={
                "total_correlations": len(correlations),
                "max_depth": depth
            }
        )

    async def _find_path(self, start_id: str, end_id: str, max_depth: int) -> Optional[List[Any]]:
        """
        BFS implementation to find the shortest deterministic path between two entities.
        """
        queue = [[start_id]]
        visited = {start_id}

        while queue:
            path = queue.pop(0)
            node = path[-1]

            if node == end_id:
                # In a real implementation, we'd return the actual entity objects
                return path

            if len(path) > max_depth:
                continue

            rels = await self.repo.get_relationships(source_id=node)
            for rel in rels:
                if rel.target_id not in visited:
                    visited.add(rel.target_id)
                    queue.append(path + [rel.target_id])

        return None

    async def _discover_correlations(self, source_id: str, max_depth: int) -> List[CorrelationLink]:
        """
        Explores the graph to find all entities within the specified depth.
        """
        results = []
        visited = {source_id}
        queue = [(source_id, 0, [])] # (id, current_depth, path)

        while queue:
            curr_id, depth, path = queue.pop(0)

            if depth >= max_depth:
                continue

            rels = await self.repo.get_relationships(source_id=curr_id)
            for rel in rels:
                if rel.target_id not in visited:
                    visited.add(rel.target_id)

                    # Add as a correlation
                    results.append(CorrelationLink(
                        target_id=rel.target_id,
                        target_type=rel.target_type if hasattr(rel, 'target_type') else "Unknown",
                        relationship=rel.relationship_type,
                        depth=depth + 1,
                        evidence=[f"Hop {depth+1}: {rel.relationship_type}"]
                    ))

                    queue.append((rel.target_id, depth + 1, path + [rel.target_id]))

        return results
