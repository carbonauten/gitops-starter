"""add document_signatures

Revision ID: c4f3a8e1b6d2
Revises: b7d2f6a93e1c
Create Date: 2026-11-27 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f3a8e1b6d2'
down_revision: Union[str, None] = 'b7d2f6a93e1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_signatures',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('file_asset_id', sa.String(length=36), nullable=False),
        sa.Column('signed_file_asset_id', sa.String(length=36), nullable=True),
        sa.Column('documenso_envelope_id', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('signer_email', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('signer_name', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('signing_token', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_document_signatures_file_asset_id', 'document_signatures', ['file_asset_id']
    )
    op.create_index(
        'ix_document_signatures_documenso_envelope_id', 'document_signatures', ['documenso_envelope_id']
    )


def downgrade() -> None:
    op.drop_index('ix_document_signatures_documenso_envelope_id', table_name='document_signatures')
    op.drop_index('ix_document_signatures_file_asset_id', table_name='document_signatures')
    op.drop_table('document_signatures')
