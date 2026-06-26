from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class EnrichedFindingModel(BaseModel):
    """
    Persistence for an enriched security finding.
    """
    __tablename__ = "intelligence_enriched_findings"

    finding_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    # Intelligence Snapshot
    canonical_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Risk and Confidence
    risk_score: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    trust_score: Mapped[float] = mapped_column(Float)

    # Enrichment Metadata
    enrichment_metadata: Mapped[dict] = mapped_column(JSON, default=dict) # patches, recommendations, timeline
    business_context: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class EnrichmentAudit(BaseModel):
    """
    Audit log for enrichment pipeline executions.
    """
    __tablename__ = "intelligence_enrichment_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(100), index=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    trust_score: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
