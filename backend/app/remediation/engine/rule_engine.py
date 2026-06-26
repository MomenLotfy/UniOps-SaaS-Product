from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from app.remediation.engine.classification.categories import FindingCategory
from app.remediation.engine.detection.tech_types import Technology
from app.utils.logger import logger

class PlanningRule(BaseModel):
    """A deterministic rule for mapping findings to capabilities and strategies."""
    id: str
    priority: int
    condition: Dict[str, Any] # e.g. {"category": "dependency_vulnerability", "tech": "nodejs"}
    result_capability: str
    result_strategy: Optional[str] = None
    requires_approval: bool = False
    priority_override: Optional[str] = None

class RuleEngine:
    """
    Deterministic rule evaluator for the Decision Engine.
    Evaluates a set of configured rules to determine the remediation path.
    """
    def __init__(self):
        # In production, these would be loaded from a configuration file or database.
        self.rules: List[PlanningRule] = self._load_default_rules()

    def _load_default_rules(self) -> List[PlanningRule]:
        return [
            PlanningRule(
                id="RULE-001",
                priority=10,
                condition={"category": FindingCategory.DEPENDENCY_VULNERABILITY.value, "tech": Technology.NODEJS.value},
                result_capability="DependencyUpgrade",
                result_strategy="npm_audit_fix",
                requires_approval=False,
                priority_override="high"
            ),
            PlanningRule(
                id="RULE-002",
                priority=20,
                condition={"category": FindingCategory.DOCKERFILE_MISCONFIG.value},
                result_capability="DockerImageHardening",
                result_strategy="multi_stage_build",
                requires_approval=True,
                priority_override="medium"
            ),
            PlanningRule(
                id="RULE-003",
                priority=5,
                condition={"category": FindingCategory.SECRETS_EXPOSURE.value},
                result_capability="SecretRotation",
                result_strategy="vault_migration",
                requires_approval=True,
                priority_override="critical"
            ),
        ]

    async def evaluate(self, category: str, tech: str) -> Optional[Tuple[str, Optional[str], bool, Optional[str]]]:
        """
        Evaluates rules and returns the best match.
        Returns: (capability_id, strategy_id, requires_approval, priority)
        """
        # Sort rules by priority (lowest number = highest priority)
        sorted_rules = sorted(self.rules, key=lambda x: x.priority)

        for rule in sorted_rules:
            match = True
            if "category" in rule.condition and rule.condition["category"] != category:
                match = False
            if "tech" in rule.condition and rule.condition["tech"] != tech:
                match = False

            if match:
                logger.info(f"[RuleEngine] Rule {rule.id} matched for {category}/{tech}")
                return (rule.result_capability, rule.result_strategy, rule.requires_approval, rule.priority_override)

        return None
