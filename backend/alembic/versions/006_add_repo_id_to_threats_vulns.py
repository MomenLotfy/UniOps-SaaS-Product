"""Add repo_id to threats and vulnerabilities for per-repo data isolation.

Revision ID: 008_repo_isolation
Revises: 007
Create Date: 2026-05-24

Without repo_id on these tables, every query returns findings mixed across ALL
repositories for the tenant. This migration adds the column (nullable so
existing rows are unaffected) and an index for efficient filtering.
"""
from alembic import op
import sqlalchemy as sa

revision = "008_repo_isolation"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── threats.repo_id ───────────────────────────────────────────────────────
    op.add_column("threats", sa.Column("repo_id", sa.String(36), nullable=True))
    op.create_index("ix_threats_repo_id", "threats", ["repo_id"])

    # ── vulnerabilities.repo_id ───────────────────────────────────────────────
    op.add_column("vulnerabilities", sa.Column("repo_id", sa.String(36), nullable=True))
    op.create_index("ix_vulnerabilities_repo_id", "vulnerabilities", ["repo_id"])


def downgrade() -> None:
    op.drop_index("ix_vulnerabilities_repo_id", "vulnerabilities")
    op.drop_column("vulnerabilities", "repo_id")

    op.drop_index("ix_threats_repo_id", "threats")
    op.drop_column("threats", "repo_id")
