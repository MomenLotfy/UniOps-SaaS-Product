from sqlalchemy import String, ForeignKey, Float, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Savings(BaseModel):
    __tablename__ = "savings"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    potential_savings: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    effort: Mapped[str] = mapped_column(String(50), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    resource: Mapped[str | None] = mapped_column(String(500))
    recommendation: Mapped[str | None] = mapped_column(Text)
