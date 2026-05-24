"""Fix scan/repository timestamp columns to use TIMESTAMPTZ.

started_at, completed_at (scans) and last_scan_at (repositories) were
created as TIMESTAMP WITHOUT TIME ZONE but the application writes
timezone-aware datetimes (datetime.now(timezone.utc)).  asyncpg rejects
the mismatch, causing every scan to crash on the first db.flush() and
remain stuck in 'queued' status forever.

Revision ID: 007
Revises: 006
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006_cost_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "scans", "started_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "scans", "completed_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "repositories", "last_scan_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        postgresql_using="last_scan_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "repositories", "last_scan_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="last_scan_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "scans", "completed_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "scans", "started_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
