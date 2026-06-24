from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SecurityPostureScore(BaseModel):
    __tablename__ = "security_posture_scores"

    tenant_id:          Mapped[str]   = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    overall_score:      Mapped[float] = mapped_column(Float, default=0.0)
    threat_score:       Mapped[float] = mapped_column(Float, default=0.0)
    vulnerability_score:Mapped[float] = mapped_column(Float, default=0.0)
    compliance_score:   Mapped[float] = mapped_column(Float, default=0.0)
    asset_score:        Mapped[float] = mapped_column(Float, default=0.0)
    policy_score:       Mapped[float] = mapped_column(Float, default=0.0)
    breakdown:          Mapped[dict]  = mapped_column(JSON, default=dict)
    trend:              Mapped[str]   = mapped_column(String(20), default="stable")
    recorded_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
