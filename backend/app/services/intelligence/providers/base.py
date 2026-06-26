from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
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

    @property
    def provider_version(self) -> str:
        """Current version of the provider implementation."""
        pass

    @property
    def provider_type(self) -> str:
        """Category of provider (e.g., 'official', 'community', 'vendor')."""
        pass

    @property
    def supported_intelligence_types(self) -> List[str]:
        """List of data types this provider can produce (e.g., ['CVE', 'Exploit'])."""
        pass

    @property
    def supported_lookup_types(self) -> Set[str]:
        """Set of lookup keys this provider supports (e.g., {'CVE', 'PURL', 'CWE'})."""
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

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validates provider-specific configuration settings.
        Returns True if valid, False or raises ProviderConfigurationError otherwise.
        """
        pass

    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Returns current API rate limit status and constraints.
        """
        pass

    async def get_capabilities_metadata(self) -> Dict[str, Any]:
        """
        Detailed description of what the provider can actually do (e.g. specific CVE ranges).
        """
        pass
