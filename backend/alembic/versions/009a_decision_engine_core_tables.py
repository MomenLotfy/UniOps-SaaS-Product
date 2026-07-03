"""Create decision engine core tables (bridge migration).

Revision ID: 009a_decision_engine_core_tables
Revises: 009_detected_by
Create Date: 2026-07-02

Creates all 22 tables required by the decision_engine module before
migration 010 (and later 011-014) adds FK constraints that reference
security_decisions and security_decision_plans.

PATTERN: The same sa.Enum Python object instance is reused across all
tables that share a given enum type. SQLAlchemy tracks the first-use
internally and emits CREATE TYPE only once (same pattern as migration 010
with strategy_type_enum / strategy_state_enum). DO NOT call op.execute()
to pre-create the types; let SQLAlchemy manage it.

Table creation order respects FK dependencies:
  Layer 0: security_decision_contexts, security_decision_policies, security_rules
  Layer 1: metadata/child tables FK -> Layer 0, plus security_decisions
  Layer 2: tables FK -> security_decisions
  Layer 3: tables FK -> Layer 2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "009a_decision_engine_core_tables"
down_revision = "009_detected_by"
branch_labels = None
depends_on = None


def _base_cols() -> list:
    """Return the standard DecisionBase column set (id, timestamps, tenant, etc.)."""
    return [
        sa.Column("id",             sa.String(36),  primary_key=True, nullable=False),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id",      sa.String(36),  nullable=False, index=True),
        sa.Column("version",        sa.Integer,     nullable=True, server_default="1"),
        sa.Column("correlation_id", sa.String(36),  nullable=False, index=True),
        sa.Column("trace_id",       sa.String(100), nullable=True,  index=True),
        sa.Column("metadata_json",  JSONB,          nullable=True),
    ]


def upgrade() -> None:
    # ── Enum type definitions ─────────────────────────────────────────────────
    # IMPORTANT: Use the SAME Python object instance for every table that
    # references a given enum. SQLAlchemy only emits CREATE TYPE on first use;
    # reusing the same object prevents DuplicateObjectError (mirrors how
    # migration 010 handles strategy_type_enum / strategy_state_enum).
    decision_state = sa.Enum(
        "CREATED", "CONTEXT_BUILDING", "VALIDATING", "READY", "REJECTED", "ARCHIVED",
        name="decisionstate",
    )
    policy_status = sa.Enum(
        "DRAFT", "ACTIVE", "DEPRECATED", "ARCHIVED",
        name="policystatus",
    )
    rule_operator = sa.Enum(
        "EQUALS", "NOT_EQUALS", "GT", "LT", "GTE", "LTE",
        "CONTAINS", "IN", "EXISTS", "NOT_EXISTS",
        name="ruleoperator",
    )
    rule_logic = sa.Enum("AND", "OR", "NOT", name="rulelogic")

    # ── Layer 0: tables with no inbound FKs from this module ─────────────────

    op.create_table(
        "security_decision_contexts",
        *_base_cols(),
        sa.Column("source_finding_id", sa.String(100), nullable=False, index=True),
        sa.Column("raw_data",          JSONB,          nullable=False),
    )

    # policy_status emitted here for the first time -> CREATE TYPE policystatus
    op.create_table(
        "security_decision_policies",
        *_base_cols(),
        sa.Column("name",         sa.String(255),  nullable=False),
        sa.Column("description",  sa.String(1000), nullable=True),
        sa.Column("category",     sa.String(100),  nullable=True, index=True),
        sa.Column("priority",     sa.Integer,      nullable=True, server_default="100", index=True),
        sa.Column("status",       policy_status,   nullable=True),
        sa.Column("scope",        JSONB,            nullable=False),
        sa.Column("is_builtin",   sa.Boolean,      nullable=True),
        sa.Column("is_mandatory", sa.Boolean,      nullable=True),
    )

    op.create_table(
        "security_rules",
        *_base_cols(),
        sa.Column("name",          sa.String(255),  nullable=False),
        sa.Column("description",   sa.String(1000), nullable=True),
        sa.Column("category",      sa.String(100),  nullable=True, index=True),
        sa.Column("priority",      sa.Integer,      nullable=True, server_default="100", index=True),
        sa.Column("scope",         sa.String(100),  nullable=True),
        sa.Column("is_active",     sa.Boolean,      nullable=True),
        sa.Column("eval_order",    sa.Integer,      nullable=True, server_default="0"),
        sa.Column("short_circuit", sa.Boolean,      nullable=True),
    )

    # ── Layer 1a: metadata -> contexts ────────────────────────────────────────

    op.create_table(
        "security_decision_metadata",
        *_base_cols(),
        sa.Column("context_id", sa.String(36),
                  sa.ForeignKey("security_decision_contexts.id"),
                  nullable=True, index=True),
        sa.Column("key",   sa.String(100),  nullable=False),
        sa.Column("value", sa.String(1000), nullable=True),
    )

    # ── Layer 1b: decisions -> contexts ───────────────────────────────────────
    # decision_state emitted here for the first time -> CREATE TYPE decisionstate

    op.create_table(
        "security_decisions",
        *_base_cols(),
        sa.Column("status",       decision_state, nullable=True, index=True),
        sa.Column("final_result", sa.String(100), nullable=True),
        sa.Column("context_id",   sa.String(36),
                  sa.ForeignKey("security_decision_contexts.id"),
                  nullable=True, index=True),
    )

    # ── Layer 1c: policy children ─────────────────────────────────────────────
    # policy_status reused (same object) -> no duplicate CREATE TYPE

    op.create_table(
        "security_decision_policy_versions",
        *_base_cols(),
        sa.Column("policy_id",       sa.String(36),
                  sa.ForeignKey("security_decision_policies.id"),
                  nullable=True, index=True),
        sa.Column("version_number",  sa.Integer, nullable=False),
        sa.Column("config_snapshot", JSONB,       nullable=False),
    )

    op.create_table(
        "security_decision_policy_evaluations",
        *_base_cols(),
        sa.Column("policy_id",       sa.String(36),
                  sa.ForeignKey("security_decision_policies.id"),
                  nullable=True, index=True),
        sa.Column("decision_id",     sa.String(36),  nullable=True, index=True),
        sa.Column("input_result",    sa.String(100), nullable=True),
        sa.Column("output_result",   sa.String(100), nullable=True),
        sa.Column("resolution_path", sa.String(1000), nullable=True),
    )

    op.create_table(
        "security_decision_policy_history",
        *_base_cols(),
        sa.Column("policy_id",      sa.String(36),
                  sa.ForeignKey("security_decision_policies.id"),
                  nullable=True, index=True),
        sa.Column("from_state",     sa.String(100),  nullable=True),
        sa.Column("to_state",       sa.String(100),  nullable=True),
        sa.Column("changed_by",     sa.String(100),  nullable=True),
        sa.Column("change_summary", sa.String(1000), nullable=True),
    )

    op.create_table(
        "security_decision_policy_statistics",
        *_base_cols(),
        sa.Column("policy_id",        sa.String(36),
                  sa.ForeignKey("security_decision_policies.id"),
                  nullable=True, index=True),
        sa.Column("match_count",      sa.Integer, nullable=True, server_default="0"),
        sa.Column("override_count",   sa.Integer, nullable=True, server_default="0"),
        sa.Column("avg_eval_time_ms", sa.Float,   nullable=True, server_default="0.0"),
    )

    # ── Layer 1d: rule children ───────────────────────────────────────────────
    # rule_logic and rule_operator emitted here -> CREATE TYPE rulelogic, ruleoperator

    op.create_table(
        "security_rule_conditions",
        *_base_cols(),
        sa.Column("rule_id",             sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
        sa.Column("parent_condition_id", sa.String(36),
                  sa.ForeignKey("security_rule_conditions.id"),
                  nullable=True, index=True),
        sa.Column("logic",               rule_logic,    nullable=True),
        sa.Column("field_path",          sa.String(255),  nullable=True),
        sa.Column("operator",            rule_operator, nullable=True),
        sa.Column("expected_value",      sa.String(1000), nullable=True),
    )

    op.create_table(
        "security_rule_actions",
        *_base_cols(),
        sa.Column("rule_id",      sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
        sa.Column("action_type",  sa.String(100),  nullable=False),
        sa.Column("action_value", sa.String(1000), nullable=False),
        sa.Column("priority",     sa.Integer,      nullable=True, server_default="0"),
    )

    op.create_table(
        "security_rule_versions",
        *_base_cols(),
        sa.Column("rule_id",        sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot",       JSONB,       nullable=False),
    )

    op.create_table(
        "security_rule_executions",
        *_base_cols(),
        sa.Column("rule_id",            sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
        sa.Column("decision_id",        sa.String(36), nullable=True, index=True),
        sa.Column("is_matched",         sa.Boolean,    nullable=False),
        sa.Column("evaluation_time_ms", sa.Float,      nullable=True),
        sa.Column("result_snapshot",    JSONB,          nullable=True),
    )

    op.create_table(
        "security_rule_dependencies",
        *_base_cols(),
        sa.Column("rule_id",            sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
        sa.Column("depends_on_rule_id", sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
    )

    op.create_table(
        "security_rule_statistics",
        *_base_cols(),
        sa.Column("rule_id",           sa.String(36),
                  sa.ForeignKey("security_rules.id"),
                  nullable=True, index=True),
        sa.Column("match_count",       sa.Integer, nullable=True, server_default="0"),
        sa.Column("total_evaluations", sa.Integer, nullable=True, server_default="0"),
        sa.Column("avg_latency_ms",    sa.Float,   nullable=True, server_default="0.0"),
        sa.Column("last_matched_at",   sa.DateTime(timezone=True), nullable=True),
    )

    # ── Layer 1e: decision_statistics ─────────────────────────────────────────
    # decision_state reused (same object) -> no duplicate CREATE TYPE

    op.create_table(
        "security_decision_statistics",
        *_base_cols(),
        sa.Column("state",           decision_state, nullable=False, index=True),
        sa.Column("count",           sa.Integer,     nullable=False, server_default="0"),
        sa.Column("avg_duration_ms", sa.Float,       nullable=False, server_default="0.0"),
        sa.UniqueConstraint("tenant_id", "state",
                            name="uq_decision_statistics_tenant_state"),
    )

    # ── Layer 2: tables that FK -> security_decisions ─────────────────────────
    # decision_state reused (same object) in history table -> no duplicate

    op.create_table(
        "security_decision_history",
        *_base_cols(),
        sa.Column("decision_id",   sa.String(36),
                  sa.ForeignKey("security_decisions.id"),
                  nullable=True, index=True),
        sa.Column("from_state",    decision_state,  nullable=True),
        sa.Column("to_state",      decision_state,  nullable=False),
        sa.Column("changed_by",    sa.String(100),  nullable=True),
        sa.Column("change_reason", sa.String(1000), nullable=True),
    )

    op.create_table(
        "security_decision_versions",
        *_base_cols(),
        sa.Column("decision_id",    sa.String(36),
                  sa.ForeignKey("security_decisions.id"),
                  nullable=True, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot",       JSONB,       nullable=False),
    )

    op.create_table(
        "security_decision_plans",
        *_base_cols(),
        sa.Column("decision_id",     sa.String(36),
                  sa.ForeignKey("security_decisions.id"),
                  nullable=True, index=True),
        sa.Column("execution_order", sa.Integer, nullable=True, server_default="1"),
    )

    op.create_table(
        "security_decision_reasons",
        *_base_cols(),
        sa.Column("decision_id",  sa.String(36),
                  sa.ForeignKey("security_decisions.id"),
                  nullable=True, index=True),
        sa.Column("reason_code",  sa.String(100),  nullable=False),
        sa.Column("description",  sa.String(1000), nullable=False),
    )

    op.create_table(
        "security_decision_constraints",
        *_base_cols(),
        sa.Column("decision_id",     sa.String(36),
                  sa.ForeignKey("security_decisions.id"),
                  nullable=True, index=True),
        sa.Column("constraint_type", sa.String(100), nullable=False),
        sa.Column("is_met",          sa.Boolean,     nullable=True),
    )

    # policy_status reused (same object) -> no duplicate CREATE TYPE
    op.create_table(
        "security_decision_policy_refs",
        *_base_cols(),
        sa.Column("decision_id",    sa.String(36),
                  sa.ForeignKey("security_decisions.id"),
                  nullable=True, index=True),
        sa.Column("policy_id",      sa.String(36),
                  sa.ForeignKey("security_decision_policies.id"),
                  nullable=True, index=True),
        sa.Column("policy_version", sa.Integer, nullable=False),
    )

    # ── Layer 3: FK -> Layer 2 ────────────────────────────────────────────────

    op.create_table(
        "security_decision_steps",
        *_base_cols(),
        sa.Column("plan_id",   sa.String(36),
                  sa.ForeignKey("security_decision_plans.id"),
                  nullable=True, index=True),
        sa.Column("step_type", sa.String(100),  nullable=False),
        sa.Column("result",    sa.String(1000), nullable=True),
    )

    op.create_table(
        "security_decision_evidence",
        *_base_cols(),
        sa.Column("reason_id",      sa.String(36),
                  sa.ForeignKey("security_decision_reasons.id"),
                  nullable=True, index=True),
        sa.Column("evidence_type",  sa.String(100),  nullable=False),
        sa.Column("evidence_value", sa.String(2000), nullable=False),
    )


def downgrade() -> None:
    # Drop in reverse FK order
    op.drop_table("security_decision_evidence")
    op.drop_table("security_decision_steps")
    op.drop_table("security_decision_policy_refs")
    op.drop_table("security_decision_constraints")
    op.drop_table("security_decision_reasons")
    op.drop_table("security_decision_plans")
    op.drop_table("security_decision_versions")
    op.drop_table("security_decision_history")
    op.drop_table("security_decision_statistics")
    op.drop_table("security_rule_statistics")
    op.drop_table("security_rule_dependencies")
    op.drop_table("security_rule_executions")
    op.drop_table("security_rule_versions")
    op.drop_table("security_rule_actions")
    op.drop_table("security_rule_conditions")
    op.drop_table("security_decision_policy_statistics")
    op.drop_table("security_decision_policy_history")
    op.drop_table("security_decision_policy_evaluations")
    op.drop_table("security_decision_policy_versions")
    op.drop_table("security_decisions")
    op.drop_table("security_decision_metadata")
    op.drop_table("security_decision_policies")
    op.drop_table("security_rules")
    op.drop_table("security_decision_contexts")

    op.execute("DROP TYPE IF EXISTS rulelogic")
    op.execute("DROP TYPE IF EXISTS ruleoperator")
    op.execute("DROP TYPE IF EXISTS policystatus")
    op.execute("DROP TYPE IF EXISTS decisionstate")
