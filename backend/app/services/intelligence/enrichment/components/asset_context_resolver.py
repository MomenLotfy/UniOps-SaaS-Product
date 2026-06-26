from __future__ import annotations
from typing import Any, Dict, List
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.utils.logger import logger

class AssetContextResolver(IEnricher):
    """
    Associates the finding with specific organizational assets.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[AssetContextResolver] Resolving asset context for {context.finding_id}")

        # Extract asset data from raw_metadata (which comes from the scanner)
        asset_meta = context.raw_metadata

        context.asset_context = {
            "repository": asset_meta.get("repository"),
            "service": asset_meta.get("service"),
            "application": asset_meta.get("application"),
            "cluster": asset_meta.get("cluster"),
            "namespace": asset_meta.get("namespace"),
            "environment": asset_meta.get("environment", "production"),
            "team": asset_meta.get("team"),
            "owner": asset_meta.get("owner"),
            "tenant": context.tenant_id
        }

        # If the asset is marked as 'critical', it increases business risk
        if asset_meta.get("asset_criticality", 1.0) > 1.5:
            context.business_risk += 10.0
