from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.utils.logger import logger

from .pipeline import NormalizationPipeline
from .mappers.base import ProviderMapper
from .merge_engine import MergeEngine
from .conflict_resolver import ConflictResolver
from .version_resolver import VersionResolver
from .reference_resolver import ReferenceResolver
from .quality_validator import DataQualityValidator

class IntelligenceNormalizationEngine:
    """
    The core engine that orchestrates the transformation of raw provider responses
    into canonical internal representations.
    """
    def __init__(self, mappers: Dict[str, ProviderMapper]):
        self.mappers = mappers
        self.conflict_resolver = ConflictResolver()
        self.merge_engine = MergeEngine(self.conflict_resolver)
        self.version_resolver = VersionResolver()
        self.ref_resolver = ReferenceResolver()
        self.quality_validator = DataQualityValidator()

    async def normalize_vulnerability(self, cve_id: str, provider_responses: List[Dict[str, Any]]) -> Optional[Any]:
        """
        Transforms multiple raw provider responses for a CVE into a single CanonicalCVE.
        """
        logger.info(f"[NormalizationEngine] Normalizing vulnerability {cve_id} from {len(provider_responses)} providers")

        fragments = []
        for resp in provider_responses:
            pid = resp.get("provider_id")
            mapper = self.mappers.get(pid)
            if not mapper:
                logger.warning(f"[NormalizationEngine] No mapper found for provider {pid}")
                continue

            # 1. Map raw data to partial canonical fragment
            fragment = await mapper.map_vulnerability(resp.get("data", {}))
            if fragment:
                fragment["provider_id"] = pid # Ensure pid is present for merging
                fragments.append(fragment)

        if not fragments:
            return None

        # 2. Merge fragments into one canonical object
        merged_cve = await self.merge_engine.merge_vulnerabilities(cve_id, fragments)

        # 3. Perform quality validation
        score, missing = self.quality_validator.validate_cve(merged_cve)
        logger.info(f"[NormalizationEngine] CVE {cve_id} normalization complete. Quality Score: {score}")

        return merged_cve

    async def normalize_package(self, purl: str, provider_responses: List[Dict[str, Any]]) -> Optional[Any]:
        """Transforms multiple raw provider responses for a package into a CanonicalPackage."""
        fragments = []
        for resp in provider_responses:
            pid = resp.get("provider_id")
            mapper = self.mappers.get(pid)
            if not mapper: continue

            fragment = await mapper.map_package(resp.get("data", {}))
            if fragment:
                fragment["provider_id"] = pid
                fragments.append(fragment)

        if not fragments: return None

        # Simplified merge for packages (picking first successful)
        # In a real system, we would merge package metadata across providers
        winner = fragments[0]
        from app.schemas.intelligence import CanonicalPackage, CanonicalVersion, CanonicalEcosystem

        return CanonicalPackage(
            purl=purl,
            name=winner.get("name", "Unknown"),
            version=CanonicalVersion(
                original=winner.get("version", ""),
                normalized=self.version_resolver.normalize_version(winner.get("version", ""), "unknown"),
                ecosystem="unknown"
            ),
            ecosystem=CanonicalEcosystem(id="unknown", name="Unknown"),
            provenance={ "purl": ProvenanceMetadata(provider_id=winner["provider_id"], provider_version="1.0.0") }
        )
