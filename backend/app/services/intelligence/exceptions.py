from __future__ import annotations
from typing import Optional

class IntelligenceProviderError(Exception):
    """Base exception for all intelligence provider related errors."""
    def __init__(self, message: str, provider_id: Optional[str] = None):
        super().__init__(message)
        self.provider_id = provider_id

class ProviderConfigurationError(IntelligenceProviderError):
    """Raised when provider configuration is invalid or missing."""
    pass

class ProviderInitializationError(IntelligenceProviderError):
    """Raised when a provider fails to initialize correctly."""
    pass

class ProviderValidationError(IntelligenceProviderError):
    """Raised when data returned by a provider fails normalization validation."""
    pass

class UnsupportedLookupError(IntelligenceProviderError):
    """Raised when a provider is asked to perform a lookup it does not support."""
    pass

class ProviderUnavailableError(IntelligenceProviderError):
    """Raised when a provider is unreachable or in maintenance mode."""
    pass

class ProviderTimeoutError(ProviderUnavailableError):
    """Raised when a provider request times out."""
    pass
