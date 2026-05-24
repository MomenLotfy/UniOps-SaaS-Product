"""Add repositories and scans tables for DevSecOps scan engine.

Revision ID: 005
Revises: 004
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── repositories ──────────────────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id",               sa.String(36),  primary_key=True),
        sa.Column("tenant_id",        sa.String(36),  sa.ForeignKey("tenants.id"),       nullable=False),
        sa.Column("integration_id",   sa.String(36),  sa.ForeignKey("integrations.id")),
        sa.Column("provider",         sa.String(50),  nullable=False),
        sa.Column("external_id",      sa.String(255), nullable=False),
        sa.Column("full_name",        sa.String(500), nullable=False),
        sa.Column("name",             sa.String(255), nullable=False),
        sa.Column("clone_url",        sa.Text),
        sa.Column("default_branch",   sa.String(255), server_default="main"),
        sa.Column("is_private",       sa.Boolean,     server_default=sa.text("true")),
        sa.Column("language",         sa.String(100)),
        sa.Column("has_dockerfile",   sa.Boolean,     server_default=sa.text("false")),
        sa.Column("has_cicd",         sa.Boolean,     server_default=sa.text("false")),
        sa.Column("last_scan_at",     sa.DateTime(timezone=True)),
        sa.Column("last_scan_score",  sa.Float),
        sa.Column("created_at",       sa.DateTime(timezone=True)),
        sa.Column("updated_at",       sa.DateTime(timezone=True)),
    )
    op.create_index("ix_repositories_tenant_id",  "repositories", ["tenant_id"])
    op.create_index("ix_repositories_full_name",  "repositories", ["full_name"])

    # ── scans ─────────────────────────────────────────────────────────────────
    op.create_table(
        "scans",
        sa.Column("id",               sa.String(36),  primary_key=True),
        sa.Column("tenant_id",        sa.String(36),  sa.ForeignKey("tenants.id"),        nullable=False),
        sa.Column("repo_id",          sa.String(36),  sa.ForeignKey("repositories.id"),   nullable=False),
        sa.Column("triggered_by",     sa.String(36),  sa.ForeignKey("users.id")),
        sa.Column("branch",           sa.String(255), server_default="main"),
        sa.Column("commit_sha",       sa.String(40)),
        sa.Column("status",           sa.String(50),  server_default="queued"),
        sa.Column("error_message",    sa.Text),
        sa.Column("started_at",       sa.DateTime(timezone=True)),
        sa.Column("completed_at",     sa.DateTime(timezone=True)),
        sa.Column("duration_secs",    sa.Integer),
        sa.Column("scanners_run",     sa.JSON,        server_default="{}"),
        sa.Column("critical_count",   sa.Integer,     server_default="0"),
        sa.Column("high_count",       sa.Integer,     server_default="0"),
        sa.Column("medium_count",     sa.Integer,     server_default="0"),
        sa.Column("low_count",        sa.Integer,     server_default="0"),
        sa.Column("secret_count",     sa.Integer,     server_default="0"),
        sa.Column("misconfig_count",  sa.Integer,     server_default="0"),
        sa.Column("security_score",   sa.Float),
        sa.Column("ai_summary",       sa.Text),
        sa.Column("ai_suggestions",   sa.JSON,        server_default="[]"),
        sa.Column("raw_results",      sa.JSON,        server_default="{}"),
        sa.Column("created_at",       sa.DateTime(timezone=True)),
        sa.Column("updated_at",       sa.DateTime(timezone=True)),
    )
    op.create_index("ix_scans_tenant_id", "scans", ["tenant_id"])
    op.create_index("ix_scans_repo_id",   "scans", ["repo_id"])
    op.create_index("ix_scans_status",    "scans", ["status"])

    # ── Add scan_id FK to threats and vulnerabilities (for traceability) ──────
    op.add_column("threats",         sa.Column("scan_id", sa.String(36), nullable=True))
    op.add_column("vulnerabilities", sa.Column("scan_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("vulnerabilities", "scan_id")
    op.drop_column("threats",         "scan_id")
    op.drop_index("ix_scans_status",    "scans")
    op.drop_index("ix_scans_repo_id",   "scans")
    op.drop_index("ix_scans_tenant_id", "scans")
    op.drop_table("scans")
    op.drop_index("ix_repositories_full_name",  "repositories")
    op.drop_index("ix_repositories_tenant_id",  "repositories")
    op.drop_table("repositories")
