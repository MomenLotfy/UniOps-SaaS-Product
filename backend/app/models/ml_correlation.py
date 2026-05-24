from sqlalchemy import String, ForeignKey, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class MLCorrelation(BaseModel):
    __tablename__ = "ml_correlations"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    metric_a: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_b: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_score: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(50), default="pearson")
    insight: Mapped[str | None] = mapped_column(String(1000))
    data_points: Mapped[dict] = mapped_column(JSON, default=dict)
