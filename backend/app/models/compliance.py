from sqlalchemy import String, ForeignKey, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Compliance(BaseModel):
    __tablename__ = "compliance"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    framework: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    details: Mapped[list] = mapped_column(JSON, default=list)
