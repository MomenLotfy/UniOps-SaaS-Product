"""Add detected_by column to vulnerabilities table.

Revision ID: 009_detected_by
Revises: 55a7b04e2fda
Create Date: 2026-06-27

This migration adds the 'detected_by' JSON column to the vulnerabilities table,
which is required by the SQLAlchemy model for tracking multiple scanners.
"""
from alembic import op
import sqlalchemy as sa

revision = "009_detected_by"
down_revision = "55a7b04e2fda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add detected_by, first_seen_at, and last_seen_at columns to vulnerabilities table
    op.add_column("vulnerabilities", sa.Column("detected_by", sa.JSON(), nullable=True))
    op.add_column("vulnerabilities", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vulnerabilities", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("vulnerabilities", "detected_by")
    op.drop_column("vulnerabilities", "first_seen_at")
    op.drop_column("vulnerabilities", "last_seen_at")
