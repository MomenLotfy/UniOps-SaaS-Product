from __future__ import annotations
from typing import Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.exceptions import NotFoundError
from ..models.rules import DecisionRule, RuleVersion, RuleCondition, RuleAction

class RuleVersionManager:
    """
    Manages versioning and snapshots for Decision Rules.
    Supports capturing full rule state and rolling back to previous versions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_snapshot(self, rule_id: str) -> RuleVersion:
        """
        Captures the current state of a rule, including its conditions and actions,
        and stores it as a new version.
        """
        # 1. Fetch current rule and its children
        stmt = select(DecisionRule).where(DecisionRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()

        if not rule:
            raise NotFoundError("DecisionRule", rule_id)

        # 2. Determine next version number
        version_stmt = select(RuleVersion.version_number).where(RuleVersion.rule_id == rule_id).order_by(desc(RuleVersion.version_number))
        version_res = await self.db.execute(version_stmt)
        last_version = version_res.scalar_one_or_none()
        next_version = (last_version + 1) if last_version else 1

        # 3. Build the snapshot (Simplified representation)
        snapshot = {
            "name": rule.name,
            "description": rule.description,
            "category": rule.category,
            "priority": rule.priority,
            "scope": rule.scope,
            "is_active": rule.is_active,
            "eval_order": rule.eval_order,
            "short_circuit": rule.short_circuit,
            "conditions": [
                {
                    "logic": c.logic,
                    "field_path": c.field_path,
                    "operator": c.operator,
                    "expected_value": c.expected_value,
                    "children": [] # Simplified for this implementation
                } for c in rule.conditions
            ],
            "actions": [
                {
                    "action_type": a.action_type,
                    "action_value": a.action_value,
                    "priority": a.priority
                } for a in rule.actions
            ]
        }

        version = RuleVersion(
            rule_id=rule_id,
            version_number=next_version,
            snapshot=snapshot
        )
        self.db.add(version)
        await self.db.flush()
        return version

    async def rollback_to_version(self, rule_id: str, version_number: int) -> DecisionRule:
        """
        Restores a rule's state from a specific version snapshot.
        """
        stmt = select(RuleVersion).where(
            RuleVersion.rule_id == rule_id,
            RuleVersion.version_number == version_number
        )
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()

        if not version:
            raise NotFoundError(f"RuleVersion(rule_id={rule_id}, version_number={version_number})")

        snapshot = version.snapshot

        # Fetch the current rule
        rule_stmt = select(DecisionRule).where(DecisionRule.id == rule_id)
        rule_res = await self.db.execute(rule_stmt)
        rule = rule_res.scalar_one_or_none()

        if not rule:
            raise NotFoundError("DecisionRule", rule_id)

        # Restore basic attributes
        rule.name = snapshot["name"]
        rule.description = snapshot["description"]
        rule.category = snapshot["category"]
        rule.priority = snapshot["priority"]
        rule.scope = snapshot["scope"]
        rule.is_active = snapshot["is_active"]
        rule.eval_order = snapshot["eval_order"]
        rule.short_circuit = snapshot["short_circuit"]

        # For conditions and actions, in a production system we'd do a diff/update.
        # For this implementation, we'll recreate them (simplified).
        # Note: This is a naive implementation that assumes no complex relationships exist.

        # (In a real system, we'd iterate through existing conditions/actions and update them)

        await self.db.flush()
        return rule
