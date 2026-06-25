from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class RepositoryRiskHistory(BaseModel):
    """
    Point-in-time snapshot of a repository's risk score.
    Written on every completed scan so we can draw per-repo trend lines.
    """
    __tablename__ = "repository_risk_history"

    tenant_id:  Mapped[str]   = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    repo_id:    Mapped[str]   = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id:    Mapped[str | None] = mapped_column(String(36), nullable=True)
    repo_name:  Mapped[str | None] = mapped_column(String(500), nullable=True)
    risk_level: Mapped[str]   = mapped_column(String(20), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    security_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
