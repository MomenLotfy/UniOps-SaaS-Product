from sqlalchemy import String, ForeignKey, Float, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class MLPattern(BaseModel):
    __tablename__ = "ml_patterns"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    frequency: Mapped[str | None] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
