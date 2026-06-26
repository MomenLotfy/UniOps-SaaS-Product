from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class CopilotConversation(BaseModel):
    """
    A security investigation session.
    Conversations are isolated per tenant and owned by a specific user.
    """
    __tablename__ = "copilot_conversations"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id:   Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    title:     Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict) # e.g. starting_context, tags

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class CopilotMessage(BaseModel):
    """
    A single interaction within a Copilot conversation.
    Stores both the request and the AI's response, along with performance metrics.
    """
    __tablename__ = "copilot_messages"

    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    role:    Mapped[str] = mapped_column(String(20), nullable=False) # system | user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # AI Performance & Cost Tracking
    model:      Mapped[str | None] = mapped_column(String(100))
    token_usage: Mapped[int | None] = mapped_column(Integer)
    latency:     Mapped[float | None] = mapped_column(Float)

    # Context Snapshot: what the AI knew at the time of this specific message
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
