from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class RemediationPlan(BaseModel):
    """
    A planned remediation action.
    Tracks the decision process from finding to execution strategy.
    """
    __tablename__ = "remediation_plans"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Decision Metadata
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'vulnerability'
    target_technology: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'docker'
    capability_id: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)

    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="draft") # draft | validated | executing | completed | failed

    # Inputs/Outputs
    required_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_outputs: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class RemediationExecutionHistory(BaseModel):
    """
    Detailed log of execution attempts for a plan.
    Used for observability and audit.
    """
    __tablename__ = "remediation_execution_history"

    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    latency: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False) # started | success | failed
    error_message: Mapped[str | None] = mapped_column(String(1000))

    # Telemetry
    model_used: Mapped[str | None] = mapped_column(String(100))
    token_usage: Mapped[int | None] = mapped_column(Integer)

    # Results
    result_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
