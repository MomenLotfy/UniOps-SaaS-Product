from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SecurityTicket(BaseModel):
    """
    A ticket (Jira / Linear / Azure DevOps) linked to a security finding.
    """
    __tablename__ = "security_tickets"

    tenant_id:    Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    created_by:   Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # What finding this ticket is for
    entity_type:  Mapped[str]      = mapped_column(String(50), nullable=False, index=True)  # threat | vulnerability | asset | repo
    entity_id:    Mapped[str]      = mapped_column(String(36), nullable=False, index=True)

    # Ticket provider
    provider:     Mapped[str]      = mapped_column(String(50), nullable=False, index=True)  # jira | linear | azure_devops

    # External ticket identifiers
    external_id:  Mapped[str | None]  = mapped_column(String(255))   # Jira issueId, Linear issueId, ADO id
    ticket_key:   Mapped[str | None]  = mapped_column(String(100))   # Jira KEY-123, Linear ENG-456
    ticket_url:   Mapped[str | None]  = mapped_column(Text)
    ticket_title: Mapped[str | None]  = mapped_column(String(500))

    # Status mirrored from provider
    ticket_status: Mapped[str] = mapped_column(String(100), default="open")
    assignee:      Mapped[str | None] = mapped_column(String(255))
    priority:      Mapped[str | None] = mapped_column(String(50))

    # Linked vs created
    link_type:     Mapped[str] = mapped_column(String(20), default="created")  # created | linked

    # Last time we fetched status from provider
    synced_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Raw provider response cached
    provider_meta: Mapped[dict] = mapped_column(JSON, default=dict)
