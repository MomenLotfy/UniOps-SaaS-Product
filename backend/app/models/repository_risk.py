from sqlalchemy import String, ForeignKey, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class RepositoryRiskScore(BaseModel):
    """
    Risk rating record for a repository, computed after each scan.
    One record per repo — upserted on every completed scan.

    risk_level: critical | high | medium | low
    risk_score: 0–100 (higher = more risk)
    trend:      worsening | stable | improving  (vs. previous rating)
    """
    __tablename__ = "repository_risk_scores"

    tenant_id:          Mapped[str]        = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    repo_id:            Mapped[str]        = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    scan_id:            Mapped[str | None] = mapped_column(String(36), nullable=True)

    # ── Risk rating ──────────────────────────────────────────────────────────
    risk_level:         Mapped[str]        = mapped_column(String(20), nullable=False, default="low")
    risk_score:         Mapped[float]      = mapped_column(Float, nullable=False, default=0.0)

    # ── Trend vs. previous scan ───────────────────────────────────────────────
    trend:              Mapped[str]        = mapped_column(String(20), nullable=False, default="stable")
    previous_risk_level:Mapped[str | None] = mapped_column(String(20), nullable=True)
    previous_risk_score:Mapped[float|None] = mapped_column(Float, nullable=True)

    # ── Factor counts ─────────────────────────────────────────────────────────
    critical_count:     Mapped[int]        = mapped_column(Integer, default=0)
    high_count:         Mapped[int]        = mapped_column(Integer, default=0)
    secret_count:       Mapped[int]        = mapped_column(Integer, default=0)
    container_count:    Mapped[int]        = mapped_column(Integer, default=0)
    compliance_violations: Mapped[int]     = mapped_column(Integer, default=0)
    open_findings:      Mapped[int]        = mapped_column(Integer, default=0)
    exposure_risk:      Mapped[float]      = mapped_column(Float, default=0.0)

    # ── Derived from scan / repo metadata ────────────────────────────────────
    security_score:     Mapped[float|None] = mapped_column(Float, nullable=True)
    owner:              Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Detailed factor breakdown (for UI tooltip / drill-down) ───────────────
    factors:            Mapped[dict]       = mapped_column(JSON, default=dict)
