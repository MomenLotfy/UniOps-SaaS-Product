from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class EntitySchema(BaseModel):
    """Standardized representation of a graph node."""
    id: str
    tenant_id: str
    entity_type: str # e.g., 'CVE', 'Package', 'Pod'
    canonical_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    confidence: float = 1.0
    provenance: Dict[str, Any] = {}
    version: int = 1

class RelationshipSchema(BaseModel):
    """Standardized representation of a graph edge."""
    id: str
    tenant_id: str
    source_id: str
    target_id: str
    relationship_type: str # e.g., 'AFFECTS', 'DEPENDS_ON'
    confidence: float = 1.0
    evidence: Optional[str] = None
    provenance: Dict[str, Any] = {}

class GraphQueryResponse(BaseModel):
    """Results of a graph traversal query."""
    query_type: str
    results: List[EntitySchema]
    relationships: List[RelationshipSchema]
    metadata: Dict[str, Any] = {
        "traversal_time_ms": 0.0,
        "nodes_visited": 0,
        "edges_traversed": 0
    }

class GraphStatsSchema(BaseModel):
    """Distribution and health metrics of the graph."""
    entity_distribution: Dict[str, int] # type -> count
    relationship_distribution: Dict[str, int] # type -> count
    total_entities: int
    total_relationships: int
    health_status: str
    last_updated: datetime
