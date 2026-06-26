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
from app.services.intelligence.normalization import NormalizationLayer
from app.core.intelligence_cache import IntelligenceCache
from app.utils.logger import logger

class IntelligenceService(BaseService):
    """
    The primary facade for the Security Intelligence domain.
    Coordinates providers, cache, and normalization.
    """
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.manager = IntelligenceProviderManager()
        self.cache = IntelligenceCache()
        self.normalizer = NormalizationLayer()

    async def get_vulnerability(self, cve_id: str) -> Optional[CanonicalCVE]:
        """Fetches normalized CVE data, checking cache first."""
        # 1. Check Cache
        cached = await self.cache.get(cve_id)
        if cached:
            return CanonicalCVE(**cached)

        # 2. Resolve best provider for this lookup
        provider = await self.manager.resolve_provider("CVE", context={"id": cve_id})
        if not provider:
            logger.warning(f"[IntelligenceService] No capable provider for CVE lookup: {cve_id}")
            return None

        try:
            raw_data = await provider.fetch_vulnerability_data(cve_id)
            if raw_data:
                normalized = self.normalizer.normalize_vulnerability(provider.provider_id, raw_data)
                if normalized:
                    # Cache the result
                    await self.cache.set(cve_id, normalized.dict())
                    return normalized
        except Exception as e:
            logger.error(f"[IntelligenceService] Provider {provider.name} failed to fetch {cve_id}: {e}")

        return None

    async def get_package(self, purl: str) -> Optional[CanonicalPackage]:
        """Fetches normalized package data."""
        cached = await self.cache.get(purl)
        if cached:
            return CanonicalPackage(**cached)

        provider = await self.manager.resolve_provider("PURL", context={"purl": purl})
        if not provider:
            logger.warning(f"[IntelligenceService] No capable provider for PURL lookup: {purl}")
            return None

        try:
            raw_data = await provider.fetch_package_info(purl)
            if raw_data:
                normalized = self.normalizer.normalize_package(provider.provider_id, raw_data)
                if normalized:
                    await self.cache.set(purl, normalized.dict())
                    return normalized
        except Exception as e:
            logger.error(f"[IntelligenceService] Provider {provider.name} failed to fetch package {purl}: {e}")

        return None

    async def get_exploit(self, cve_id: str) -> Optional[CanonicalExploit]:
        """Fetches normalized exploit data."""
        cached = await self.cache.get(f"exploit:{cve_id}")
        if cached:
            return CanonicalExploit(**cached)

        provider = await self.manager.resolve_provider("EXPLOIT", context={"id": cve_id})
        if not provider:
            logger.warning(f"[IntelligenceService] No capable provider for exploit lookup: {cve_id}")
            return None

        try:
            raw_data = await provider.fetch_exploit_info(cve_id)
            if raw_data:
                normalized = self.normalizer.normalize_exploit(provider.provider_id, raw_data)
                if normalized:
                    await self.cache.set(f"exploit:{cve_id}", normalized.dict())
                    return normalized
        except Exception as e:
            logger.error(f"[IntelligenceService] Provider {provider.name} failed to fetch exploit {cve_id}: {e}")

        return None

    async def get_active_providers(self) -> List[str]:
        """Returns list of currently active provider IDs."""
        providers = await self.manager.list_active_providers()
        return [p.provider_id for p in providers]

    async def get_provider_health(self) -> List[Dict[str, Any]]:
        """Fetches real-time health status for all providers."""
        health = await self.manager.get_health_report()
        # Transform into a list for the API schema
        return [{"provider_id": pid, **data} for pid, data in health.items()]

    async def get_provider_status(self) -> List[Dict[str, Any]]:
        """Fetches operational status for all providers from DB."""
        result = await self.db.execute(select(ProviderMetadata))
        return [m.__dict__ for m in result.scalars().all()]
