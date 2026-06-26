from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class RiskAssessment(BaseModel):
    """
    Persistence for a specific finding's risk evaluation.
    """
    __tablename__ = "risk_assessments"

    finding_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    # Detailed scores
    technical_score: Mapped[float] = mapped_column(Float)
    business_score: Mapped[float] = mapped_column(Float)
    environmental_score: Mapped[float] = mapped_column(Float)
    operational_score: Mapped[float] = mapped_column(Float)
    compliance_score: Mapped[float] = mapped_column(Float)

    # Final Outcome
    overall_score: Mapped[float] = mapped_column(Float)
    priority: Mapped[str] = mapped_column(String(50)) # critical, high, medium, low

    # Metadata
    confidence_score: Mapped[float] = mapped_column(Float)
    calculation_version: Mapped[str] = mapped_column(String(50))
    calculation_metadata: Mapped[dict] = mapped_column(JSON, default=dict) # Rules triggered, etc.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class RepositoryRiskProfile(BaseModel):
    """
    Aggregated risk profile for a repository.
    """
    __tablename__ = "repository_risk_profiles"

    repository_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)

    overall_score: Mapped[float] = mapped_column(Float)
    priority_level: Mapped[str] = mapped_column(String(50))
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)

    last_calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class AssetRiskProfile(BaseModel):
    """
    Risk profile for a specific asset (e.g. Kubernetes Namespace).
    """
    __tablename__ = "asset_risk_profiles"

    asset_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    asset_type: Mapped[str] = mapped_column(String(100)) # cluster, namespace, service

    risk_score: Mapped[float] = mapped_column(Float)
    priority_level: Mapped[str] = mapped_column(String(50))

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class RiskCalculationAudit(BaseModel):
    """
    Audit log of risk calculation events for transparency and debugging.
    """
    __tablename__ = "risk_calculation_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(100), index=True)

    input_snapshot: Mapped[dict] = mapped_column(JSON) # EnrichedFinding snapshot
    output_snapshot: Mapped[dict] = mapped_column(JSON) # Final RiskAssessment snapshot

    duration_ms: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
