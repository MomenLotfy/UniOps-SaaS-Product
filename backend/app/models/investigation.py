from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean, Float, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class InvestigationSession(Base):
    """
    Persists the state of a security investigation.
    Allows researchers to resume work with their filters and context intact.
    """
    __tablename__ = "investigation_sessions"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)

    # State persistence
    current_context = Column(JSON, nullable=False, default=dict)  # Current filters, search terms, etc.
    pagination_state = Column(JSON, nullable=True)              # Last page, offset, etc.
    sorting_state = Column(JSON, nullable=True)                  # sort_by, direction

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    bookmarks = relationship("InvestigationBookmark", back_populates="session")
    saved_queries = relationship("SavedQuery", back_populates="session")

class InvestigationBookmark(Base):
    """
    Marks a specific entity or search result for later reference within a session.
    """
    __tablename__ = "investigation_bookmarks"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("investigation_sessions.id"), nullable=False)
    tenant_id = Column(String, index=True, nullable=False)

    # The target of the bookmark
    entity_type = Column(String, nullable=False) # e.g., 'CVE', 'Repository', 'Asset'
    entity_id = Column(String, nullable=False)
    label = Column(String, nullable=True)

    # Contextual metadata (where the user was when they bookmarked)
    context_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InvestigationSession", back_populates="bookmarks")

class SavedQuery(Base):
    """
    Persists a complex set of query parameters for reuse.
    """
    __tablename__ = "saved_queries"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("investigation_sessions.id"), nullable=True)
    tenant_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # The actual query logic (deterministic parameters)
    query_params = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("InvestigationSession", back_populates="saved_queries")

class SearchHistory(Base):
    """
    Audits and persists search terms for performance analysis and user convenience.
    """
    __tablename__ = "search_history"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)

    query_text = Column(String, nullable=False)
    query_type = Column(String, nullable=False) # 'text', 'entity', 'relationship', etc.
    result_count = Column(Integer, nullable=True)
    execution_time_ms = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

class TimelineMetadata(Base):
    """
    Stores markers or specific windows of interest within an entity's timeline.
    """
    __tablename__ = "timeline_metadata"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    entity_id = Column(String, index=True, nullable=False)
    entity_type = Column(String, nullable=False)

    marker_label = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CorrelationMetadata(Base):
    """
    Persists deterministic correlations identified between entities.
    """
    __tablename__ = "correlation_metadata"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)

    source_entity_id = Column(String, index=True, nullable=False)
    source_entity_type = Column(String, nullable=False)

    target_entity_id = Column(String, index=True, nullable=False)
    target_entity_type = Column(String, nullable=False)

    correlation_type = Column(String, nullable=False) # e.g., 'transitive_dependency', 'shared_owner'
    confidence_score = Column(Float, default=1.0) # Deterministic score based on relationship depth

    evidence = Column(JSON, nullable=True) # List of paths or relationships that prove the correlation
    created_at = Column(DateTime, default=datetime.utcnow)
