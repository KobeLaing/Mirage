"""Initial schema: users, posts, votes, reactions.

Revision ID: 0001
Revises:
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

from app.db.base import UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("handle", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("avatar_id", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("handle", name="uq_users_handle"),
        sa.CheckConstraint("xp >= 0", name="ck_users_xp_non_negative"),
        sa.CheckConstraint("avatar_id BETWEEN 1 AND 10", name="ck_users_avatar_range"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(500), nullable=True),
        sa.Column("media_key", sa.String(64), nullable=False),
        sa.Column("media_kind", sa.String(8), nullable=False),
        sa.Column("mime_type", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("ground_truth", sa.String(4), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_posts"),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], ondelete="CASCADE", name="fk_posts_author_id_users"
        ),
        sa.UniqueConstraint("media_key", name="uq_posts_media_key"),
        sa.CheckConstraint("media_kind IN ('image', 'video')", name="ck_posts_media_kind"),
        sa.CheckConstraint("ground_truth IN ('AI', 'REAL')", name="ck_posts_ground_truth"),
    )
    # Feed: ORDER BY created_at DESC, id DESC. A composite B-tree index is scanned
    # backwards for DESC order on both SQLite and PostgreSQL.
    op.create_index("ix_posts_feed", "posts", ["created_at", "id"])
    op.create_index("ix_posts_author", "posts", ["author_id", "created_at"])

    op.create_table(
        "votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(4), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_votes"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_votes_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], ondelete="CASCADE", name="fk_votes_post_id_posts"
        ),
        sa.UniqueConstraint("user_id", "post_id", name="uq_votes_user_post"),
        sa.CheckConstraint("value IN ('AI', 'REAL')", name="ck_votes_value"),
    )
    op.create_index("ix_votes_post", "votes", ["post_id"])
    op.create_index("ix_votes_user_recent", "votes", ["user_id", "updated_at"])

    op.create_table(
        "reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_reactions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_reactions_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], ondelete="CASCADE", name="fk_reactions_post_id_posts"
        ),
        sa.UniqueConstraint("user_id", "post_id", name="uq_reactions_user_post"),
        sa.CheckConstraint("kind IN ('heart', 'like', 'laugh')", name="ck_reactions_kind"),
    )
    op.create_index("ix_reactions_post", "reactions", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_reactions_post", table_name="reactions")
    op.drop_table("reactions")
    op.drop_index("ix_votes_user_recent", table_name="votes")
    op.drop_index("ix_votes_post", table_name="votes")
    op.drop_table("votes")
    op.drop_index("ix_posts_author", table_name="posts")
    op.drop_index("ix_posts_feed", table_name="posts")
    op.drop_table("posts")
    op.drop_table("users")
