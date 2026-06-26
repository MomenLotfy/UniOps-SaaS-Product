"""add_copilot_tables

Revision ID: 55a7b04e2fda
Revises: 008_repo_isolation
Create Date: 2026-06-26 09:56:02.354612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '55a7b04e2fda'
down_revision: Union[str, None] = '008_repo_isolation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_conversations',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False, index=True),
        sa.Column('user_id', sa.String(length=36), nullable=False, index=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_foreign_key('fk_conv_tenant', 'copilot_conversations', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key('fk_conv_user', 'copilot_conversations', 'users', ['user_id'], ['id'])

    op.create_table(
        'copilot_messages',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), nullable=False, index=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('token_usage', sa.Integer(), nullable=True),
        sa.Column('latency', sa.Float(), nullable=True),
        sa.Column('context_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_foreign_key('fk_msg_conv', 'copilot_messages', 'copilot_conversations', ['conversation_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_table('copilot_messages')
    op.drop_table('copilot_conversations')
