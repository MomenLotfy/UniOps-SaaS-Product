from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ProvenanceMetadata(BaseModel):
    """Source tracking for relationship intelligence."""
    source: str
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ImpactSummary(BaseModel):
    """High-level view of the security impact of a finding."""
    finding_id: str
    affected_assets: List[str] = []
    affected_services: List[str] = []
    affected_teams: List[str] = []
    affected_repositories: List[str] = []
    business_impact_score: float = 0.0
    critical_paths_count: int = 0

class BlastRadiusSchema(BaseModel):
    """Detailed propagation of a vulnerability across the graph."""
    immediate: List[str] = [] # Direct dependents
    extended: List[str] = []  # 2-3 hops away
    potential: List[str] = [] # Reachable via conditional paths
    total_impacted_nodes: int = 0

class DependencyChainSchema(BaseModel):
    """Linear representation of a dependency path."""
    chain: List[str] # [CVE -> Pkg -> Container -> Pod]
    depth: int
    is_circular: bool = False

class OwnershipSchema(BaseModel):
    """Resolved ownership hierarchy for an entity."""
    entity_id: str
    technical_owner: str
    business_owner: str
    team: str
    escalation_path: List[str] = []

class RelationshipIntelligence(BaseModel):
    """The core reasoning output for a relationship."""
    source_id: str
    target_id: str
    relationship_type: str
    strength: float # 0.0 - 1.0
    criticality: float # 0.0 - 1.0
    evidence: Optional[str] = None
