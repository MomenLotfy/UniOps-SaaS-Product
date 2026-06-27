"""Add decision approval tables (Module 0 / Part 5).

Revision ID: 011_decision_approval_tables
Revises: 010_decision_strategy_tables
Create Date: 2026-06-27

Creates 15 tables for the Decision Approval Engine:
  security_decision_approvals                 (root)
  security_decision_approval_decisions        (per-actor votes)
  security_decision_approval_policies         (pluggable policies)
  security_decision_approval_rules            (policy rules)
  security_decision_approval_requirements     (approver slots)
  security_decision_approval_evidence         (supporting data)
  security_decision_approval_reasons          (justifications)
  security_decision_approval_constraints      (preconditions)
  security_decision_approval_metadata         (kv metadata)
  security_decision_approval_history          (state-change audit)
  security_decision_approval_versions         (snapshot rows)
  security_decision_approval_statistics       (per-tenant metrics)
  security_decision_approval_audit            (append-only ledger)
  security_decision_approval_actors           (concrete approvers)
  security_decision_approval_groups           (logical groups)

All foreign keys target tables created by the decision_engine module
(`security_decisions`) and the decision_strategy module
(`security_decision_strategies`).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# Revision identifiers
revision = "011_decision_approval_tables"
down_revision = "010_decision_strategy_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = JSONB if is_postgres else sa.JSON

    # ── Enum types ────────────────────────────────────────────────
    approval_state_enum = sa.Enum(
        "CREATED", "VALIDATING", "WAITING_APPROVAL", "PARTIALLY_APPROVED",
        "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", "ARCHIVED",
        name="approval_state_enum",
    )
    approval_type_enum = sa.Enum(
        "SECURITY", "PLATFORM", "BUSINESS", "COMPLIANCE",
        "EMERGENCY", "AUTOMATIC",
        name="approval_type_enum",
    )
    approval_mode_enum = sa.Enum(
        "SINGLE", "MULTIPLE", "SEQUENTIAL", "PARALLEL",
        "MAJORITY", "AUTOMATIC_APPROVAL", "AUTOMATIC_REJECTION",
        name="approval_requirement_mode_enum",
    )
    approval_outcome_enum = sa.Enum(
        "PENDING", "APPROVED", "REJECTED", "ABSTAINED", "EXPIRED",
        name="approval_outcome_enum",
    )
    approval_history_from_enum = sa.Enum(
        "CREATED", "VALIDATING", "WAITING_APPROVAL", "PARTIALLY_APPROVED",
        "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", "ARCHIVED",
        name="approval_history_from_enum",
    )
    approval_history_to_enum = sa.Enum(
        "CREATED", "VALIDATING", "WAITING_APPROVAL", "PARTIALLY_APPROVED",
        "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", "ARCHIVED",
        name="approval_history_to_enum",
    )
    approval_statistics_type_enum = sa.Enum(
        "SECURITY", "PLATFORM", "BUSINESS", "COMPLIANCE",
        "EMERGENCY", "AUTOMATIC",
        name="approval_statistics_type_enum",
    )
    approval_statistics_state_enum = sa.Enum(
        "CREATED", "VALIDATING", "WAITING_APPROVAL", "PARTIALLY_APPROVED",
        "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", "ARCHIVED",
        name="approval_statistics_state_enum",
    )

    # ── 1. security_decision_approvals (root) ─────────────────────
    op.create_table(
        "security_decision_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("strategy_id", sa.String(36), nullable=True),
        sa.Column("approval_state", approval_state_enum, nullable=False, default="CREATED"),
        sa.Column("approval_type",  approval_type_enum,  nullable=False, default="SECURITY"),
        sa.Column("requirement_mode", approval_mode_enum, nullable=False, default="SINGLE"),
        sa.Column("summary", sa.String(2000), nullable=True),
        sa.Column("business_justification",  sa.String(2000), nullable=True),
        sa.Column("technical_justification", sa.String(2000), nullable=True),
        sa.Column("risk_score",        sa.Float(), nullable=False, default=0.0),
        sa.Column("criticality_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("composite_score",   sa.Float(), nullable=False, default=0.0),
        sa.Column("confidence",        sa.Float(), nullable=False, default=0.0),
        sa.Column("expires_at",     sa.String(50), nullable=True),
        sa.Column("is_emergency",   sa.Boolean(), nullable=False, default=False),
        sa.Column("auto_decided",   sa.Boolean(), nullable=False, default=False),
        sa.Column("blocked",        sa.Boolean(), nullable=False, default=False),
        sa.Column("blocked_reason", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["decision_id"], ["security_decisions.id"], name="fk_apr_decision"),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_apr_strategy"),
    )
    op.create_index("ix_apr_tenant",          "security_decision_approvals", ["tenant_id"])
    op.create_index("ix_apr_decision",        "security_decision_approvals", ["decision_id"])
    op.create_index("ix_apr_strategy",        "security_decision_approvals", ["strategy_id"])
    op.create_index("ix_apr_state",           "security_decision_approvals", ["approval_state"])
    op.create_index("ix_apr_type",            "security_decision_approvals", ["approval_type"])
    op.create_index("ix_apr_mode",            "security_decision_approvals", ["requirement_mode"])
    op.create_index("ix_apr_created_at",      "security_decision_approvals", ["created_at"])
    op.create_index("ix_apr_tenant_state",    "security_decision_approvals", ["tenant_id", "approval_state"])
    op.create_index("ix_apr_tenant_type",     "security_decision_approvals", ["tenant_id", "approval_type"])
    op.create_index("ix_apr_state_created",   "security_decision_approvals", ["approval_state", "created_at"])

    # ── 2. security_decision_approval_decisions ───────────────────
    op.create_table(
        "security_decision_approval_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("approver_id",   sa.String(100), nullable=False),
        sa.Column("approver_role", sa.String(100), nullable=True),
        sa.Column("outcome",       approval_outcome_enum, nullable=False, default="PENDING"),
        sa.Column("rationale",     sa.String(2000), nullable=True),
        sa.Column("decided_at",    sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_aprd_request"),
    )
    op.create_index("ix_aprd_request",         "security_decision_approval_decisions", ["request_id"])
    op.create_index("ix_aprd_approver",        "security_decision_approval_decisions", ["approver_id"])
    op.create_index("ix_aprd_outcome",         "security_decision_approval_decisions", ["outcome"])
    op.create_index("ix_aprd_request_outcome", "security_decision_approval_decisions", ["request_id", "outcome"])

    # ── 3. security_decision_approval_policies ────────────────────
    op.create_table(
        "security_decision_approval_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("policy_name",     sa.String(200), nullable=False),
        sa.Column("policy_version",  sa.Integer(), nullable=False, default=1),
        sa.Column("description",     sa.String(2000), nullable=True),
        sa.Column("is_active",       sa.Boolean(), nullable=False, default=True),
        sa.Column("priority",        sa.Integer(), nullable=False, default=100),
        sa.Column("config",          json_type, nullable=True),
    )
    op.create_index("ix_appol_tenant",   "security_decision_approval_policies", ["tenant_id"])
    op.create_index("ix_appol_name",     "security_decision_approval_policies", ["policy_name"])
    op.create_index("ix_appol_version",  "security_decision_approval_policies", ["policy_version"])
    op.create_index("ix_appol_active",   "security_decision_approval_policies", ["is_active"])

    # ── 4. security_decision_approval_rules ───────────────────────
    op.create_table(
        "security_decision_approval_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("policy_id", sa.String(36), nullable=False),
        sa.Column("factor",    sa.String(100), nullable=False),
        sa.Column("operator",  sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False, default=0.0),
        sa.Column("weight",    sa.Float(), nullable=False, default=0.0),
        sa.Column("action",    sa.String(50), nullable=False),
        sa.Column("notes",     sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["policy_id"], ["security_decision_approval_policies.id"], name="fk_aprule_policy"),
    )
    op.create_index("ix_aprule_policy", "security_decision_approval_rules", ["policy_id"])
    op.create_index("ix_aprule_factor", "security_decision_approval_rules", ["factor"])

    # ── 5. security_decision_approval_requirements ────────────────
    op.create_table(
        "security_decision_approval_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",     sa.String(36), nullable=False),
        sa.Column("required_role",  sa.String(100), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False, default=1),
        sa.Column("is_mandatory",   sa.Boolean(), nullable=False, default=True),
        sa.Column("description",    sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apreq_request"),
    )
    op.create_index("ix_apreq_request", "security_decision_approval_requirements", ["request_id"])
    op.create_index("ix_apreq_role",    "security_decision_approval_requirements", ["required_role"])
    op.create_index("ix_apreq_order",   "security_decision_approval_requirements", ["sequence_order"])

    # ── 6. security_decision_approval_evidence ────────────────────
    op.create_table(
        "security_decision_approval_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",     sa.String(36), nullable=False),
        sa.Column("evidence_type",  sa.String(100), nullable=False),
        sa.Column("evidence_value", sa.String(4000), nullable=False),
        sa.Column("source",         sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_ape_request"),
    )
    op.create_index("ix_ape_request", "security_decision_approval_evidence", ["request_id"])

    # ── 7. security_decision_approval_reasons ─────────────────────
    op.create_table(
        "security_decision_approval_reasons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",  sa.String(36), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("category",    sa.String(50), nullable=False, default="POLICY"),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_aprsn_request"),
    )
    op.create_index("ix_aprsn_request", "security_decision_approval_reasons", ["request_id"])
    op.create_index("ix_aprsn_code",    "security_decision_approval_reasons", ["reason_code"])

    # ── 8. security_decision_approval_constraints ─────────────────
    op.create_table(
        "security_decision_approval_constraints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",      sa.String(36), nullable=False),
        sa.Column("constraint_type", sa.String(100), nullable=False),
        sa.Column("is_met",          sa.Boolean(), nullable=False, default=False),
        sa.Column("details",         sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apc_request"),
    )
    op.create_index("ix_apc_request", "security_decision_approval_constraints", ["request_id"])
    op.create_index("ix_apc_type",    "security_decision_approval_constraints", ["constraint_type"])

    # ── 9. security_decision_approval_metadata ────────────────────
    op.create_table(
        "security_decision_approval_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("key",        sa.String(128), nullable=False),
        sa.Column("value",      sa.String(4000), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apmd_request"),
    )
    op.create_index("ix_apmd_request", "security_decision_approval_metadata", ["request_id"])
    op.create_index("ix_apmd_key",     "security_decision_approval_metadata", ["key"])

    # ── 10. security_decision_approval_history ────────────────────
    op.create_table(
        "security_decision_approval_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",  sa.String(36), nullable=False),
        sa.Column("from_state",  approval_history_from_enum, nullable=True),
        sa.Column("to_state",    approval_history_to_enum,   nullable=False),
        sa.Column("changed_by",    sa.String(100), nullable=False),
        sa.Column("change_reason", sa.String(2000), nullable=True),
        sa.Column("changed_at",    sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_aph_request"),
    )
    op.create_index("ix_aph_request",  "security_decision_approval_history", ["request_id"])
    op.create_index("ix_aph_to_state", "security_decision_approval_history", ["to_state"])
    op.create_index("ix_aph_at",       "security_decision_approval_history", ["changed_at"])

    # ── 11. security_decision_approval_versions ───────────────────
    op.create_table(
        "security_decision_approval_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",     sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot",       json_type, nullable=False),
        sa.Column("change_summary", sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apv_request"),
    )
    op.create_index("ix_apv_request", "security_decision_approval_versions", ["request_id"])
    op.create_index("ix_apv_version", "security_decision_approval_versions", ["version_number"])

    # ── 12. security_decision_approval_statistics ─────────────────
    op.create_table(
        "security_decision_approval_statistics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("approval_type",   approval_statistics_type_enum, nullable=False),
        sa.Column("approval_state",  approval_statistics_state_enum, nullable=False),
        sa.Column("count",           sa.Integer(), nullable=False, default=0),
        sa.Column("avg_duration_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_chain_length", sa.Float(), nullable=False, default=0.0),
        sa.Column("automatic_count", sa.Integer(), nullable=False, default=0),
        sa.Column("manual_count",    sa.Integer(), nullable=False, default=0),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_aps_request"),
    )
    op.create_index("ix_aps_tenant",      "security_decision_approval_statistics", ["tenant_id"])
    op.create_index("ix_aps_type",        "security_decision_approval_statistics", ["approval_type"])
    op.create_index("ix_aps_state",       "security_decision_approval_statistics", ["approval_state"])
    op.create_index("ix_aps_tenant_type", "security_decision_approval_statistics", ["tenant_id", "approval_type"])

    # ── 13. security_decision_approval_audit ──────────────────────
    op.create_table(
        "security_decision_approval_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",  sa.String(36), nullable=False),
        sa.Column("event_type",  sa.String(100), nullable=False),
        sa.Column("actor_id",    sa.String(100), nullable=True),
        sa.Column("actor_role",  sa.String(100), nullable=True),
        sa.Column("details",     json_type, nullable=True),
        sa.Column("occurred_at", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apa_request"),
    )
    op.create_index("ix_apa_request", "security_decision_approval_audit", ["request_id"])
    op.create_index("ix_apa_event",   "security_decision_approval_audit", ["event_type"])
    op.create_index("ix_apa_actor",   "security_decision_approval_audit", ["actor_id"])
    op.create_index("ix_apa_at",      "security_decision_approval_audit", ["occurred_at"])

    # ── 14. security_decision_approval_actors ─────────────────────
    op.create_table(
        "security_decision_approval_actors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id",   sa.String(36), nullable=False),
        sa.Column("actor_id",     sa.String(100), nullable=False),
        sa.Column("role",         sa.String(100), nullable=False),
        sa.Column("is_primary",   sa.Boolean(), nullable=False, default=True),
        sa.Column("delegated_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apact_request"),
    )
    op.create_index("ix_apa_request", "security_decision_approval_actors", ["request_id"])
    op.create_index("ix_apa_actor",   "security_decision_approval_actors", ["actor_id"])
    op.create_index("ix_apa_role",    "security_decision_approval_actors", ["role"])

    # ── 15. security_decision_approval_groups ─────────────────────
    op.create_table(
        "security_decision_approval_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("group_name", sa.String(200), nullable=False),
        sa.Column("member_ids", sa.String(4000), nullable=True),
        sa.Column("quorum",     sa.Integer(), nullable=False, default=1),
        sa.ForeignKeyConstraint(["request_id"], ["security_decision_approvals.id"], name="fk_apg_request"),
    )
    op.create_index("ix_apg_request", "security_decision_approval_groups", ["request_id"])
    op.create_index("ix_apg_name",    "security_decision_approval_groups", ["group_name"])


def downgrade() -> None:
    # Drop in reverse order so FKs don't fail.
    tables = [
        "security_decision_approval_groups",
        "security_decision_approval_actors",
        "security_decision_approval_audit",
        "security_decision_approval_statistics",
        "security_decision_approval_versions",
        "security_decision_approval_history",
        "security_decision_approval_metadata",
        "security_decision_approval_constraints",
        "security_decision_approval_reasons",
        "security_decision_approval_evidence",
        "security_decision_approval_requirements",
        "security_decision_approval_rules",
        "security_decision_approval_policies",
        "security_decision_approval_decisions",
        "security_decision_approvals",
    ]
    for t in tables:
        op.drop_table(t)

    sa.Enum(name="approval_state_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_requirement_mode_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_outcome_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_history_from_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_history_to_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_statistics_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approval_statistics_state_enum").drop(op.get_bind(), checkfirst=True)