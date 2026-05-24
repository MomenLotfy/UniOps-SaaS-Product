from sqlalchemy import String, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Webhook(BaseModel):
    __tablename__ = "webhooks"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str | None] = mapped_column(String(255))
    events: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    last_response_code: Mapped[int | None] = mapped_column()
    failure_count: Mapped[int] = mapped_column(default=0)
