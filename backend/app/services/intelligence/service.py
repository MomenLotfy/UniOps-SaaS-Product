from __future__ import annotations
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.base import BaseService
from app.models.intelligence import (
    IntelligenceCacheEntry, ProviderMetadata, ProviderHealth,
    SyncHistory, IntelligenceVersion
)
from app.schemas.intelligence import CanonicalCVE, CanonicalPackage, CanonicalExploit
from app.services.intelligence.providers.manager import IntelligenceProviderManager
from app.services.intelligence.normalization.engine import IntelligenceNormalizationEngine
from app.services.intelligence.normalization.mappers.base import ProviderMapper
from app.services.intelligence.normalization.mappers.impls.nvd import NvdMapper
from app.services.intelligence.normalization.mappers.impls.osv import OsvMapper
from app.core.intelligence_cache import IntelligenceCache
from app.utils.logger import logger

class IntelligenceService(BaseService):
    """
    The primary facade for the Security Intelligence domain.
    Coordinates providers, normalization, and cache.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.manager = IntelligenceProviderManager()

        # Initialize Normalization Engine with registered mappers
        mappers = {
            "nvd": NvdMapper("nvd", "1.0.0"),
            "osv": OsvMapper("osv", "1.0.0"),
            # Other mappers would be added here or loaded dynamically
        }
        self.normalization_engine = IntelligenceNormalizationEngine(mappers)
        self.cache = IntelligenceCache()

    async def get_vulnerability(self, cve_id: str) -> Optional[CanonicalCVE]:
        """Fetches normalized CVE data, checking cache first."""
        # 1. Check Cache
        cached = await self.cache.get(cve_id)
        if cached:
            return CanonicalCVE(**cached)

        # 2. Fetch raw data from all capable providers
        providers = await self.manager.resolve_all_capable_providers("CVE")
        if not providers:
            logger.warning(f"[IntelligenceService] No capable providers for CVE lookup: {cve_id}")
            return None

        provider_responses = []
        for provider in providers:
            try:
                raw_data = await provider.fetch_vulnerability_data(cve_id)
                if raw_data:
                    provider_responses.append({
                        "provider_id": provider.provider_id,
                        "data": raw_data
                    })
            except Exception as e:
                logger.error(f"[IntelligenceService] Provider {provider.name} failed to fetch {cve_id}: {e}")

        if not provider_responses:
            return None

        # 3. Normalize and Merge
        canonical_cve = await self.normalization_engine.normalize_vulnerability(cve_id, provider_responses)

        if canonical_cve:
            # Cache the canonical result
            await self.cache.set(cve_id, canonical_cve.dict())
            return canonical_cve

        return None

    async def get_package(self, purl: str) -> Optional[CanonicalPackage]:
        """Fetches normalized package data."""
        cached = await self.cache.get(purl)
        if cached:
            return CanonicalPackage(**cached)

        providers = await self.manager.resolve_all_capable_providers("PURL")
        if not providers:
            return None

        provider_responses = []
        for provider in providers:
            try:
                raw_data = await provider.fetch_package_info(purl)
                if raw_data:
                    provider_responses.append({
                        "provider_id": provider.provider_id,
                        "data": raw_data
                    })
            except Exception as e:
                logger.error(f"[IntelligenceService] Provider {provider.name} failed to fetch package {purl}: {e}")

        if not provider_responses:
            return None

        canonical_pkg = await self.normalization_engine.normalize_package(purl, provider_responses)

        if canonical_pkg:
            await self.cache.set(purl, canonical_pkg.dict())
            return canonical_pkg

        return None

    async def get_exploit(self, cve_id: str) -> Optional[CanonicalExploit]:
        """Fetches normalized exploit data."""
        cached = await self.cache.get(f"exploit:{cve_id}")
        if cached:
            return CanonicalExploit(**cached)

        providers = await self.manager.resolve_all_capable_providers("EXPLOIT")
        if not providers:
            return None

        provider_responses = []
        for provider in providers:
            try:
                raw_data = await provider.fetch_exploit_info(cve_id)
                if raw_data:
                    provider_responses.append({
                        "provider_id": provider.provider_id,
                        "data": raw_data
                    })
            except Exception as e:
                logger.error(f"[IntelligenceService] Provider {provider.name} failed to fetch exploit {cve_id}: {e}")

        if not provider_responses:
            return None

        # Exploit normalization not yet fully implemented in engine, using simplified logic
        # In a real system, this would use normalization_engine.normalize_exploit
        return None

    async def get_active_providers(self) -> List[str]:
        """Returns list of currently active provider IDs."""
        providers = await self.manager.list_active_providers()
        return [p.provider_id for p in providers]

    async def get_provider_health(self) -> List[Dict[str, Any]]:
        """Fetches real-time health status for all providers."""
        health = await self.manager.get_health_report()
        return [{"provider_id": pid, **data} for pid, data in health.items()]

    async def get_provider_status(self) -> List[Dict[str, Any]]:
        """Fetches operational status for all providers from DB."""
        result = await self.db.execute(select(ProviderMetadata))
        return [m.__dict__ for m in result.scalars().all()]
