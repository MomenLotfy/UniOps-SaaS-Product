from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel

class RollbackStatus(str, Enum):
    """Rollback capability of a remediation strategy."""
    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    MANUAL = "manual"
    AUTOMATIC = "automatic"

class RemediationContext(BaseModel):
    """Context passed through the remediation pipeline."""
    tenant_id: str
    finding_id: str
    repo_id: str
    scan_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

class ExecutionPlan(BaseModel):
    """The output of the Decision Engine."""
    plan_id: str
    finding_id: str
    finding_type: str
    target_technology: str
    capability_id: str
    strategy_id: str
    priority: str
    risk_level: str = "medium"
    confidence_score: float = 0.0
    estimated_impact: str = "low"
    required_inputs: Dict[str, Any] = {}
    expected_outputs: List[str] = []
    approval_required: bool = False
    approval_role: Optional[str] = None
    rollback_available: bool = True
    rollback_status: RollbackStatus = RollbackStatus.AUTOMATIC
    validation_requirements: List[str] = []
    estimated_duration_seconds: int = 0
    human_summary: Optional[str] = None
    status: str = "draft" # draft | validated | executing | completed | failed

class IRemediationPlugin(ABC):
    """Interface for a remediation plugin."""

    @property
    def plugin_id(self) -> str:
        pass

    @property
    def name(self) -> str:
        pass

    @property
    def supported_capabilities(self) -> List[str]:
        """List of capability IDs this plugin provides."""
        pass

    @property
    def supported_technologies(self) -> Set[str]:
        """Technologies this plugin can handle (e.g. {'docker', 'terraform'})."""
        pass

    @property
    def supported_finding_types(self) -> Set[str]:
        """Finding categories this plugin can remediate (e.g. {'misconfiguration', 'vulnerability'})."""
        pass

    async def initialize(self) -> None:
        """Plugin setup logic."""
        pass

    async def get_strategy(self, strategy_id: str) -> Optional[IRemediationStrategy]:
        """Retrieve a specific strategy implementation by ID."""
        pass

class IRemediationStrategy(ABC):
    """Interface for a specific remediation strategy."""

    @property
    def strategy_id(self) -> str:
        pass

    @property
    def rollback_status(self) -> RollbackStatus:
        """Declares if and how this strategy supports rollback."""
        return RollbackStatus.UNSUPPORTED

    async def validate(self, context: RemediationContext) -> bool:
        """Check if the strategy is applicable to the current context."""
        pass

    async def execute(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """The actual execution logic (to be implemented by specific strategies)."""
        pass

    async def rollback(self, context: RemedيsationContext, plan: ExecutionPlan) -> Any:
        """Performs the rollback operation to revert changes made by execute()."""
        pass

    async def get_required_inputs(self, context: RemediationContext) -> Dict[str, Any]:
        """Returns the parameters needed to execute this strategy."""
        pass

    @property
    def expected_outputs(self) -> List[str]:
        """What this strategy promises to deliver."""
        pass

class ICapability(ABC):
    """Interface representing a remediation capability (e.g., 'SecretRotation')."""

    @property
    def capability_id(self) -> str:
        pass

    async def resolve_strategy(self, context: RemediationContext) -> IRemediationStrategy:
        """Determine the best strategy for the given context."""
        pass

class IRemediationValidator(ABC):
    """Interface for validating remediation plans or results."""

    async def validate(self, plan: ExecutionPlan, context: RemediationContext) -> bool:
        pass
