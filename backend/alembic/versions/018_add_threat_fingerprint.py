"""Add threat dedup columns.

Revision ID: 018_add_threat_fingerprint
Revises: 017_add_report_tables
Create Date: 2026-07-04

Adds the columns required to deduplicate threats across scan runs:

  - fingerprint       : sha256(tenant_id|repo_id|scanner|rule_id|file|line)
  - occurrence_count  : how many scans have observed this finding
  - first_seen_at     : when the fingerprint was first inserted
  - last_seen_at      : when the fingerprint was most recently observed

Without these columns the run_scan task creates a fresh Threat row for every
finding on every scan, leading to unbounded growth and a history chart that
swamps real signal with duplicates.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "018_add_threat_fingerprint"
down_revision = "017_add_report_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("threats")}

    if "fingerprint" not in cols:
        op.add_column("threats", sa.Column("fingerprint", sa.String(64), nullable=True))
        op.create_index("ix_threats_fingerprint", "threats", ["fingerprint"])

    if "occurrence_count" not in cols:
        op.add_column(
            "threats",
            sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        )

    if "first_seen_at" not in cols:
        op.add_column(
            "threats",
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "last_seen_at" not in cols:
        op.add_column(
            "threats",
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Composite index that powers _upsert_threat lookups
    op.create_index(
        "ix_threats_tenant_repo_fingerprint",
        "threats",
        ["tenant_id", "repo_id", "fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_threats_tenant_repo_fingerprint", table_name="threats")
    op.drop_index("ix_threats_fingerprint", table_name="threats")
    op.drop_column("threats", "last_seen_at")
    op.drop_column("threats", "first_seen_at")
    op.drop_column("threats", "occurrence_count")
    op.drop_column("threats", "fingerprint")
