"""add meetings

Revision ID: a1c4e8f29b3d
Revises: 9552082cd2c2
Create Date: 2026-11-25 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c4e8f29b3d'
down_revision: Union[str, None] = '9552082cd2c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'meetings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('room_name', sa.String(length=200), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('created_by_id', sa.String(length=100), nullable=False),
        sa.Column('created_by_name', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('room_name'),
    )


def downgrade() -> None:
    op.drop_table('meetings')
