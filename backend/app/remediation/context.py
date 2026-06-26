from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ExecutionContext(BaseModel):
    """
    Immutable context passed through the entire remediation pipeline.
    Contains all state necessary for the decision engine and execution plugins.
    """
    # ── Identity & Traceability ─────────────────────────────────────────────────
    execution_id: str
    correlation_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ── Target Entity ───────────────────────────────────────────────────────────
    repository_id: str
    finding_id: str
    scan_id: Optional[str] = None

    # ── Security State ───────────────────────────────────────────────────────────
    risk_score: float = 0.0
    severity: str = "medium"
    policy_state: Dict[str, Any] = {} # Current policy settings for this tenant
    compliance_frameworks: list[str] = []
    sbom_snapshot_id: Optional[str] = None

    # ── Metadata ─────────────────────────────────────────────────────────────────
    repo_metadata: Dict[str, Any] = {} # e.g. language, stars, owner
    tenant_metadata: Dict[str, Any] = {}

    # ── Intent ───────────────────────────────────────────────────────────────────
    requested_action: str # e.g. 'auto_fix', 'propose_only'
    execution_options: Dict[str, Any] = {} # e.g. {'dry_run': True, 'force': False}
    validation_options: Dict[str, Any] = {}

    # ── AI Guidance ──────────────────────────────────────────────────────────────
    ai_recommendation: Optional[str] = None
    ai_confidence_score: float = 0.0
    ai_suggested_strategy: Optional[str] = None

    class Config:
        frozen = True # Ensure immutability
