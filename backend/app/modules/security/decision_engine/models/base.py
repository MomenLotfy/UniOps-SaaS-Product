from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class DecisionBase(BaseModel):
    """
    Mixin providing mandatory common fields for all Decision Engine models.
    Inherits from BaseModel for UUID id, created_at, and updated_at.
    """
    __abstract__ = True
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # We reuse BaseModel's created_at and updated_at
