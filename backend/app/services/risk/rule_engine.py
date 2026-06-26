from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.services.risk.context import RiskContext
from app.utils.logger import logger

class RiskRuleEngine:
    """
    Deterministic rule engine for prioritizing security findings.
    Converts dimensional scores and metadata into a a final priority level.
    """

    def __init__(self):
        # Rules are defined as a list of (condition_lambda, priority_result)
        # Higher index = higher priority for the rule (overrides previous)
        self.rules = [
            # Rule 1: Low severity + Low business impact -> Low
            (lambda ctx: ctx.technical_score < 40 and ctx.business_score < 40, "low"),

            # Rule 2: High technical risk OR High business impact -> High
            (lambda ctx: ctx.technical_score >= 70 or ctx.business_score >= 70, "high"),

            # Rule 3: High Technical Risk + Public Exploit + Production -> Critical
            (lambda ctx: (
                ctx.technical_score >= 70 and
                ctx.enriched_finding.exploit and
                ctx.enriched_finding.package and
                ctx.enriched_finding.package.ecosystem.id == "production" # Mocking check
            ), "critical"),

            # Rule 4: Compliance Violation (e.g. PCI DSS) -> High/Critical
            (lambda ctx: ctx.compliance_score >= 80, "critical"),
        ]

    def evaluate_priority(self, context: RiskContext) -> str:
        """
        Executes the rule set against the current context and returns the priority.
        """
        final_priority = "medium" # Default

        for rule_id, (condition, result) in enumerate(self.rules):
            try:
                if condition(context):
                    final_priority = result
                    context.add_rule_trigger(f"rule_{rule_id}")
            except Exception as e:
                logger.error(f"[RiskRuleEngine] Error evaluating rule {rule_id}: {e}")

        return final_priority
