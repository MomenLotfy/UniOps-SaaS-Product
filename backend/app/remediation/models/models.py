from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON, DateTime, Float, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from app.remediation.lifecycle.state import RemediationState

class RemediationPlan(BaseModel):
    """
    The central entity for a remediation attempt.
    Now supports versioning for immutability and audit.
    """
    __tablename__ = "remediation_plans"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("remediation_plans.id"), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    change_reason: Mapped[Optional[str]] = mapped_column(String(500))

    # Decision Metadata
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_technology: Mapped[str] = mapped_column(String(100), nullable=False)
    capability_id: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)

    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[RemediationState] = mapped_column(Enum(RemediationState), default=RemediationState.CREATED)

    # Inputs/Outputs
    required_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_outputs: Mapped[list] = mapped_column(JSON, default=list)

    # Context Snapshot
    execution_context: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relationships
    steps: Mapped[List["RemediationStep"]] = relationship(back_populates="plan")
    state_history: Mapped[List["RemediationStateHistory"]] = relationship(back_populates="plan")
    events: Mapped[List["RemediationEventLog"]] = relationship(back_populates="plan")

class RemediationStep(BaseModel):
    """
    Granular steps within a plan execution (e.g. 'Validate Config' -> 'Apply Patch').
    """
    __tablename__ = "remediation_steps"

    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="pending") # pending | running | success | failed | skipped

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    scrape_result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_details: Mapped[Optional[str]] = mapped_column(String(2000))

    plan: Mapped["RemediationPlan"] = relationship(back_populates="steps")

class RemediationStateHistory(BaseModel):
    """
    Audit trail of all state transitions for a plan.
    """
    __tablename__ = "remediation_state_history"

    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    from_state: Mapped[RemediationState] = mapped_column(Enum(RemediationState))
    to_state: Mapped[RemediationState] = mapped_column(Enum(RemediationState))

    transition_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transitioned_by: Mapped[Optional[str]] = mapped_column(String(100)) # e.g. 'PlanningWorker'
    reason: Mapped[Optional[str]] = mapped_column(String(500))

    # Audit enrichment
    rule_ids: Mapped[list] = mapped_column(JSON, default=list)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100))
    execution_version: Mapped[Optional[int]] = mapped_column(Integer)

    plan: Mapped["RemediationPlan"] = relationship(back_populates="state_history")

class RemediationEventLog(BaseModel):
    """
    Persistence of all events flowing through the remediation event bus.
    """
    __tablename__ = "remediation_event_logs"

    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(10), default="1.0")

    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    plan: Mapped["RemediationPlan"] = relationship(back_populates="events")

class PluginMetadata(BaseModel):
    """
    Static registration data for remediation plugins.
    Includes compatibility and health metadata.
    """
    __tablename__ = "remediation_plugin_metadata"

    plugin_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(1000))

    # Compatibility layer
    min_engine_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    max_engine_version: Mapped[str] = mapped_column(String(20), nullable=True)
    required_apis: Mapped[list] = mapped_column(JSON, default=list)
    supported_features: Mapped[list] = mapped_column(JSON, default=list)

    supported_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)

    # Health & Status
    is_active: Mapped[bool] = mapped_column(default=True)
    health_status: Mapped[str] = mapped_column(String(50), default="healthy") # healthy | degraded | failing
    maintenance_mode: Mapped[bool] = mapped_column(default=False)
    deprecation_status: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class RemediationExecutionMetrics(BaseModel):
    """
    Aggregated runtime metrics for remediation performance.
    """
    __tablename__ = "remediation_execution_metrics"

    metric_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    value: Mapped[float] = mapped_column(Float)
    dimension: Mapped[dict] = mapped_column(JSON, default=dict) # e.g. {"capability": "DockerImageHardening"}

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class RemediationExecutionHistory(BaseModel):
    """
    Legacy refined: detailed log of execution attempts.
    """
    __tablename__ = "remediation_execution_history"

    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    latency: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000))

    # Version tracking
    planner_version: Mapped[Optional[str]] = mapped_column(String(50))
    capability_version: Mapped[Optional[str]] = mapped_column(String(50))
    strategy_version: Mapped[Optional[str]] = mapped_column(String(50))
    plugin_version: Mapped[Optional[str]] = mapped_column(String(50))
    engine_version: Mapped[Optional[str]] = mapped_column(String(50))

    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    token_usage: Mapped[Optional[int]] = mapped_column(Integer)

    result_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
