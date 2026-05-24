from datetime import datetime
from sqlalchemy import String, ForeignKey, Float, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class MLPrediction(BaseModel):
    __tablename__ = "ml_predictions"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), default="1.0.0")
    prediction_type: Mapped[str] = mapped_column(String(100))
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_accurate: Mapped[bool | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)
