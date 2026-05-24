"""Cost module fixes: savings default status, last_sync_at on integrations.

Revision ID: 006_cost_fixes
Revises: 005
Create Date: 2025-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "006_cost_fixes"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Fix savings default status: "open" → "pending" ───────────────────
    op.alter_column(
        "savings",
        "status",
        existing_type=sa.String(50),
        server_default="pending",
        existing_nullable=True,
    )
    # Back-fill existing rows that have "open" so Apply buttons appear
    op.execute("UPDATE savings SET status = 'pending' WHERE status = 'open'")

    # ── 2. Add last_sync_at to integrations (if not exists) ─────────────────
    conn = op.get_bind()
    cols = [row[1] for row in conn.execute(sa.text("PRAGMA table_info(integrations)")).fetchall()] \
        if conn.dialect.name == "sqlite" else \
        [row[0] for row in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='integrations'"
        )).fetchall()]

    if "last_sync_at" not in cols:
        op.add_column(
            "integrations",
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── 3. cost_anomalies: add root_cause + recommendation columns ───────────
    anomaly_cols = cols  # reuse pattern
    # Re-fetch for cost_anomalies
    if conn.dialect.name == "postgresql":
        ca_cols = [row[0] for row in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='cost_anomalies'"
        )).fetchall()]
    else:
        ca_cols = [row[1] for row in conn.execute(
            sa.text("PRAGMA table_info(cost_anomalies)")
        ).fetchall()]

    if "root_cause" not in ca_cols:
        op.add_column(
            "cost_anomalies",
            sa.Column("root_cause", sa.Text, nullable=True),
        )
    if "recommendation" not in ca_cols:
        op.add_column(
            "cost_anomalies",
            sa.Column("recommendation", sa.Text, nullable=True),
        )


def downgrade() -> None:
    op.alter_column(
        "savings", "status",
        existing_type=sa.String(50),
        server_default="open",
    )
    op.execute("UPDATE savings SET status = 'open' WHERE status = 'pending'")
