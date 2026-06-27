"""Add execution orchestration tables (Module 0 / Part 6).

Revision ID: 012_execution_orchestration_tables
Revises: 011_decision_approval_tables
Create Date: 2026-06-27

Creates 12 tables for the Execution Orchestration Engine:
  security_execution_packages           (root)
  security_execution_preparations       (pre-pipeline snapshot)
  security_execution_readiness          (per-factor verdicts)
  security_execution_dependencies       (resolved refs)
  security_execution_constraints        (hard preconditions)
  security_execution_requirements       (soft requirements)
  security_execution_metadata           (kv metadata)
  security_execution_history            (state-change audit)
  security_execution_versions           (snapshot rows)
  security_execution_statistics         (per-tenant metrics)
  security_execution_audit              (append-only ledger)
  security_execution_summary            (denormalised "ready-to-show")

All foreign keys target tables created by the decision_engine module
(`security_decisions`), the decision_strategy module
(`security_decision_strategies`), and the decision_approval module
(`security_decision_approvals`).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# Revision identifiers
revision = "012_execution_orchestration_tables"
down_revision = "011_decision_approval_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = JSONB if is_postgres else sa.JSON

    # ── Enum types ────────────────────────────────────────────────
    package_state_enum = sa.Enum(
        "CREATED", "READINESS_VALIDATING", "READINESS_PASSED",
        "READINESS_FAILED", "BUILDING", "BUILT", "READY",
        "REJECTED", "FAILED", "ARCHIVED",
        name="execution_package_state_enum",
    )
    readiness_outcome_enum = sa.Enum(
        "PASSED", "WARNING", "FAILED",
        name="execution_readiness_outcome_enum",
    )
    dependency_kind_enum = sa.Enum(
        "REPOSITORY", "ASSET", "PACKAGE", "CVE", "FINDING",
        "POLICY", "APPROVAL", "DECISION", "STRATEGY", "EXTERNAL",
        name="execution_dependency_kind_enum",
    )
    constraint_type_enum = sa.Enum(
        "DECISION_READY", "APPROVAL_APPROVED", "STRATEGY_APPROVED",
        "REPOSITORY_PRESENT", "ASSET_PRESENT", "DEPENDENCY_RESOLVED",
        "METADATA_COMPLETE", "TENANT_MATCH", "POLICY_PASSED",
        "ENVIRONMENT_MATCH", "EXECUTION_WINDOW_OPEN", "ROLLBACK_PLANNED",
        name="execution_constraint_type_enum",
    )
    history_from_enum = sa.Enum(
        "CREATED", "READINESS_VALIDATING", "READINESS_PASSED",
        "READINESS_FAILED", "BUILDING", "BUILT", "READY",
        "REJECTED", "FAILED", "ARCHIVED",
        name="execution_history_from_enum",
    )
    history_to_enum = sa.Enum(
        "CREATED", "READINESS_VALIDATING", "READINESS_PASSED",
        "READINESS_FAILED", "BUILDING", "BUILT", "READY",
        "REJECTED", "FAILED", "ARCHIVED",
        name="execution_history_to_enum",
    )
    statistics_state_enum = sa.Enum(
        "CREATED", "READINESS_VALIDATING", "READINESS_PASSED",
        "READINESS_FAILED", "BUILDING", "BUILT", "READY",
        "REJECTED", "FAILED", "ARCHIVED",
        name="execution_statistics_state_enum",
    )

    # ── 1. security_execution_packages (root) ────────────────────
    op.create_table(
        "security_execution_packages",
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
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.Column("package_state",   package_state_enum,   nullable=False, default="CREATED"),
        sa.Column("package_version", sa.Integer(),         nullable=False, default=1),
        sa.Column("is_immutable",    sa.Boolean(),         nullable=False, default=False),
        sa.Column("is_ready",        sa.Boolean(),         nullable=False, default=False),
        sa.Column("is_rejected",     sa.Boolean(),         nullable=False, default=False),
        sa.Column("rejection_reason", sa.String(1000),     nullable=True),
        sa.Column("decision_version", sa.Integer(),        nullable=True),
        sa.Column("strategy_version", sa.Integer(),        nullable=True),
        sa.Column("approval_version", sa.Integer(),        nullable=True),
        sa.Column("summary",         sa.String(2000),      nullable=True),
        sa.Column("payload_hash",    sa.String(128),       nullable=True),
        sa.Column("dependency_count", sa.Integer(),        nullable=False, default=0),
        sa.Column("constraint_count", sa.Integer(),        nullable=False, default=0),
        sa.Column("metadata_count",   sa.Integer(),        nullable=False, default=0),
        sa.Column("package_size_kb",  sa.Float(),          nullable=False, default=0.0),
        sa.ForeignKeyConstraint(["decision_id"], ["security_decisions.id"],               name="fk_epkg_decision"),
        sa.ForeignKeyConstraint(["strategy_id"], ["security_decision_strategies.id"],     name="fk_epkg_strategy"),
        sa.ForeignKeyConstraint(["approval_id"], ["security_decision_approvals.id"],      name="fk_epkg_approval"),
    )
    op.create_index("ix_epkg_tenant",         "security_execution_packages", ["tenant_id"])
    op.create_index("ix_epkg_decision",       "security_execution_packages", ["decision_id"])
    op.create_index("ix_epkg_strategy",       "security_execution_packages", ["strategy_id"])
    op.create_index("ix_epkg_approval",       "security_execution_packages", ["approval_id"])
    op.create_index("ix_epkg_state",          "security_execution_packages", ["package_state"])
    op.create_index("ix_epkg_version",        "security_execution_packages", ["package_version"])
    op.create_index("ix_epkg_created_at",     "security_execution_packages", ["created_at"])
    op.create_index("ix_epkg_tenant_state",   "security_execution_packages", ["tenant_id", "package_state"])
    op.create_index("ix_epkg_state_created",  "security_execution_packages", ["package_state", "created_at"])
    op.create_index("ix_epkg_decision_state", "security_execution_packages", ["decision_id", "package_state"])

    # ── 2. security_execution_preparations ────────────────────────
    op.create_table(
        "security_execution_preparations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",     sa.String(36), nullable=False, unique=True),
        sa.Column("decision_id",    sa.String(36), nullable=False),
        sa.Column("decision_snapshot", json_type, nullable=True),
        sa.Column("strategy_snapshot", json_type, nullable=True),
        sa.Column("approval_snapshot", json_type, nullable=True),
        sa.Column("context_snapshot",  json_type, nullable=True),
        sa.Column("is_complete",   sa.Boolean(),      nullable=False, default=False),
        sa.Column("missing_fields", sa.String(4000),  nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_eprep_package"),
    )
    op.create_index("ix_eprep_tenant",   "security_execution_preparations", ["tenant_id"])
    op.create_index("ix_eprep_decision", "security_execution_preparations", ["decision_id"])
    op.create_index("ix_eprep_package",  "security_execution_preparations", ["package_id"])

    # ── 3. security_execution_readiness ───────────────────────────
    op.create_table(
        "security_execution_readiness",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",    sa.String(36), nullable=False, unique=True),
        sa.Column("outcome",       readiness_outcome_enum, nullable=False, default="PASSED"),
        sa.Column("factors_total",  sa.Integer(), nullable=False, default=0),
        sa.Column("factors_passed", sa.Integer(), nullable=False, default=0),
        sa.Column("factors_warned", sa.Integer(), nullable=False, default=0),
        sa.Column("factors_failed", sa.Integer(), nullable=False, default=0),
        sa.Column("validation_ms",  sa.Float(),   nullable=False, default=0.0),
        sa.Column("verdicts",       sa.String(8000), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_erd_package"),
    )
    op.create_index("ix_erd_tenant",  "security_execution_readiness", ["tenant_id"])
    op.create_index("ix_erd_package", "security_execution_readiness", ["package_id"])
    op.create_index("ix_erd_outcome", "security_execution_readiness", ["outcome"])

    # ── 4. security_execution_dependencies ────────────────────────
    op.create_table(
        "security_execution_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",    sa.String(36), nullable=False),
        sa.Column("kind",          dependency_kind_enum, nullable=False),
        sa.Column("reference",     sa.String(255), nullable=False),
        sa.Column("display_name",  sa.String(500), nullable=True),
        sa.Column("is_resolved",   sa.Boolean(),   nullable=False, default=False),
        sa.Column("resolution_ms", sa.Float(),     nullable=False, default=0.0),
        sa.Column("notes",         sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_edep_package"),
    )
    op.create_index("ix_edep_tenant",   "security_execution_dependencies", ["tenant_id"])
    op.create_index("ix_edep_package",  "security_execution_dependencies", ["package_id"])
    op.create_index("ix_edep_kind",     "security_execution_dependencies", ["kind"])
    op.create_index("ix_edep_resolved", "security_execution_dependencies", ["is_resolved"])

    # ── 5. security_execution_constraints ─────────────────────────
    op.create_table(
        "security_execution_constraints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",      sa.String(36), nullable=False),
        sa.Column("constraint_type", constraint_type_enum, nullable=False),
        sa.Column("is_met",     sa.Boolean(),      nullable=False, default=False),
        sa.Column("severity",   sa.String(20),    nullable=False, default="HARD"),
        sa.Column("details",    sa.String(2000),  nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_ec_package"),
    )
    op.create_index("ix_ec_tenant",  "security_execution_constraints", ["tenant_id"])
    op.create_index("ix_ec_package", "security_execution_constraints", ["package_id"])
    op.create_index("ix_ec_type",    "security_execution_constraints", ["constraint_type"])
    op.create_index("ix_ec_met",     "security_execution_constraints", ["is_met"])

    # ── 6. security_execution_requirements ────────────────────────
    op.create_table(
        "security_execution_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",       sa.String(36),  nullable=False),
        sa.Column("requirement_type", sa.String(100), nullable=False),
        sa.Column("value",            sa.String(2000), nullable=True),
        sa.Column("is_mandatory",     sa.Boolean(),    nullable=False, default=False),
        sa.Column("description",      sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_erq_package"),
    )
    op.create_index("ix_erq_tenant",  "security_execution_requirements", ["tenant_id"])
    op.create_index("ix_erq_package", "security_execution_requirements", ["package_id"])

    # ── 7. security_execution_metadata ────────────────────────────
    op.create_table(
        "security_execution_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("key",         sa.String(128), nullable=False),
        sa.Column("value",       sa.String(4000), nullable=False),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_emd_package"),
    )
    op.create_index("ix_emd_tenant",  "security_execution_metadata", ["tenant_id"])
    op.create_index("ix_emd_package", "security_execution_metadata", ["package_id"])
    op.create_index("ix_emd_key",     "security_execution_metadata", ["key"])

    # ── 8. security_execution_history ─────────────────────────────
    op.create_table(
        "security_execution_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",    sa.String(36), nullable=False),
        sa.Column("from_state",    history_from_enum, nullable=True),
        sa.Column("to_state",      history_to_enum,   nullable=False),
        sa.Column("changed_by",    sa.String(100), nullable=False),
        sa.Column("change_reason", sa.String(2000), nullable=True),
        sa.Column("changed_at",    sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_eh_package"),
    )
    op.create_index("ix_eh_tenant",     "security_execution_history", ["tenant_id"])
    op.create_index("ix_eh_package",    "security_execution_history", ["package_id"])
    op.create_index("ix_eh_to_state",   "security_execution_history", ["to_state"])
    op.create_index("ix_eh_changed_at", "security_execution_history", ["changed_at"])

    # ── 9. security_execution_versions ────────────────────────────
    op.create_table(
        "security_execution_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",     sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(),   nullable=False),
        sa.Column("snapshot",       json_type,      nullable=False),
        sa.Column("change_summary", sa.String(2000), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_ev_package"),
    )
    op.create_index("ix_ev_tenant",   "security_execution_versions", ["tenant_id"])
    op.create_index("ix_ev_package",  "security_execution_versions", ["package_id"])
    op.create_index("ix_ev_version",  "security_execution_versions", ["version_number"])

    # ── 10. security_execution_statistics ─────────────────────────
    op.create_table(
        "security_execution_statistics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_state", statistics_state_enum, nullable=False),
        sa.Column("count",               sa.Integer(), nullable=False, default=0),
        sa.Column("avg_duration_ms",     sa.Float(),   nullable=False, default=0.0),
        sa.Column("avg_package_size_kb", sa.Float(),   nullable=False, default=0.0),
        sa.Column("rejected_count",      sa.Integer(), nullable=False, default=0),
        sa.Column("ready_count",         sa.Integer(), nullable=False, default=0),
        sa.Column("package_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_es_package"),
    )
    op.create_index("ix_es_tenant",        "security_execution_statistics", ["tenant_id"])
    op.create_index("ix_es_state",         "security_execution_statistics", ["package_state"])
    op.create_index("ix_es_tenant_state",  "security_execution_statistics", ["tenant_id", "package_state"])

    # ── 11. security_execution_audit ──────────────────────────────
    op.create_table(
        "security_execution_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",  sa.String(36), nullable=False),
        sa.Column("event_type",  sa.String(100), nullable=False),
        sa.Column("actor_id",    sa.String(100), nullable=True),
        sa.Column("actor_role",  sa.String(100), nullable=True),
        sa.Column("details",     json_type, nullable=True),
        sa.Column("occurred_at", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_ea_package"),
    )
    op.create_index("ix_ea_tenant",  "security_execution_audit", ["tenant_id"])
    op.create_index("ix_ea_package", "security_execution_audit", ["package_id"])
    op.create_index("ix_ea_event",   "security_execution_audit", ["event_type"])
    op.create_index("ix_ea_actor",   "security_execution_audit", ["actor_id"])
    op.create_index("ix_ea_at",      "security_execution_audit", ["occurred_at"])

    # ── 12. security_execution_summary ────────────────────────────
    op.create_table(
        "security_execution_summary",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("package_id",        sa.String(36), nullable=False, unique=True),
        sa.Column("readiness_status",  sa.String(50),  nullable=False, default="UNKNOWN"),
        sa.Column("validation_results", json_type, nullable=True),
        sa.Column("selected_strategy", sa.String(200), nullable=True),
        sa.Column("approval_status",   sa.String(50),  nullable=False, default="UNKNOWN"),
        sa.Column("dependency_count",  sa.Integer(),   nullable=False, default=0),
        sa.Column("constraint_passed", sa.Integer(),   nullable=False, default=0),
        sa.Column("constraint_failed", sa.Integer(),   nullable=False, default=0),
        sa.Column("package_metadata",  json_type, nullable=True),
        sa.Column("package_timeline",  json_type, nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["security_execution_packages.id"], name="fk_esu_package"),
    )
    op.create_index("ix_esu_tenant",  "security_execution_summary", ["tenant_id"])
    op.create_index("ix_esu_package", "security_execution_summary", ["package_id"])


def downgrade() -> None:
    # Drop in reverse order so FKs don't fail.
    tables = [
        "security_execution_summary",
        "security_execution_audit",
        "security_execution_statistics",
        "security_execution_versions",
        "security_execution_history",
        "security_execution_metadata",
        "security_execution_requirements",
        "security_execution_constraints",
        "security_execution_dependencies",
        "security_execution_readiness",
        "security_execution_preparations",
        "security_execution_packages",
    ]
    for t in tables:
        op.drop_table(t)

    sa.Enum(name="execution_package_state_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_readiness_outcome_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_dependency_kind_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_constraint_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_history_from_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_history_to_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="execution_statistics_state_enum").drop(op.get_bind(), checkfirst=True)