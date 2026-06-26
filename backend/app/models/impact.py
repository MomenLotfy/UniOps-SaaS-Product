from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class ImpactAnalysis(BaseModel):
    """
    Persists the results of an impact analysis for a specific finding.
    """
    __tablename__ = "security_impact_analyses"

    finding_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    # Impact Summaries
    affected_assets_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_services_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_repos_count: Mapped[int] = mapped_column(Integer, default=0)

    # Detailed Analysis (Stored as JSON for flexibility)
    blast_radius_metadata: Mapped[dict] = mapped_column(JSON, default=dict) # {immediate: [], extended: [], potential: []}
    dependency_chains: Mapped[list] = mapped_column(JSON, default=list)
    business_impact_score: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class RelationshipScore(BaseModel):
    """
    Weights the significance of relationships in the graph.
    """
    __tablename__ = "security_relationship_scores"

    relationship_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    criticality_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    description: Mapped[Optional[str]] = mapped_column(String(500))

class OwnershipMapping(BaseModel):
    """
    Maps entities to their technical and business owners.
    """
    __tablename__ = "security_ownership_mappings"

    entity_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    technical_owner: Mapped[str] = mapped_column(String(255)) # Team/User ID
    business_owner: Mapped[str] = mapped_column(String(255))
    escalation_path: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class TraversalHistory(BaseModel):
    """
    Audit log of complex graph traversals for performance tuning.
    """
    __tablename__ = "security_traversal_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query_type: Mapped[str] = mapped_column(String(100))
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    nodes_visited: Mapped[int] = mapped_column(Integer)
    edges_traversed: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
