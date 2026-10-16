"""Authentication: users.password_hash and the sessions table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

from app.db.base import UTCDateTime

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing users get NULL, which means "cannot sign in" until the seed script
    # (or a future password-reset flow) sets a hash.
    # Plain ADD COLUMN, no table rebuild (see 0005 for why that matters).
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_sessions_user_id_users"
        ),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user", table_name="sessions")
    op.drop_table("sessions")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_hash")
