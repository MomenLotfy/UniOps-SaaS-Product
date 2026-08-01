"""Add ownership management tables.

Revision ID: 016_add_ownership_tables
Revises: 015_idempotency_records
Create Date: 2026-07-03

Creates tables for comprehensive ownership management:
- ownership_mappings: Stores owner, team, department for any resource
- ownership_audit_logs: Tracks all ownership changes
- ownership_defaults: Default rules for automatic assignment
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


revision = "016_add_ownership_tables"
down_revision = "015_idempotency_records"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(
        text("SELECT 1 FROM pg_tables WHERE schemaname = current_schema() AND tablename = :t"),
        {"t": table_name},
    ).first()
    return row is not None


def upgrade() -> None:
    # ownership_mappings table (idempotent)
    if not _table_exists("ownership_mappings"):
        op.create_table(
            "ownership_mappings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.String(36), nullable=False),
            sa.Column("owner", sa.String(255), nullable=True),
            sa.Column("owner_type", sa.String(50), nullable=False, default="user"),
            sa.Column("team", sa.String(255), nullable=True),
            sa.Column("department", sa.String(255), nullable=True),
            sa.Column("business_unit", sa.String(255), nullable=True),
            sa.Column("backup_owner", sa.String(255), nullable=True),
            sa.Column("escalation_chain", sa.JSON(), nullable=False, default=list),
            sa.Column("business_criticality", sa.String(50), nullable=False, default="standard"),
            sa.Column("environment", sa.String(50), nullable=False, default="unknown"),
            sa.Column("region", sa.String(100), nullable=True),
            sa.Column("risk_level", sa.String(20), nullable=False, default="medium"),
            sa.Column("sla_status", sa.String(50), nullable=False, default="compliant"),
            sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_by", sa.String(36), nullable=True),
            sa.Column("is_assigned", sa.Boolean(), nullable=False, default=False),
            sa.Column("assignment_method", sa.String(50), nullable=False, default="manual"),
            sa.Column("cloud_provider", sa.String(50), nullable=True),
            sa.Column("cloud_account_id", sa.String(100), nullable=True),
            sa.Column("cluster_name", sa.String(255), nullable=True),
            sa.Column("namespace", sa.String(255), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        )
        op.create_index("ix_ownership_mapping_tenant", "ownership_mappings", ["tenant_id"])
        op.create_index("ix_ownership_mapping_entity", "ownership_mappings", ["entity_type", "entity_id"])
        op.create_index("ix_ownership_mapping_owner", "ownership_mappings", ["owner"])
        op.create_index("ix_ownership_mapping_team", "ownership_mappings", ["team"])
        op.create_index("ix_ownership_mapping_dept", "ownership_mappings", ["department"])

    # ownership_audit_logs table (idempotent)
    if not _table_exists("ownership_audit_logs"):
        op.create_table(
            "ownership_audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.String(36), nullable=False),
            sa.Column("entity_name", sa.String(500), nullable=True),
            sa.Column("prev_owner", sa.String(255), nullable=True),
            sa.Column("prev_team", sa.String(255), nullable=True),
            sa.Column("prev_dept", sa.String(255), nullable=True),
            sa.Column("new_owner", sa.String(255), nullable=True),
            sa.Column("new_team", sa.String(255), nullable=True),
            sa.Column("new_dept", sa.String(255), nullable=True),
            sa.Column("changed_by", sa.String(36), nullable=False),
            sa.Column("change_type", sa.String(50), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        )
        op.create_index("ix_audit_log_tenant", "ownership_audit_logs", ["tenant_id"])
        op.create_index("ix_audit_log_entity", "ownership_audit_logs", ["entity_type", "entity_id"])
        op.create_index("ix_audit_log_owner", "ownership_audit_logs", ["changed_by"])
        op.create_index("ix_audit_log_changed_at", "ownership_audit_logs", ["changed_at"])

    # ownership_defaults table (idempotent)
    if not _table_exists("ownership_defaults"):
        op.create_table(
            "ownership_defaults",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("resource_type", sa.String(50), nullable=False),
            sa.Column("environment", sa.String(50), nullable=True),
            sa.Column("cloud_provider", sa.String(50), nullable=True),
            sa.Column("region", sa.String(100), nullable=True),
            sa.Column("tag_key", sa.String(100), nullable=True),
            sa.Column("tag_value", sa.String(100), nullable=True),
            sa.Column("owner", sa.String(255), nullable=False),
            sa.Column("owner_type", sa.String(50), nullable=False, default="user"),
            sa.Column("team", sa.String(255), nullable=True),
            sa.Column("department", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
            sa.Column("priority", sa.Integer(), nullable=False, default=100),
            sa.Column("rule_name", sa.String(255), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        )
        op.create_index("ix_ownership_default_tenant", "ownership_defaults", ["tenant_id"])
        op.create_index("ix_ownership_default_type", "ownership_defaults", ["resource_type"])


def downgrade() -> None:
    op.drop_index("ix_ownership_default_type", table_name="ownership_defaults")
    op.drop_index("ix_ownership_default_tenant", table_name="ownership_defaults")
    op.drop_table("ownership_defaults")

    op.drop_index("ix_audit_log_changed_at", table_name="ownership_audit_logs")
    op.drop_index("ix_audit_log_owner", table_name="ownership_audit_logs")
    op.drop_index("ix_audit_log_entity", table_name="ownership_audit_logs")
    op.drop_index("ix_audit_log_tenant", table_name="ownership_audit_logs")
    op.drop_table("ownership_audit_logs")

    op.drop_index("ix_ownership_mapping_dept", table_name="ownership_mappings")
    op.drop_index("ix_ownership_mapping_team", table_name="ownership_mappings")
    op.drop_index("ix_ownership_mapping_owner", table_name="ownership_mappings")
    op.drop_index("ix_ownership_mapping_entity", table_name="ownership_mappings")
    op.drop_index("ix_ownership_mapping_tenant", table_name="ownership_mappings")
    op.drop_table("ownership_mappings")
