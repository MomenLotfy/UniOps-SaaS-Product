from __future__ import annotations
from typing import List
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase

class DecisionContext(DecisionBase):
    """
    Aggregated state containing all information used to make the decision.
    """
    __tablename__ = "security_decision_contexts"

    source_finding_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # Link to Vulnerability/Threat
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False) # Full snapshot of context build

    # Relationships
    context_metadata: Mapped[List["DecisionMetadata"]] = relationship(back_populates="context")

class DecisionMetadata(DecisionBase):
    """
    Structured key-value metadata specific to the decision context.
    """
    __tablename__ = "security_decision_metadata"

    context_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_decision_contexts.id"), index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(1000))

    context: Mapped["DecisionContext"] = relationship(back_populates="context_metadata")
