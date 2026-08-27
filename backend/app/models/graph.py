from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class GraphEntity(BaseModel):
    """
    A canonical node in the Security Knowledge Graph.
    Represents any security-relevant object (CVE, Package, Pod, etc.).
    """
    __tablename__ = "security_graph_entities"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True) # e.g., 'CVE', 'Package', 'Pod'

    # Canonical identity and metadata
    canonical_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    # `metadata` is reserved by SQLAlchemy's Declarative API. Keep the
    # existing database column name while using a safe Python attribute.
    graph_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Quality & Trust
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)

    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relationships (Edges)
    outgoing: Mapped[List["GraphRelationship"]] = relationship(
        "GraphRelationship",
        foreign_keys="GraphRelationship.source_id",
        back_populates="source"
    )
    incoming: Mapped[List["GraphRelationship"]] = relationship(
        "GraphRelationship",
        foreign_keys="GraphRelationship.target_id",
        back_populates="target"
    )

class GraphRelationship(BaseModel):
    """
    A canonical edge in the Security Knowledge Graph.
    """
    __tablename__ = "security_graph_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    # Edge definition
    source_id: Mapped[str] = mapped_column(String(255), ForeignKey("security_graph_entities.id"), index=True)
    target_id: Mapped[str] = mapped_column(String(255), ForeignKey("security_graph_entities.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), index=True) # e.g., 'AFFECTS', 'DEPENDS_ON'

    # Edge metadata
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[Optional[str]] = mapped_column(JSON)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    source: Mapped["GraphEntity"] = relationship(back_populates="outgoing")
    target: Mapped["GraphEntity"] = relationship(back_populates="incoming")

class EntityResolutionLog(BaseModel):
    """
    Tracks how multiple identifiers were resolved into a single canonical entity.
    """
    __tablename__ = "security_graph_resolution_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_entity_id: Mapped[str] = mapped_column(String(255), ForeignKey("security_graph_entities.id"), index=True)

    original_id: Mapped[str] = mapped_column(String(255))
    original_provider: Mapped[str] = mapped_column(String(100))
    resolution_method: Mapped[str] = mapped_column(String(100)) # e.g., 'PURL_MATCH', 'CVE_ID_MATCH'

    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class GraphMetadata(BaseModel):
    """
    Global state and versioning for the Knowledge Graph.
    """
    __tablename__ = "security_graph_metadata"

    version_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    entity_count: Mapped[int] = mapped_column(Integer)
    relationship_count: Mapped[int] = mapped_column(Integer)
    last_update_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(50)) # healthy, rebuilding, degraded
