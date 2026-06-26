from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.impact.analyzer import ImpactAnalysisEngine
from app.services.impact.dependency import DependencyAnalyzer
from app.services.impact.reachability import ReachabilityEngine
from app.services.impact.resolvers.ownership_resolver import OwnershipResolver
from app.services.graph.repository import GraphRepository
from app.schemas.impact import ImpactSummary, BlastRadiusSchema, OwnershipSchema, DependencyChainSchema
from app.utils.logger import logger

class RelationshipIntelligenceEngine:
    """
    The main facade for Relationship Intelligence and Impact Analysis.
    Provides high-level reasoning capabilities over the Security Knowledge Graph.
    """
    def __init__(self, db_session: Any):
        self.db = db_session
        self.repo = GraphRepository(db_session)
        self.impact_analyzer = ImpactAnalysisEngine(db_session)
        self.dep_analyzer = DependencyAnalyzer(self.repo)
        self.reachability = ReachabilityEngine(self.repo)
        self.ownership = OwnershipResolver(db_session)

    async def get_full_impact_report(self, entity_id: str, tenant_id: str) -> ImpactSummary:
        """
        Returns a comprehensive impact summary for a given security entity.
        """
        return await self.impact_analyzer.analyze_impact(entity_id, tenant_id)

    async def get_blast_radius(self, entity_id: str, tenant_id: str) -> BlastRadiusSchema:
        """
        Determines the total reach of a vulnerability.
        """
        # Directly leverage the analyzer's internal engine
        return await self.impact_analyzer.blast_radius.calculate_blast_radius(entity_id, tenant_id)

    async def get_dependency_chains(self, entity_id: str, tenant_id: str) -> List[DependencyChainSchema]:
        """
        Uncovers all transitive dependency paths.
        """
        return await self.dep_analyzer.resolve_dependency_chain(entity_id, tenant_id)

    async def resolve_ownership(self, entity_id: str, tenant_id: str) -> Optional[OwnershipSchema]:
        """
        Resolves the owners for an entity.
        """
        return await self.ownership.resolve_ownership(entity_id, tenant_id)

    async def check_reachability(self, entity_id: str, tenant_id: str) -> bool:
        """
        Checks if an entity is reachable from the public internet.
        """
        return await self.reachability.is_reachable_from_internet(entity_id, tenant_id)
