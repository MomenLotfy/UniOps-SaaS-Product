"""Add rejection_count to security_decision_strategy_statistics.

Revision ID: 013_strategy_rejection_count
Revises: 012_execution_orchestration_tables
Create Date: 2026-06-28

Sprint 1 stabilization: R9 — DecisionStrategyStatistics was missing
`rejection_count`, causing DecisionStrategyStatisticsService.record_rejection
to raise AttributeError on first call.  Add the column with default 0.
"""
from alembic import op
import sqlalchemy as sa


revision = "013_strategy_rejection_count"
down_revision = "012_execution_orchestration_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "security_decision_strategy_statistics",
        sa.Column(
            "rejection_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("security_decision_strategy_statistics", "rejection_count")