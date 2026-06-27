from __future__ import annotations
from sqlalchemy import String, ForeignKey, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import DecisionBase
from ..constants import DecisionState

class DecisionStatistics(DecisionBase):
    """
    Aggregated metrics for decision pipeline performance and outcomes.
    """
    __tablename__ = "security_decision_statistics"

    state: Mapped[DecisionState] = mapped_column(String(50), index=True) # e.g. READY, REJECTED
    count: Mapped[int] = mapped_column(Integer, default=0)
    avg_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)

    # Note: This model doesn't strictly need a correlation_id as it's aggregated,
    # but we inherit DecisionBase for consistency in the metadata/tenant_id pattern.
