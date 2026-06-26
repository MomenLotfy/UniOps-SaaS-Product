from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

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
    finding_type: str
    target_technology: str
    capability_id: str
    strategy_id: str
    priority: str
    required_inputs: Dict[str, Any] = {}
    expected_outputs: List[str] = []
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

    async def validate(self, context: RemediationContext) -> bool:
        """Check if the strategy is applicable to the current context."""
        pass

    async def execute(self, context: RemediationContext, plan: ExecutionPlan) -> Any:
        """The actual execution logic (to be implemented by specific strategies)."""
        pass

    async def get_required_inputs(self, context: RemediationContext) -> Dict[str, Any]:
        """Returns the parameters needed to execute this strategy."""
        pass

    @property
    def expected_outputs(self) -> List[str]:
        """What this strategy promises to deliver (e.g. 'updated_dockerfile', 'pr_link')."""
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
