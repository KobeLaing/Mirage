"""Blind Mode: a per-user setting, off by default.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A plain ADD COLUMN (not batch mode): SQLite can do this in place. Batch
    # mode would rebuild the users table, and dropping the old copy cascades
    # ON DELETE to every post and vote.
    op.add_column("users", sa.Column("blind_mode", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("blind_mode")
