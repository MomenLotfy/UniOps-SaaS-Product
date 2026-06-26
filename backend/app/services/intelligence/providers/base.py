from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.schemas.intelligence import CanonicalCVE, CanonicalPackage, CanonicalExploit, CanonicalRemediationReference

class IIntelligenceProvider(ABC):
    """
    Abstract Base Class for all Security Intelligence Providers.
    Each provider (NVD, OSV, GitHub, etc.) must implement these methods.
    """

    @property
    def provider_id(self) -> str:
        """Unique identifier for the provider (e.g., 'nvd', 'osv')."""
        pass

    @property
    def name(self) -> str:
        """Human-readable name of the provider."""
        pass

    async def fetch_vulnerability_data(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches raw vulnerability data for a given CVE ID.
        Returns a dictionary that the Normalization Layer will later process.
        """
        pass

    async def fetch_package_info(self, purl: str) -> Optional[Dict[str, Any]]:
        """
        Fetches intelligence related to a specific package (via PURL).
        """
        pass

    async def fetch_exploit_info(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches exploit maturity and availability data.
        """
        pass

    async def check_health(self) -> Dict[str, Any]:
        """
        Performs a connectivity and health check on the provider's API.
        """
        pass
