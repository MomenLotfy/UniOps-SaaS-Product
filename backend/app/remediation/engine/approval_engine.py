from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ApprovalLevel(str, Enum):
    NONE = "none"
    LOW_RISK_AUTO = "low_risk_auto"
    SECURITY_MANAGER = "security_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    BUSINESS_OWNER = "business_owner"
    MANUAL_ONLY = "manual_only"

class ApprovalDecision(BaseModel):
    requires_approval: bool
    approval_role: Optional[ApprovalLevel] = None
    reason: str
    bypass_allowed: bool = False

class ApprovalEngine:
    """
    Determines if a remediation plan requires human intervention.
    Evaluates based on repository criticality, risk score, and tenant policies.
    """
    def __init__(self):
        # Thresholds for auto-approval
        self.risk_threshold = 4.0 # Any risk score > 4 requires approval
        self.critical_repo_identifiers = {"prod", "main", "core-api", "payments"}

    async def determine_approval(self, plan_metadata: Dict[str, Any], repo_metadata: Dict[str, Any]) -> ApprovalDecision:
        """
        Decision logic for approval requirements.
        """
        risk_score = plan_metadata.get("risk_score", 5.0)
        repo_name = repo_metadata.get("name", "").lower()
        is_production = repo_metadata.get("environment") == "production"

        # 1. Critical Production Repo -> Always requires Security Manager
        if is_production or any(crit in repo_name for crit in self.critical_repo_identifiers):
            return ApprovalDecision(
                requires_approval=True,
                approval_role=ApprovalLevel.SECURITY_MANAGER,
                reason="Action targeting a critical production repository."
            )

        # 2. High Risk Score -> Requires Approval
        if risk_score > self.risk_threshold:
            return ApprovalDecision(
                requires_approval=True,
                approval_role=ApprovalLevel.SECURITY_MANAGER,
                reason=f"Risk score {risk_score} exceeds auto-remediation threshold."
            )

        # 3. Low risk in non-prod -> Auto
        return ApprovalDecision(
            requires_approval=False,
            approval_role=ApprovalLevel.NONE,
            reason="Low risk finding in non-critical environment."
        )
