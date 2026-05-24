from datetime import date
from sqlalchemy import String, ForeignKey, Float, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CostMetric(BaseModel):
    __tablename__ = "cost_metrics"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    integration_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("integrations.id"))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    service: Mapped[str] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
