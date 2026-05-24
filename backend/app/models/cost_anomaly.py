from datetime import date
from sqlalchemy import String, ForeignKey, Float, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CostAnomaly(BaseModel):
    __tablename__ = "cost_anomalies"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    service: Mapped[str] = mapped_column(String(255))
    expected_cost: Mapped[float] = mapped_column(Float)
    actual_cost: Mapped[float] = mapped_column(Float)
    deviation: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="open")
    detected_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
