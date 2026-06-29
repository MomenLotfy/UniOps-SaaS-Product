"""Sprint 2 R24 — create idempotency_records table.

Revision ID: 015_idempotency_records
Revises: 014_sprint2_schema_alignment
Create Date: 2026-06-28

Backs the new ``POST /security/decision-approvals/{id}/actions`` endpoint
which honours the ``Idempotency-Key`` header.  One row per
``(tenant_id, key)`` pair; rows auto-expire after 24 hours (best-effort GC).
"""
from alembic import op
import sqlalchemy as sa


revision = "015_idempotency_records"
down_revision = "014_sprint2_schema_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_idempotency_tenant", "idempotency_records", ["tenant_id"]
    )
    op.create_index(
        "ix_idempotency_key",     "idempotency_records", ["key"]
    )
    op.create_index(
        "ix_idempotency_expires", "idempotency_records", ["expires_at"]
    )
    op.create_unique_constraint(
        "uq_idempotency_tenant_key",
        "idempotency_records",
        ["tenant_id", "key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_idempotency_tenant_key", "idempotency_records", type_="unique")
    op.drop_index("ix_idempotency_expires", table_name="idempotency_records")
    op.drop_index("ix_idempotency_key",      table_name="idempotency_records")
    op.drop_index("ix_idempotency_tenant",   table_name="idempotency_records")
    op.drop_table("idempotency_records")