from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ApiKey(BaseModel):
    __tablename__ = "api_keys"

    tenant_id: Mapped[str]   = mapped_column(String(36), nullable=False, index=True)
    user_id:   Mapped[str]   = mapped_column(String(36), nullable=False, index=True)
    name:      Mapped[str]   = mapped_column(String(100), nullable=False)
    key_hash:  Mapped[str]   = mapped_column(String(128), nullable=False, unique=True)
    key_prefix: Mapped[str]  = mapped_column(String(25),  nullable=False)
    scopes:    Mapped[list]  = mapped_column(JSON, default=list)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool]  = mapped_column(Boolean, default=True)
