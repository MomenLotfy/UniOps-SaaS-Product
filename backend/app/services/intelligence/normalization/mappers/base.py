from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from app.schemas.intelligence import (
    CanonicalCVE, CanonicalPackage, CanonicalExploit,
    CanonicalWeakness, CanonicalAttackPattern, ProvenanceMetadata
)

class ProviderMapper(ABC):
    """
    Abstract Base Class for all Provider Mappers.
    Converts raw provider-specific responses into canonical fragments.
    """

    def __init__(self, provider_id: str, provider_version: str):
        self.provider_id = provider_id
        self.provider_version = provider_version

    def create_provenance(self, trust_score: float = 1.0) -> ProvenanceMetadata:
        """Helper to create provenance for a specific field."""
        return ProvenanceMetadata(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            trust_score=trust_score
        )

    @abstractmethod
    def map_vulnerability(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Maps raw vulnerability data to a partial CanonicalCVE structure.
        Returns a dict of fields to be merged.
        """
        pass

    @abstractmethod
    def map_package(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Maps raw package data to a partial CanonicalPackage structure.
        """
        pass

    @abstractmethod
    def map_exploit(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Maps raw exploit data to a partial CanonicalExploit structure.
        """
        pass
