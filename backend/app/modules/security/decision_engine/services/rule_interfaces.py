from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Tuple, List, Optional
from dataclasses import dataclass

@dataclass
class RuleEvaluationResult:
    """
    The deterministic result of a single rule evaluation.
    """
    rule_id: str
    is_matched: bool
    result_value: Optional[Any] = None
    execution_time_ms: float = 0.0
    evidence: Optional[str] = None

class IRuleEngine(ABC):
    """
    Interface for the Deterministic Rule Engine.
    """
    @abstractmethod
    async def evaluate(self, context: Any) -> Tuple[str, List[Any], List[Any]]:
        """
        Evaluates the provided context against all active rules.
        Returns: (final_result, matched_plans, matched_reasons)
        """
        pass

class IRuleRepository(ABC):
    """
    Interface for rule persistence and retrieval.
    """
    @abstractmethod
    async def get_active_rules(self, tenant_id: str) -> List[Any]:
        pass

    @abstractmethod
    async def get_rule_by_id(self, rule_id: str, tenant_id: str) -> Optional[Any]:
        pass
