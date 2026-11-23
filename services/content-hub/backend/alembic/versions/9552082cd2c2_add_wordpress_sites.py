"""add wordpress_sites

Revision ID: 9552082cd2c2
Revises: d2c5f9535dcd
Create Date: 2026-11-23 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9552082cd2c2'
down_revision: Union[str, None] = 'd2c5f9535dcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'wordpress_sites',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('username', sa.String(length=200), nullable=False),
        sa.Column('app_password_enc', sa.Text(), nullable=False),
        sa.Column('created_by_id', sa.String(length=100), nullable=False),
        sa.Column('created_by_name', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('wordpress_sites')
