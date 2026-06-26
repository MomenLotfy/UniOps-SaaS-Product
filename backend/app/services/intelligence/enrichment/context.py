from __future__ import annotations
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from app.schemas.intelligence import (
    CanonicalCVE, CanonicalPackage, CanonicalExploit,
    CanonicalWeakness, CanonicalAttackPattern
)

@dataclass
class EnrichmentContext:
    """
    Carries the state of an enrichment process across the pipeline.
    Allows enrichers to share data and contribute to the final result.
    """
    finding_id: str
    tenant_id: str
    raw_metadata: Dict[str, Any]

    # Canonical Intelligence (Input)
    vulnerability: Optional[CanonicalCVE] = None
    package: Optional[CanonicalPackage] = None
    exploit: Optional[CanonicalExploit] = None
    weakness: Optional[CanonicalWeakness] = None
    attack_pattern: Optional[CanonicalAttackPattern] = None

    # Enrichment Results (Accumulated)
    references: List[Any] = field(default_factory=list)
    patches: List[Any] = field(default_factory=list)
    business_impact: Dict[str, Any] = field(default_factory=dict)
    asset_context: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[Any] = field(default_factory=list)
    timeline: List[Any] = field(default_factory=list)

    # Risk and Confidence
    technical_risk: float = 0.0
    business_risk: float = 0.0
    environmental_risk: float = 0.0
    overall_risk: float = 0.0
    confidence_score: float = 0.0
    trust_score: float = 0.0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    def add_metadata(self, key: str, value: Any):
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)
