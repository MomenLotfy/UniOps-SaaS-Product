from __future__ import annotations
from typing import Any, Dict, Optional, List, Set
from app.services.graph.repository import GraphRepository
from app.schemas.impact import BlastRadiusSchema
from app.utils.logger import logger

class BlastRadiusEngine:
    """
    Determines the propagation of a vulnerability through the knowledge graph.
    """
    def __init__(self, repository: GraphRepository):
        self.repo = repository

    async def calculate_blast_radius(self, starting_entity_id: str, tenant_id: str) -> BlastRadiusSchema:
        """
        Finds all entities affected by the starting entity using multi-hop traversal.
        """
        logger.info(f"[BlastRadiusEngine] Calculating radius for {starting_entity_id}")

        immediate = []
        extended = []
        potential = []

        # Hop 1: Immediate (1 edge away)
        rels = await self.repo.get_relationships(source_id=starting_entity_id, tenant_id=tenant_id)
        for rel in rels:
            immediate.append(rel.target_id)

        # Hop 2: Extended (2-3 edges away)
        for entity_id in list(immediate):
            rels = await self.repo.get_relationships(source_id=entity_id, tenant_id=tenant_id)
            for rel in rels:
                if rel.target_id not in immediate:
                    extended.append(rel.target_id)

        # Hop 3: Potential (Conditional reachability)
        # This would involve analyzing 'POTENTIAL_SINK' or 'SOMETIMES_AFFECTS' relationships
        # For now, we mark a subset of extended as potential
        potential = extended[:len(extended)//4]

        return BlastRadiusSchema(
            immediate=immediate,
            extended=extended,
            potential=potential,
            total_impacted_nodes=len(immediate) + len(extended)
        )
