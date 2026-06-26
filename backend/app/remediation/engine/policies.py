from enum import Enum
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field

class ExecutionPolicyType(str, Enum):
    """Types of constraints that can be applied to remediation execution."""
    AUTO_EXECUTE = "auto_execute"
    MANUAL_APPROVAL = "manual_approval"
    SECURITY_MANAGER_APPROVAL = "security_manager_approval"
    BUSINESS_APPROVAL = "business_approval"
    MAINTENANCE_WINDOW = "maintenance_window"
    PRODUCTION_FREEZE = "production_freeze"
    EMERGENCY_OVERRIDE = "emergency_override"

class ExecutionPolicy(BaseModel):
    """
    Defines the constraints and requirements for executing a remediation.
    This is a metadata layer that the Decision Engine and Execution Pipeline use
    to determine IF and WHEN a plan can be executed.
    """
    policy_id: str
    policy_type: ExecutionPolicyType
    description: str

    # Parameters for the policy (e.g. window start/end, required roles)
    parameters: Dict[str, Any] = {}

    # Priority of the policy (lower number = higher priority)
    priority: int = 100

    # Whether this policy can be bypassed in an emergency
    bypassable: bool = False
    bypass_role: Optional[str] = "super_admin"

class PolicyEvaluation(BaseModel):
    """The result of evaluating a policy against a plan."""
    policy_id: str
    is_allowed: bool
    reason: str
    required_action: Optional[str] = None # e.g. 'WAIT_FOR_WINDOW', 'REQUEST_APPROVAL'
    override_available: bool = False
