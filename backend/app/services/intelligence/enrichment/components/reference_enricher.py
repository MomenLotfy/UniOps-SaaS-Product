from __future__ import annotations
from typing import Any, Dict, List
from .base import IEnricher
from app.services.intelligence.enrichment.context import EnrichmentContext
from app.schemas.intelligence import CanonicalRemediationReference, ProvenanceMetadata
from app.utils.logger import logger

class ReferenceEnricher(IEnricher):
    """
    Enriches the finding with a comprehensive set of security references,
    advisories, and official links.
    """
    async def enrich(self, context: EnrichmentContext) -> None:
        logger.info(f"[ReferenceEnricher] Enriching references for finding {context.finding_id}")

        references = []

        # 1. Extract references from the Canonical CVE
        if context.vulnerability:
            for ref_url in context.vulnerability.references:
                references.append(self._create_canonical_ref(ref_url, "nvd"))

        # 2. Extract from Canonical Advisories
        if context.vulnerability and context.vulnerability.advisories:
            for adv in context.vulnerability.advisories:
                references.append(CanonicalRemediationReference(
                    ref_id=adv.advisory_id,
                    type="advisory",
                    url="https://example.com/advisory/" + adv.advisory_id,
                    title=adv.title,
                    is_official=True,
                    provenance=adv.provenance
                ))

        # 3. Add placeholders for other references (CISA, GHSA etc)
        # In a real implementation, this would involve lookups in the IntelligenceService

        context.references = references
        context.add_metadata("reference_count", len(references))

    def _create_canonical_ref(self, url: str, provider: str) -> CanonicalRemediationReference:
        return CanonicalRemediationReference(
            ref_id=f"ref_{hash(url)}",
            type="general",
            url=url,
            title=url,
            is_official=False,
            provenance=ProvenanceMetadata(
                provider_id=provider,
                provider_version="1.0.0",
                trust_score=0.7
            )
        )
