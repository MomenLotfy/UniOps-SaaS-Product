from __future__ import annotations
from abc import ABC, abstractmethod
from app.services.intelligence.enrichment.context import EnrichmentContext

class IEnricher(ABC):
    """
    Abstract Base Class for all Enrichment components.
    Each enricher takes an EnrichmentContext and modifies it in place.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def enrich(self, context: EnrichmentContext) -> None:
        """
        Performs enrichment and updates the provided context.
        """
        pass
