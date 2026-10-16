from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow

VOTE_VALUES = ("AI", "REAL")
REACTION_KINDS = ("heart", "like", "laugh")
MEDIA_KINDS = ("image", "video")
AVATAR_COUNT = 10


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)  # static constants only, never user input
    return f"{column} IN ({quoted})"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("xp >= 0", name="xp_non_negative"),
        CheckConstraint(f"avatar_id BETWEEN 1 AND {AVATAR_COUNT}", name="avatar_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    avatar_id: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    # Argon2id hash (includes its own salt and cost settings). NULL means the
    # account has no password and cannot sign in. Never add this to a response schema.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Blind Mode preference, stored server-side so it follows the user to every device.
    blind_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class UserSession(Base):
    """One signed-in browser. The cookie holds a signed random secret; this table
    stores only its SHA-256, so a leaked database can't be replayed as cookies.
    Keeping sessions server-side is what makes logout real: revoking the row
    kills the cookie even though its signature is still valid."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 hex of the secret
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(_in("media_kind", MEDIA_KINDS), name="media_kind"),
        CheckConstraint(_in("ground_truth", VOTE_VALUES), name="ground_truth"),
        Index("ix_posts_feed", "created_at", "id"),
        Index("ix_posts_author", "author_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    caption: Mapped[str | None] = mapped_column(String(500))
    media_key: Mapped[str] = mapped_column(String(64), unique=True)
    media_kind: Mapped[str] = mapped_column(String(8))
    mime_type: Mapped[str] = mapped_column(String(32))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    # HIDDEN. Never add this to a response schema (SR-17).
    ground_truth: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    author: Mapped[User] = relationship(lazy="raise")


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_votes_user_post"),
        CheckConstraint(_in("value", VOTE_VALUES), name="value"),
        Index("ix_votes_post", "post_id"),
        Index("ix_votes_user_recent", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_post", "post_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Stored exactly as typed (after trimming) and always rendered as plain text.
    body: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    author: Mapped[User] = relationship(lazy="raise")


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_reactions_user_post"),
        CheckConstraint(_in("kind", REACTION_KINDS), name="kind"),
        Index("ix_reactions_post", "post_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
