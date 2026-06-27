from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Tuple, List, Optional
from dataclasses import dataclass

@dataclass
class PolicyResolution:
    """
    The result of the policy resolution process.
    """
    policy_id: str
    policy_name: str
    final_result: str
    resolution_path: str # Trace of how this policy was selected (e.g. Repo -> Tenant)
    overridden: bool = False
    reason: Optional[str] = None

class IPolicyEngine(ABC):
    """
    Interface for the Enterprise Policy Engine.
    """
    @abstractmethod
    async def apply_policy(
        self,
        context: Any,
        technical_result: str,
        reasons: List[Any]
    ) -> Tuple[str, List[Any], PolicyResolution]:
        """
        Transforms a technical rule result into an organizationally compliant decision.
        Returns: (adjusted_result, updated_reasons, resolution_meta)
        """
        pass

class IPolicyRepository(ABC):
    """
    Interface for policy persistence.
    """
    @abstractmethod
    async def resolve_effective_policy(self, tenant_id: str, scope_data: dict) -> Optional[Any]:
        """
        Traverses the hierarchy to find the most specific active policy.
        """
        pass
