from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum
from sqlalchemy import String, ForeignKey, JSON, DateTime, Integer, Boolean, Enum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import DecisionBase

class RuleOperator(str, PyEnum):
    """
    Deterministic operators for rule evaluation.
    """
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GT"
    LESS_THAN = "LT"
    GREATER_THAN_OR_EQUAL = "GTE"
    LESS_THAN_OR_EQUAL = "LTE"
    CONTAINS = "CONTAINS"
    IN = "IN"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"

class RuleLogic(str, PyEnum):
    """
    Boolean logic for combining conditions.
    """
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

class DecisionRule(DecisionBase):
    """
    A deterministic rule used to evaluate security findings.
    """
    __tablename__ = "security_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    category: Mapped[str] = mapped_column(String(100), index=True) # e.g. 'compliance', 'risk'
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True) # Lower = Higher Priority
    scope: Mapped[str] = mapped_column(String(100), default="global") # global, tenant, app
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Execution configuration
    eval_order: Mapped[int] = mapped_column(Integer, default=0)
    short_circuit: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    conditions: Mapped[List["RuleCondition"]] = relationship(back_populates="rule", cascade="all, delete-orphan")
    actions: Mapped[List["RuleAction"]] = relationship(back_populates="rule", cascade="all, delete-orphan")
    versions: Mapped[List["RuleVersion"]] = relationship(back_populates="rule")
    executions: Mapped[List["RuleExecution"]] = relationship(back_populates="rule")
    dependencies: Mapped[List["RuleDependency"]] = relationship(back_populates="rule", foreign_keys="RuleDependency.rule_id")

class RuleCondition(DecisionBase):
    """
    A logical condition within a rule. Supports nesting.
    """
    __tablename__ = "security_rule_conditions"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)
    parent_condition_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("security_rule_conditions.id"), index=True)

    logic: Mapped[RuleLogic] = mapped_column(Enum(RuleLogic), default=RuleLogic.AND)

    # Expression details
    field_path: Mapped[Optional[str]] = mapped_column(String(255)) # Path in DecisionContext.raw_data (e.g. 'risk.overall_score')
    operator: Mapped[Optional[RuleOperator]] = mapped_column(Enum(RuleOperator))
    expected_value: Mapped[Optional[str]] = mapped_column(String(1000)) # Serialized value

    rule: Mapped["DecisionRule"] = relationship(back_populates="conditions")
    children: Mapped[List["RuleCondition"]] = relationship()

class RuleAction(DecisionBase):
    """
    Deterministic outcome produced when a rule matches.
    """
    __tablename__ = "security_rule_actions"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'SET_RESULT', 'ADD_REASON'
    action_value: Mapped[str] = mapped_column(String(1000), nullable=False) # e.g. 'PATCH', 'SENSITIVE_DATA_EXPOSED'
    priority: Mapped[int] = mapped_column(Integer, default=0)

    rule: Mapped["DecisionRule"] = relationship(back_populates="actions")

class RuleVersion(DecisionBase):
    """
    Historical version of a rule definition.
    """
    __tablename__ = "security_rule_versions"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False) # Full rule state

    rule: Mapped["DecisionRule"] = relationship(back_populates="versions")

class RuleExecution(DecisionBase):
    """
    Audit of a specific rule evaluation.
    """
    __tablename__ = "security_rule_executions"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)
    decision_id: Mapped[str] = mapped_column(String(36), index=True)
    is_matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluation_time_ms: Mapped[float] = mapped_column(Float)
    result_snapshot: Mapped[dict] = mapped_column(JSON) # The context subset used for evaluation

    rule: Mapped["DecisionRule"] = relationship(back_populates="executions")

class RuleDependency(DecisionBase):
    """
    Inter-rule dependencies (Rule A must evaluate before Rule B).
    """
    __tablename__ = "security_rule_dependencies"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)
    depends_on_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)

    rule: Mapped["DecisionRule"] = relationship(back_populates="dependencies", foreign_keys=[rule_id])

class RuleStatistics(DecisionBase):
    """
    Aggregated metrics for rule performance.
    """
    __tablename__ = "security_rule_statistics"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_rules.id"), index=True)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    total_evaluations: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    last_matched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
