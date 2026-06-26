from __future__ import annotations
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from app.schemas.intelligence import EnrichedFinding

@dataclass
class RiskContext:
    """
    Carries the state of a risk evaluation process across the pipeline.
    """
    finding_id: str
    tenant_id: str
    enriched_finding: EnrichedFinding

    # Calculated Dimensional Scores (0.0 - 100.0)
    technical_score: float = 0.0
    business_score: float = 0.0
    environmental_score: float = 0.0
    operational_score: float = 0.0
    compliance_score: float = 0.0

    # Priority and Final Score
    overall_score: float = 0.0
    priority: str = "informational"

    # Confidence and Trust
    confidence: float = 0.0
    trust: float = 0.0

    # Metadata and audit trail
    metadata: Dict[str, Any] = field(default_factory=dict)
    triggered_rules: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)

    def add_rule_trigger(self, rule_id: str):
        self.triggered_rules.append(rule_id)

    def update_score(self, dimension: str, value: float):
        setattr(self, f"{dimension}_score", value)
