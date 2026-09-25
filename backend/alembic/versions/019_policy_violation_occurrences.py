"""Track recurring policy violations without duplicating active rows.

Revision ID: 019_policy_violation_occurrences
Revises: 018_add_threat_fingerprint
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "019_policy_violation_occurrences"
down_revision = "018_add_threat_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("policy_violations")}

    if "occurrence_count" not in columns:
        op.add_column(
            "policy_violations",
            sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        )
    if "first_seen_at" not in columns:
        op.add_column(
            "policy_violations",
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "last_seen_at" not in columns:
        op.add_column(
            "policy_violations",
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("policy_violations")}

    if "last_seen_at" in columns:
        op.drop_column("policy_violations", "last_seen_at")
    if "first_seen_at" in columns:
        op.drop_column("policy_violations", "first_seen_at")
    if "occurrence_count" in columns:
        op.drop_column("policy_violations", "occurrence_count")