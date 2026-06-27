"""Add decision strategy tables (Module 0 / Part 4).

Revision ID: 010_decision_strategy_tables
Revises: 009_detected_by
Create Date: 2026-06-27

Creates 13 tables for the Decision Strategy Engine:
  security_decision_strategies                  (root)
  security_decision_strategy_candidates         (considered candidates)
  security_decision_strategy_scores             (per-dimension scoring)
  security_decision_strategy_rankings           (final ranking audit)
  security_decision_strategy_evaluations        (pipeline-run audit)
  security_decision_strategy_constraints        (hard preconditions)
  security_decision_strategy_requirements       (runtime requirements)
  security_decision_strategy_reasons            (justifications)
  security_decision_strategy_evidence           (supporting evidence)
  security_decision_strategy_metadata           (kv metadata)
  security_decision_strategy_history            (state-change audit)
  security_decision_strategy_statistics         (per-tenant metrics)
  security_decision_strategy_versions           (versioned snapshots)

All foreign keys target tables created by the decision_engine module
(`security_decisions`, `security_decision_plans`).  Those tables are
expected to exist via the prior `init_db()` run; this migration does
NOT create them — they live behind the decision_engine's own migration
in a later revision (tracked separately).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# Revision identifiers
revision = "010_decision_strategy_tables"
down_revision = "009_detected_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum types
    strategy_type_enum = sa.Enum(
        "PATCH_EXISTING_VERSION", "UPGRADE_PACKAGE", "DOWNGRADE_PACKAGE",
        "REPLACE_DEPENDENCY", "DISABLE_FEATURE", "CONFIGURATION_CHANGE",
        "INFRASTRUCTURE_CHANGE", "CONTAINER_UPDATE", "OS_PACKAGE_UPDATE",
        "IMAGE_REPLACEMENT", "SECRET_ROTATION", "CERTIFICATE_ROTATION",
        "POLICY_CHANGE", "TEMPORARY_MITIGATION", "MANUAL_REVIEW_REQUIRED",
        "VENDOR_PATCH_REQUIRED", "NO_ACTION",
        name="strategy_type_enum",
    )
    strategy_state_enum = sa.Enum(
        "SELECTED", "APPROVED", "EXECUTING", "COMPLETED",
        "FAILED", "REJECTED", "ARCHIVED",
        name="strategy_state_enum",
    )

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = JSONB if is_postgres else sa.JSON

    # ── security_decision_strategies (root) ─────────────────────────────
    op.create_table(
        "security_decision_strategies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=True),
        sa.Column("strategy_type", strategy_type_enum, nullable=False, default="NO_ACTION"),
        sa.Column("state", strategy_state_enum, nullable=False, default="SELECTED"),
        sa.Column("priority", sa.Integer(), nullable=False, default=100),
        sa.Column("confidence", sa.Float(), nullable=False, default=0.0),
        sa.Column("risk_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("feasibility_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("composite_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("business_justification", sa.String(2000), nullable=True),
        sa.Column("technical_justification", sa.String(2000), nullable=True),
        sa.Column("selection_reason", sa.String(2000), nullable=True),
        sa.Column("rejected_reason", sa.String(2000), nullable=True),
        sa.Column("expected_downtime_min", sa.Integer(), nullable=True),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_reversible", sa.Boolean(), nullable=False, default=True),
        sa.ForeignKeyConstraint(["decision_id"], ["security_decisions.id"], name="fk_dstrat_decision"),
        sa.ForeignKeyConstraint(["plan_id"], ["security_decision_plans.id"], name="fk_dstrat_plan"),
    )
    op.create_index("ix_dstrat_tenant",       "security_decision_strategies", ["tenant_id"])
    op.create_index("ix_dstrat_decision",     "security_decision_strategies", ["decision_id"])
    op.create_index("ix_dstrat_strategy",     "security_decision_strategies", ["strategy_type"])
    op.create_index("ix_dstrat_state",        "security_decision_strategies", ["state"])
    op.create_index("ix_dstrat_priority",     "security_decision_strategies", ["priority"])
    op.create_index("ix_dstrat_tenant_state", "security_decision_strategies", ["tenant_id", "state"])

    # ── security_decision_strategy_candidates ───────────────────────────
    op.create_table(
        "security_decision_strategy_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("candidate_type", strategy_type_enum, nullable=False),
        sa.Column("feasibility_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("composite_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, default=True),
        sa.Column("rejected_reason", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dsc_strategy"),
    )
    op.create_index("ix_dsc_tenant",   "security_decision_strategy_candidates", ["tenant_id"])
    op.create_index("ix_dsc_strategy", "security_decision_strategy_candidates", ["strategy_id"])
    op.create_index("ix_dsc_type",     "security_decision_strategy_candidates", ["candidate_type"])

    # ── security_decision_strategy_scores ──────────────────────────────
    op.create_table(
        "security_decision_strategy_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("dimension", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False, default=0.0),
        sa.Column("weight", sa.Float(), nullable=False, default=0.0),
        sa.Column("contribution", sa.Float(), nullable=False, default=0.0),
        sa.Column("rationale", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["security_decision_strategy_candidates.id"], name="fk_dsscr_candidate"),
    )
    op.create_index("ix_dsscr_candidate", "security_decision_strategy_scores", ["candidate_id"])
    op.create_index("ix_dsscr_dimension", "security_decision_strategy_scores", ["dimension"])

    # ── security_decision_strategy_rankings ────────────────────────────
    op.create_table(
        "security_decision_strategy_rankings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False, default=0.0),
        sa.ForeignKeyConstraint(["candidate_id"], ["security_decision_strategy_candidates.id"], name="fk_dsr_candidate"),
    )
    op.create_index("ix_dsr_candidate", "security_decision_strategy_rankings", ["candidate_id"])
    op.create_index("ix_dsr_rank",      "security_decision_strategy_rankings", ["rank"])

    # ── security_decision_strategy_evaluations ──────────────────────────
    op.create_table(
        "security_decision_strategy_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("selected_strategy_id", sa.String(36), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False, default=0),
        sa.Column("rejected_count", sa.Integer(), nullable=False, default=0),
        sa.Column("duration_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("ranking_duration_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("selection_duration_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["decision_id"], ["security_decisions.id"], name="fk_dse_decision"),
        sa.ForeignKeyConstraint(["selected_strategy_id"], ["security_decision_strategies.id"], name="fk_dse_strategy"),
    )
    op.create_index("ix_dse_tenant",   "security_decision_strategy_evaluations", ["tenant_id"])
    op.create_index("ix_dse_decision", "security_decision_strategy_evaluations", ["decision_id"])

    # ── security_decision_strategy_constraints ──────────────────────────
    op.create_table(
        "security_decision_strategy_constraints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("constraint_type", sa.String(100), nullable=False),
        sa.Column("is_met", sa.Boolean(), nullable=False, default=False),
        sa.Column("details", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dscstrat_strategy"),
    )
    op.create_index("ix_dscstrat_strategy", "security_decision_strategy_constraints", ["strategy_id"])
    op.create_index("ix_dscstrat_type",     "security_decision_strategy_constraints", ["constraint_type"])

    # ── security_decision_strategy_requirements ─────────────────────────
    op.create_table(
        "security_decision_strategy_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("requirement_type", sa.String(100), nullable=False),
        sa.Column("value", sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dsreq_strategy"),
    )
    op.create_index("ix_dsreq_strategy", "security_decision_strategy_requirements", ["strategy_id"])
    op.create_index("ix_dsreq_type",     "security_decision_strategy_requirements", ["requirement_type"])

    # ── security_decision_strategy_reasons ──────────────────────────────
    op.create_table(
        "security_decision_strategy_reasons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, default="TECHNICAL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dsr_strat"),
    )
    op.create_index("ix_dsr_strat", "security_decision_strategy_reasons", ["strategy_id"])
    op.create_index("ix_dsr_code",  "security_decision_strategy_reasons", ["reason_code"])

    # ── security_decision_strategy_evidence ─────────────────────────────
    op.create_table(
        "security_decision_strategy_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("reason_id", sa.String(36), nullable=False),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column("evidence_value", sa.String(2000), nullable=False),
        sa.ForeignKeyConstraint(["reason_id"], ["security_decision_strategy_reasons.id"], name="fk_dsev_reason"),
    )
    op.create_index("ix_dsev_reason", "security_decision_strategy_evidence", ["reason_id"])

    # ── security_decision_strategy_metadata ─────────────────────────────
    op.create_table(
        "security_decision_strategy_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dsmeta_strategy"),
    )
    op.create_index("ix_dsmeta_strategy", "security_decision_strategy_metadata", ["strategy_id"])

    # ── security_decision_strategy_history ──────────────────────────────
    op.create_table(
        "security_decision_strategy_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("from_state", strategy_state_enum, nullable=True),
        sa.Column("to_state", strategy_state_enum, nullable=False),
        sa.Column("changed_by", sa.String(100), nullable=False),
        sa.Column("change_reason", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dsh_strategy"),
    )
    op.create_index("ix_dsh_strategy", "security_decision_strategy_history", ["strategy_id"])
    op.create_index("ix_dsh_to_state", "security_decision_strategy_history", ["to_state"])

    # ── security_decision_strategy_statistics ───────────────────────────
    op.create_table(
        "security_decision_strategy_statistics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_type", strategy_type_enum, nullable=False),
        sa.Column("state", strategy_state_enum, nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, default=0),
        sa.Column("avg_duration_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_confidence", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_risk", sa.Float(), nullable=False, default=0.0),
    )
    op.create_index("ix_dss_tenant",       "security_decision_strategy_statistics", ["tenant_id"])
    op.create_index("ix_dss_type",         "security_decision_strategy_statistics", ["strategy_type"])
    op.create_index("ix_dss_state",        "security_decision_strategy_statistics", ["state"])
    op.create_index("ix_dss_tenant_type",  "security_decision_strategy_statistics", ["tenant_id", "strategy_type"])

    # ── security_decision_strategy_versions ─────────────────────────────
    op.create_table(
        "security_decision_strategy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", json_type, nullable=False),
        sa.Column("change_summary", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"], name="fk_dsv_strategy"),
    )
    op.create_index("ix_dsv_strategy", "security_decision_strategy_versions", ["strategy_id"])
    op.create_index("ix_dsv_version",  "security_decision_strategy_versions", ["version_number"])


def downgrade() -> None:
    op.drop_index("ix_dsv_version",  table_name="security_decision_strategy_versions")
    op.drop_index("ix_dsv_strategy", table_name="security_decision_strategy_versions")
    op.drop_table("security_decision_strategy_versions")

    op.drop_index("ix_dss_tenant_type",  table_name="security_decision_strategy_statistics")
    op.drop_index("ix_dss_state",        table_name="security_decision_strategy_statistics")
    op.drop_index("ix_dss_type",         table_name="security_decision_strategy_statistics")
    op.drop_index("ix_dss_tenant",       table_name="security_decision_strategy_statistics")
    op.drop_table("security_decision_strategy_statistics")

    op.drop_index("ix_dsh_to_state", table_name="security_decision_strategy_history")
    op.drop_index("ix_dsh_strategy", table_name="security_decision_strategy_history")
    op.drop_table("security_decision_strategy_history")

    op.drop_index("ix_dsmeta_strategy", table_name="security_decision_strategy_metadata")
    op.drop_table("security_decision_strategy_metadata")

    op.drop_index("ix_dsev_reason", table_name="security_decision_strategy_evidence")
    op.drop_table("security_decision_strategy_evidence")

    op.drop_index("ix_dsr_code",  table_name="security_decision_strategy_reasons")
    op.drop_index("ix_dsr_strat", table_name="security_decision_strategy_reasons")
    op.drop_table("security_decision_strategy_reasons")

    op.drop_index("ix_dsreq_type",     table_name="security_decision_strategy_requirements")
    op.drop_index("ix_dsreq_strategy", table_name="security_decision_strategy_requirements")
    op.drop_table("security_decision_strategy_requirements")

    op.drop_index("ix_dscstrat_type",     table_name="security_decision_strategy_constraints")
    op.drop_index("ix_dscstrat_strategy", table_name="security_decision_strategy_constraints")
    op.drop_table("security_decision_strategy_constraints")

    op.drop_index("ix_dse_decision", table_name="security_decision_strategy_evaluations")
    op.drop_index("ix_dse_tenant",   table_name="security_decision_strategy_evaluations")
    op.drop_table("security_decision_strategy_evaluations")

    op.drop_index("ix_dsr_rank",      table_name="security_decision_strategy_rankings")
    op.drop_index("ix_dsr_candidate", table_name="security_decision_strategy_rankings")
    op.drop_table("security_decision_strategy_rankings")

    op.drop_index("ix_dsscr_dimension", table_name="security_decision_strategy_scores")
    op.drop_index("ix_dsscr_candidate", table_name="security_decision_strategy_scores")
    op.drop_table("security_decision_strategy_scores")

    op.drop_index("ix_dsc_type",     table_name="security_decision_strategy_candidates")
    op.drop_index("ix_dsc_strategy", table_name="security_decision_strategy_candidates")
    op.drop_index("ix_dsc_tenant",   table_name="security_decision_strategy_candidates")
    op.drop_table("security_decision_strategy_candidates")

    op.drop_index("ix_dstrat_tenant_state", table_name="security_decision_strategies")
    op.drop_index("ix_dstrat_priority",     table_name="security_decision_strategies")
    op.drop_index("ix_dstrat_state",        table_name="security_decision_strategies")
    op.drop_index("ix_dstrat_strategy",     table_name="security_decision_strategies")
    op.drop_index("ix_dstrat_decision",     table_name="security_decision_strategies")
    op.drop_index("ix_dstrat_tenant",       table_name="security_decision_strategies")
    op.drop_table("security_decision_strategies")

    op.execute("DROP TYPE IF EXISTS strategy_state_enum")
    op.execute("DROP TYPE IF EXISTS strategy_type_enum")