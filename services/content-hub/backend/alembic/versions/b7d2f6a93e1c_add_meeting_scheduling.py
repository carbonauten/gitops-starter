"""add meeting scheduling

Revision ID: b7d2f6a93e1c
Revises: a1c4e8f29b3d
Create Date: 2026-11-25 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d2f6a93e1c'
down_revision: Union[str, None] = 'a1c4e8f29b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('meetings', sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meetings', sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='30'))


def downgrade() -> None:
    op.drop_column('meetings', 'duration_minutes')
    op.drop_column('meetings', 'scheduled_at')
