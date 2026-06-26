from __future__ import annotations
from typing import Dict, List, Optional, Set
from app.services.intelligence.providers.base import IIntelligenceProvider
from app.utils.logger import logger

class IntelligenceProviderRegistry:
    """
    Singleton registry for managing intelligence providers.
    Handles registration, discovery, and lifecycle of providers.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IntelligenceProviderRegistry, cls).__new__(cls)
            cls._instance._providers: Dict[str, IIntelligenceProvider] = {}
            cls._instance._active_ids: Set[str] = set()
        return cls._instance

    def register_provider(self, provider: IIntelligenceProvider, active: bool = True) -> None:
        """Registers a provider instance."""
        self._providers[provider.provider_id] = provider
        if active:
            self._active_ids.add(provider.provider_id)
        logger.info(f"[IntelligenceRegistry] Registered provider: {provider.name} ({provider.provider_id}) - active={active}")

    def get_provider(self, provider_id: str) -> Optional[IIntelligenceProvider]:
        """Retrieves a specific provider by ID."""
        return self._providers.get(provider_id)

    def list_providers(self, only_active: bool = False) -> List[IIntelligenceProvider]:
        """Returns currently registered providers."""
        if only_active:
            return [self._providers[pid] for pid in self._active_ids if pid in self._providers]
        return list(self._providers.values())

    def get_all_provider_ids(self, only_active: bool = False) -> List[str]:
        """Returns a list of registered provider IDs."""
        if only_active:
            return list(self._active_ids)
        return list(self._providers.keys())

    def enable_provider(self, provider_id: str) -> bool:
        """Activates a provider if it is registered."""
        if provider_id in self._providers:
            self._active_ids.add(provider_id)
            return True
        return False

    def disable_provider(self, provider_id: str) -> bool:
        """Deactivates a provider."""
        if provider_id in self._active_ids:
            self._active_ids.remove(provider_id)
            return True
        return False

    def discover_capabilities(self, lookup_type: str) -> List[IIntelligenceProvider]:
        """
        Finds all active providers that support a specific lookup type (e.g., 'CVE').
        """
        return [
            p for pid, p in self._providers.items()
            if pid in self._active_ids and lookup_type in p.supported_lookup_types
        ]

    def get_provider_version(self, provider_id: str) -> Optional[str]:
        """Returns the implementation version of a provider."""
        p = self.get_provider(provider_id)
        return p.provider_version if p else None
