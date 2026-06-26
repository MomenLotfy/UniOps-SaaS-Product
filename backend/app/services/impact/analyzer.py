from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.graph.repository import GraphRepository
from app.services.impact.blast_radius import BlastRadiusEngine
from app.services.impact.dependency import DependencyAnalyzer
from app.services.impact.reachability import ReachabilityEngine
from app.services.impact.resolvers.ownership_resolver import OwnershipResolver
from app.schemas.impact import ImpactSummary, BlastRadiusSchema, OwnershipSchema
from app.utils.logger import logger

class ImpactAnalysisEngine:
    """
    Synthesizes graph data into a human-readable and machine-actionable impact report.
    """
    def __init__(self, db_session: Any):
        self.repo = GraphRepository(db_session)
        self.blast_radius = BlastRadiusEngine(self.repo)
        self.dep_analyzer = DependencyAnalyzer(self.repo)
        self.reachability = ReachabilityEngine(self.repo)
        self.ownership = OwnershipResolver(db_session)

    async def analyze_impact(self, entity_id: str, tenant_id: str) -> ImpactSummary:
        """
        Performs a full impact analysis for a given entity.
        """
        logger.info(f"[ImpactAnalysisEngine] Analyzing total impact for {entity_id}")

        # 1. Calculate Blast Radius
        radius = await self.blast_radius.calculate_blast_radius(entity_id, tenant_id)

        # 2. Resolve Reachability
        is_public = await self.reachability.is_reachable_from_internet(entity_id, tenant_id)

        # 3. Map to Business Impact
        # In a real la-logic, this would count nodes by type (e.g. how many 'BusinessService' nodes)
        affected_services = [node for node in radius.immediate if "service" in node]

        # 4. Resolve Ownership
        owner = await self.ownership.resolve_ownership(entity_id, tenant_id)

        return ImpactSummary(
            finding_id=entity_id,
            affected_assets=radius.immediate + radius.extended,
            affected_services=affected_services,
            affected_teams=[owner.team] if owner else [],
            affected_repositories=[], # la-logic
            business_impact_score=100.0 if is_public else 50.0,
            critical_paths_count=len(radius.immediate)
        )
