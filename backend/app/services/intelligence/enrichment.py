from __future__ import annotations
from typing import Any, Dict, Optional, List
from datetime import datetime
from app.schemas.intelligence import (
    EnrichedFinding, CanonicalCVE, CanonicalPackage,
    CanonicalExploit, CanonicalWeakness, CanonicalAttackPattern,
    CanonicalRisk, CanonicalRemediationReference, ConfidenceLevel
)
from app.services.intelligence.normalization import NormalizationLayer
from app.services.intelligence.risk_calculator import RiskCalculator
from app.utils.logger import logger

class EnrichmentEngine:
    """
    The pipeline that transforms a raw scanner finding into an EnrichedFinding.
    Orchestrates the lookup and normalization process.
    """
    def __init__(self, intelligence_service: Any):
        self.intel_service = intelligence_service
        self.normalizer = NormalizationLayer()
        self.risk_calculator = RiskCalculator()

    async def enrich(self, finding_id: str, tenant_id: str, raw_metadata: Dict[str, Any]) -> EnrichedFinding:
        """
        Full enrichment pipeline.
        """
        logger.info(f"[EnrichmentEngine] Enriching finding {finding_id} for tenant {tenant_id}")

        # 1. Extract identifiers
        cve_id = raw_metadata.get("cve_id")
        purl = raw_metadata.get("purl")

        # 2. Fetch intelligence from service (which handles caching)
        vulnerability = None
        if cve_id:
            vulnerability = await self.intel_service.get_vulnerability(cve_id)

        package = None
        if purl:
            package = await self.intel_service.get_package(purl)

        exploit = None
        if cve_id:
            exploit = await self.intel_service.get_exploit(cve_id)

        # 3. Calculate Business Risk
        risk = self.risk_calculator.calculate_risk(
            cvss_score=vulnerability.cvss_score if vulnerability else None,
            exploit_maturity=exploit.maturity if exploit else "unknown",
            is_known_exploited=False, # Future integration with CISA KEV
            asset_criticality=raw_metadata.get("asset_criticality", 1.0)
        )

        # 4. Assemble Enriched Finding
        return EnrichedFinding(
            finding_id=finding_id,
            tenant_id=tenant_id,
            vulnerability=vulnerability,
            package=package,
            exploit=exploit,
            risk=risk,
            confidence=ConfidenceLevel.HIGH if vulnerability and exploit else ConfidenceLevel.MEDIUM,
            providers_used=await self.intel_service.get_active_providers(),
            last_enriched_at=datetime.utcnow()
        )
