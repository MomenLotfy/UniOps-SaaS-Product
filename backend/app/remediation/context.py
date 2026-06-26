from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ExecutionContext(BaseModel):
    """
    Immutable context passed through the entire remediation pipeline.
    Enhanced for full correlation propagation and version tracking.
    """
    # ── Traceability & Correlation ────────────────────────────────────────────────
    request_id: str
    correlation_id: str
    execution_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ── Versioning Metadata ───────────────────────────────────────────────────────
    planner_version: str = "1.0.0"
    capability_version: Optional[str] = None
    plugin_version: Optional[str] = None
    engine_version: str = "1.0.0"

    # ── Target Entity ────────────────────────────────────────────────────────S
    repository_id: str
    finding_id: str
    scan_id: Optional[str] = None

    # ── Security State ──────────────────────────────────────────────────────────
    risk_score: float = 0.0
    severity: str = "medium"
    policy_state: Dict[str, Any] = {}
    compliance_frameworks: list[str] = []
    sbom_snapshot_id: Optional[str] = None

    # ── Metadata ─────────────────────────────────────────────────────────────────
    repo_metadata: Dict[str, Any] = {}
    tenant_metadata: Dict[str, Any] = {}

    # ── Intent ───────────────────────────────────────────────────────────────────
    requested_action: str
    execution_options: Dict[str, Any] = {}
    validation_options: Dict[str, Any] = {}

    # ── AI Guidance ──────────────────────────────────────────────────────────────
    ai_recommendation: Optional[str] = None
    ai_confidence_score: float = 0.0
    ai_suggested_strategy: Optional[str] = None

    class Config:
        frozen = True
