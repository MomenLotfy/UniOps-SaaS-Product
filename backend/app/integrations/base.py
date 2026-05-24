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
