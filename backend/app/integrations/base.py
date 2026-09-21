"""Base integration class — all third-party clients extend this."""
from abc import ABC, abstractmethod
from typing import Optional, Any
from app.utils.logger import logger


class BaseIntegration(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

    @abstractmethod
    async def sync(self) -> dict:
        pass

    def _get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    async def _safe_request(self, coro, error_default=None):
        try:
            return await coro
        except Exception as e:
            logger.error(f"{self.__class__.__name__} request failed: {e}")
            return error_default


# ── Provider failure contract ────────────────────────────────────────────────
#
# Integration clients in this project report outcomes as dicts of the shape
# ``{"success": bool, "error": str | None, ...}``. Endpoints that returned
# those dicts verbatim produced HTTP 200 ``success: true`` envelopes for
# operations the provider had actually rejected (audit BUG-004 / BUG-006).
#
# ``raise_for_provider_failure`` is the single translation point from that
# dict convention onto the project's existing exception contract:
#
#   provider unavailable / not configured -> IntegrationUnavailableError (503)
#   resource not found                    -> NotFoundError               (404)
#   invalid operation or state            -> ConflictError               (409)
#   any other provider rejection          -> IntegrationError            (502)
#
# It deliberately reuses ``app.core.exceptions`` rather than introducing a
# second response convention.

_NOT_FOUND_MARKERS = (
    "not found", "notfound", "does not exist", "no such", "404",
)
_CONFLICT_MARKERS = (
    "already exists", "conflict", "already running", "invalid state", "409",
)
_UNAVAILABLE_MARKERS = (
    "connection refused", "max retries exceeded", "timed out", "timeout",
    "name or service not known", "no route to host", "unavailable",
    "no kubernetes integration", "client unavailable", "certificate verify",
)


def _classify(message: str) -> str:
    low = (message or "").lower()
    if any(m in low for m in _NOT_FOUND_MARKERS):
        return "not_found"
    if any(m in low for m in _CONFLICT_MARKERS):
        return "conflict"
    if any(m in low for m in _UNAVAILABLE_MARKERS):
        return "unavailable"
    return "integration_error"


def raise_for_provider_failure(result: dict, integration: str = "Kubernetes"):
    """
    Return ``result`` when the provider operation succeeded, otherwise raise
    the project exception that matches the failure.

    This exists so no caller can accidentally turn a failed provider mutation
    into a successful HTTP response.
    """
    if result.get("success"):
        return result

    from app.core.exceptions import (
        ConflictError, IntegrationError, IntegrationUnavailableError,
        ProviderResourceNotFoundError,
    )

    message = result.get("error") or f"{integration} operation failed"

    # An explicit "provider not connected" signal wins over message sniffing.
    if result.get("connected") is False:
        raise IntegrationUnavailableError(integration, message)

    kind = _classify(message)
    if kind == "not_found":
        # ProviderResourceNotFoundError, not NotFoundError: the latter formats
        # f"{resource} not found" and would mangle the provider's own message.
        raise ProviderResourceNotFoundError(message)
    if kind == "conflict":
        raise ConflictError(message)
    if kind == "unavailable":
        raise IntegrationUnavailableError(integration, message)
    raise IntegrationError(integration, message)
