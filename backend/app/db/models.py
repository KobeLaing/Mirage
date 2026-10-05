from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


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
