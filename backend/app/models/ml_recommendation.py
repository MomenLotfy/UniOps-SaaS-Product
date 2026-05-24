from sqlalchemy import String, ForeignKey, Float, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class MLRecommendation(BaseModel):
    __tablename__ = "ml_recommendations"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=5)
    confidence: Mapped[float] = mapped_column(Float)
    impact: Mapped[str] = mapped_column(String(50), default="medium")
    effort: Mapped[str] = mapped_column(String(50), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    action: Mapped[str | None] = mapped_column(Text)
