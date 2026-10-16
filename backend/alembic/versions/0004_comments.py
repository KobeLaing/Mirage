"""Comments on posts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

from app.db.base import UTCDateTime

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(500), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_comments"),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], ondelete="CASCADE", name="fk_comments_post_id_posts"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_comments_user_id_users"
        ),
    )
    # A post's comments, oldest first: WHERE post_id = ? ORDER BY created_at.
    op.create_index("ix_comments_post", "comments", ["post_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_comments_post", table_name="comments")
    op.drop_table("comments")
