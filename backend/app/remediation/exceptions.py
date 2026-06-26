from __future__ import annotations
from typing import Optional

class RemediationError(Exception):
    """Base exception for all remediation engine errors."""
    def __init__(self, message: str, tenant_id: Optional[str] = None, plan_id: Optional[str] = None):
        super().__init__(message)
        self.tenant_id = tenant_id
        self.plan_id = plan_id

class RemediationValidationError(RemediationError):
    """Raised when a plan or context fails validation."""
    pass

class CapabilityNotFoundError(RemediationError):
    """Raised when a required capability is not registered or available."""
    pass

class StrategyExecutionError(RemediationError):
    """Raised when a strategy execution fails."""
    pass

class LockAcquisitionError(RemediationError):
    """Raised when a required resource lock cannot be acquired."""
    pass

class StateTransitionError(RemediationError):
    """Raised when an illegal state transition is attempted."""
    pass

class PluginCompatibilityError(RemediationError):
    """Raised when a plugin is incompatible with the current engine version."""
    pass

class PolicyViolationError(RemediationError):
    """Raised when an execution policy is violated."""
    pass

class RollbackError(RemediationError):
    """Raised when a rollback operation fails."""
    pass

class RemediationTimeoutError(RemediationError):
    """Raised when an execution or stage times out."""
    pass
