from __future__ import annotations
from typing import Dict, Any, Type, Optional
import importlib
from app.utils.logger import logger
from app.services.intelligence.providers.base import IIntelligenceProvider
from app.services.intelligence.exceptions import ProviderInitializationError, ProviderConfigurationError

class ProviderLoader:
    """
    Responsible for dynamically instantiating provider classes based on the registry.
    Handles the mapping between provider IDs and their Python implementation classes.
    """

    # Mapping of provider_id to the implementation class path
    # This can be extended to a config file or database mapping
    PROVIDER_MAP: Dict[str, str] = {
        "nvd": "app.services.intelligence.providers.impls.nvd.NvdProvider",
        "osv": "app.services.intelligence.providers.impls.osv.OsvProvider",
        "ghsa": "app.services.intelligence.providers.impls.ghsa.GhsaProvider",
        "cisa": "app.services.intelligence.providers.impls.cisa.CisaKevProvider",
        "epss": "app.services.intelligence.providers.impls.epss.EpssProvider",
        "cwe": "app.services.intelligence.providers.impls.cwe.CweProvider",
        "capec": "app.services.intelligence.providers.impls.capec.CapecProvider",
        "owasp": "app.services.intelligence.providers.impls.owasp.OwaspProvider",
        "vendor": "app.services.intelligence.providers.impls.vendor.VendorAdvisoryProvider",
    }

    @classmethod
    def load_provider(cls, provider_id: str, config: Optional[Dict[str, Any]] = None) -> IIntelligenceProvider:
        """
        Dynamically loads and instantiates an intelligence provider.
        """
        if provider_id not in cls.PROVIDER_MAP:
            logger.error(f"[ProviderLoader] No implementation found for provider: {provider_id}")
            raise ProviderInitializationError(f"Provider {provider_id} is not implemented.")

        try:
            module_path, class_name = cls.PROVIDER_MAP[provider_id].rsplit(".", 1)
            module = importlib.import_module(module_path)
            provider_class: Type[IIntelligenceProvider] = getattr(module, class_name)

            logger.info(f"[ProviderLoader] Instantiating provider {provider_id} via {class_name}")

            # In a real implementation, we'd pass the config to the constructor
            # For these architecture stubs, we assume a default constructor
            instance = provider_class()

            # Validate configuration if provided
            if config:
                if not await instance.validate_config(config):
                    raise ProviderConfigurationError(f"Invalid configuration provided for {provider_id}")

            return instance

        except Exception as e:
            logger.exception(f"[ProviderLoader] Failed to load provider {provider_id}: {e}")
            raise ProviderInitializationError(f"Critical failure during initialization of {provider_id}: {e}")
