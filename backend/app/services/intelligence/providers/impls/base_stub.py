from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
from app.services.intelligence.providers.base import IIntelligenceProvider

class BaseStubProvider(IIntelligenceProvider):
    """
    Base implementation for architecture stubs.
    Provides default empty implementations for the interface.
    """
    def __init__(self, provider_id: str, name: str, version: str,
                 provider_type: str, supported_types: List[str],
                 supported_lookups: Set[str]):
        self._provider_id = provider_id
        self._name = name
        self._version = version
        self._type = provider_type
        self._supported_types = supported_types
        self._supported_lookups = supported_lookups

    @property
    def provider_id(self) -> str: return self._provider_id

    @property
    def name(self) -> str: return self._name

    @property
    def provider_version(self) -> str: return self._version

    @property
    def provider_type(self) -> str: return self._type

    @property
    def supported_intelligence_types(self) -> List[str]: return self._supported_types

    @property
    def supported_lookup_types(self) -> Set[str]: return self._supported_lookups

    async def fetch_vulnerability_data(self, cve_id: str) -> Optional[Dict[str, Any]]:
        return None # Architecture stub

    async def fetch_package_info(self, purl: str) -> Optional[Dict[str, Any]]:
        return None # Architecture stub

    async def fetch_exploit_info(self, cve_id: str) -> Optional[Dict[str, Any]]:
        return None # Architecture stub

    async def check_health(self) -> Dict[str, Any]:
        return {"status": "healthy", "latency_ms": 10.5, "error": None}

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def get_rate_limit_info(self) -> Dict[str, Any]:
        return {"limit": "unlimited", "remaining": "N/A", "reset": None}

    async def get_capabilities_metadata(self) -> Dict[str, Any]:
        return {"description": f"Stub implementation for {self.name}"}
