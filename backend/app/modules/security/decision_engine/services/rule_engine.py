from __future__ import annotations
from typing import Any, Tuple, List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.rules import DecisionRule, RuleCondition, RuleAction, RuleOperator, RuleLogic
from .rule_interfaces import IRuleEngine, IRuleRepository, RuleEvaluationResult

class RuleEvaluator:
    """
    Handles the atomic evaluation of a single RuleCondition.
    """
    def evaluate_condition(self, condition: RuleCondition, context_data: dict) -> bool:
        # Handle nested conditions first (Recursive AND/OR/NOT)
        if condition.children:
            results = [self.evaluate_condition(child, context_data) for child in condition.children]
            if condition.logic == RuleLogic.AND:
                return all(results)
            if condition.logic == RuleLogic.OR:
                return any(results)
            if condition.logic == RuleLogic.NOT:
                return not results[0] if results else False
            return False

        # Leaf condition: Evaluate expression
        if not condition.field_path or not condition.operator:
            return False

        try:
            # Resolve field value from context (e.g. 'risk.overall_score')
            value = context_data
            for part in condition.field_path.split('.'):
                value = value.get(part, {}) if isinstance(value, dict) else None

            if value is None:
                return condition.operator == RuleOperator.NOT_EXISTS

            expected = condition.expected_value

            # Deterministic Operator Mapping
            if condition.operator == RuleOperator.EQUALS:
                return str(value) == str(expected)
            if condition.operator == RuleOperator.NOT_EQUALS:
                return str(value) != str(expected)
            if condition.operator == RuleOperator.GREATER_THAN:
                return float(value) > float(expected)
            if condition.operator == RuleOperator.LESS_THAN:
                return float(value) < float(expected)
            if condition.operator == RuleOperator.GREATER_THAN_OR_EQUAL:
                return float(value) >= float(expected)
            if condition.operator == RuleOperator.LESS_THAN_OR_EQUAL:
                return float(value) <= float(expected)
            if condition.operator == RuleOperator.CONTAINS:
                return str(expected) in str(value)
            if condition.operator == RuleOperator.IN:
                return str(value) in [v.strip() for v in str(expected).split(',')]
            if condition.operator == RuleOperator.EXISTS:
                return True

            return False
        except (ValueError, TypeError):
            return False

class RuleEngine(IRuleEngine):
    """
    The production-grade Deterministic Rule Engine.
    """
    def __init__(self, db: AsyncSession, repository: IRuleRepository):
        self.db = db
        self.repository = repository
        self.evaluator = RuleEvaluator()

    async def evaluate(self, context: Any) -> Tuple[str, List[Any], List[Any]]:
        """
        Evaluates the DecisionContext against active rules.
        """
        tenant_id = context.tenant_id
        context_data = context.raw_data

        # 1. Load active rules for the tenant
        rules = await self.repository.get_active_rules(tenant_id)

        # 2. Sort by priority (Lower = Higher) and eval_order
        rules.sort(key=lambda r: (r.priority, r.eval_order))

        matched_reasons = []
        final_result = "MONITOR" # Default fallback
        plans = []

        for rule in rules:
            # Evaluate conditions
            is_match = self.evaluator.evaluate_condition(rule.conditions[0], context_data) if rule.conditions else False

            if is_match:
                # Apply rule actions
                for action in rule.actions:
                    if action.action_type == "SET_RESULT":
                        final_result = action.action_value
                    elif action.action_type == "ADD_REASON":
                        matched_reasons.append({
                            "code": action.action_value,
                            "description": f"Matched rule: {rule.name}"
                        })

                # Handle short-circuiting
                if rule.short_circuit:
                    break

        # In a real implementation, we'd map 'final_result' to a DecisionPlan here.
        # For the foundation, we return the result and reasons.
        return final_result, [], matched_reasons
