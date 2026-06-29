from __future__ import annotations
from sqlalchemy import Enum as SAEnum, Float, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import DecisionBase
from ..constants import DecisionState

class DecisionStatistics(DecisionBase):
    """
    Aggregated metrics for decision pipeline performance and outcomes.

    Sprint 2 R21: ``state`` is now an SAEnum of DecisionState (was String(50)).
    Sprint 2 R20: unique constraint on (tenant_id, state) prevents
    duplicate-bucket inserts from concurrent writers (requires SELECT … FOR UPDATE
    on the hot path; provided by DecisionStatisticsService).
    """
    __tablename__ = "security_decision_statistics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "state", name="uq_decision_statistics_tenant_state"),
    )

    state: Mapped[DecisionState] = mapped_column(
        SAEnum(DecisionState, name="decision_statistics_state_enum"),
        index=True,
        nullable=False,
    )
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Note: This model doesn't strictly need a correlation_id as it's aggregated,
    # but we inherit DecisionBase for consistency in the metadata/tenant_id pattern.
