"""Add reports and report scheduling tables.

Revision ID: 017_add_report_tables
Revises: 016_add_ownership_tables
Create Date: 2026-07-03

Creates tables for comprehensive reporting functionality:
- reports: Stores generated reports with status, scheduling, and results
- report_templates: Template definitions for report generation
- scheduled_reports: Tracks scheduled report runs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.sql import text


revision = "017_add_report_tables"
down_revision = "016_add_ownership_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    # Check if tables already exist (for idempotent migration)
    existing_tables = inspector.get_table_names()

    # report_templates table - stores template definitions
    if "report_templates" not in existing_tables:
        op.create_table(
            "report_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("key", sa.String(100), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(50), nullable=False, default="security"),
            sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
            sa.Column("default_format", sa.String(20), nullable=False, default="json"),
            sa.Column("default_params", sa.JSON(), nullable=False, default=dict),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        )
        op.create_index("ix_report_template_tenant", "report_templates", ["tenant_id"])
        op.create_index("ix_report_template_key", "report_templates", ["key"])
        op.create_index("ix_report_template_category", "report_templates", ["category"])
    else:
        # Pre-existing table from earlier create_all run may have used
        # `key` as the primary key with a composite (key, id) PK.  Add a
        # standalone UNIQUE constraint on `key` so other tables can FK
        # reference it (required by scheduled_reports below).
        conn.execute(
            text(
                "ALTER TABLE report_templates "
                "DROP CONSTRAINT IF EXISTS report_templates_key_unique"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE report_templates "
                "ADD CONSTRAINT report_templates_key_unique UNIQUE (key)"
            )
        )

    # reports table - stores generated reports
    if "reports" not in existing_tables:
        op.create_table(
            "reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("template", sa.String(100), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, default="pending"),
            sa.Column("format", sa.String(20), nullable=False, default="json"),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("parameters", sa.JSON(), nullable=False, default=dict),
            sa.Column("summary", sa.JSON(), nullable=True),
            sa.Column("findings", sa.JSON(), nullable=True),
            sa.Column("metrics", sa.JSON(), nullable=True),
            sa.Column("charts", sa.JSON(), nullable=True),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("is_scheduled", sa.Boolean(), nullable=False, default=False),
            sa.Column("schedule_cron", sa.String(100), nullable=True),
            sa.Column("schedule_timezone", sa.String(100), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("recipients", sa.JSON(), nullable=False, default=list),
            sa.Column("include_charts", sa.Boolean(), nullable=False, default=True),
            sa.Column("include_findings", sa.Boolean(), nullable=False, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        )
        op.create_index("ix_report_tenant", "reports", ["tenant_id"])
        op.create_index("ix_report_template", "reports", ["template"])
        op.create_index("ix_report_status", "reports", ["status"])
        op.create_index("ix_report_created_at", "reports", ["created_at"])
        op.create_index("ix_report_scheduled", "reports", ["is_scheduled", "next_run_at"])

    # scheduled_reports table - tracks scheduled report runs
    if "scheduled_reports" not in existing_tables:
        op.create_table(
            "scheduled_reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("report_template_key", sa.String(100), nullable=False),
            sa.Column("cron_expression", sa.String(100), nullable=False),
            sa.Column("timezone", sa.String(100), nullable=False, default="UTC"),
            sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("recipients", sa.JSON(), nullable=False, default=list),
            sa.Column("last_status", sa.String(50), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["report_template_key"], ["report_templates.key"]),
        )
        op.create_index("ix_scheduled_report_tenant", "scheduled_reports", ["tenant_id"])
        op.create_index("ix_scheduled_report_active", "scheduled_reports", ["is_active", "next_run_at"])
        op.create_index("ix_scheduled_report_template", "scheduled_reports", ["report_template_key"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_report_template", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_report_active", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_report_tenant", table_name="scheduled_reports")
    op.drop_table("scheduled_reports")

    op.drop_index("ix_report_scheduled", table_name="reports")
    op.drop_index("ix_report_created_at", table_name="reports")
    op.drop_index("ix_report_status", table_name="reports")
    op.drop_index("ix_report_template", table_name="reports")
    op.drop_index("ix_report_tenant", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_report_template_category", table_name="report_templates")
    op.drop_index("ix_report_template_key", table_name="report_templates")
    op.drop_index("ix_report_template_tenant", table_name="report_templates")
    op.drop_table("report_templates")
