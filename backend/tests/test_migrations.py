import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.migrate import alembic_config
from app.db.models import Post, User, Vote, Reaction
from app.db.session import build_engine


def test_upgrade_creates_tables_and_indexes(migrated):
    engine = build_engine(migrated.database_url)
    insp = inspect(engine)
    assert {"users", "posts", "votes", "reactions"} <= set(insp.get_table_names())
    assert "ix_posts_feed" in {ix["name"] for ix in insp.get_indexes("posts")}
    vote_uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("votes")}
    assert ("user_id", "post_id") in vote_uniques
    reaction_uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("reactions")}
    assert ("user_id", "post_id") in reaction_uniques
    engine.dispose()


def test_models_match_migrations(migrated):
    """The hand-written migration and the ORM models must describe the same schema."""
    engine = build_engine(migrated.database_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_downgrade_then_upgrade(migrated):
    cfg = alembic_config(migrated.database_url)
    command.downgrade(cfg, "base")
    engine = build_engine(migrated.database_url)
    assert "posts" not in inspect(engine).get_table_names()
    engine.dispose()
    command.upgrade(cfg, "head")


def test_migrations_never_lose_existing_data(settings):
    """Regression: on SQLite, a migration that rebuilds `users` used to cascade-
    delete every post and vote. Data from the first schema must survive every
    upgrade and every downgrade."""
    import sqlalchemy as sa

    from app.db.base import utcnow

    cfg = alembic_config(settings.database_url, settings.upload_dir)
    command.upgrade(cfg, "0001")
    users = sa.table("users", *(sa.column(c) for c in ("id", "handle", "display_name", "avatar_id", "xp", "created_at")))
    posts = sa.table("posts", *(sa.column(c) for c in ("id", "author_id", "media_key", "media_kind", "mime_type", "created_at")))
    votes = sa.table("votes", *(sa.column(c) for c in ("user_id", "post_id", "value", "created_at", "updated_at")))
    engine = build_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(sa.insert(users).values(id=1, handle="u1", display_name="u1", avatar_id=1, xp=10, created_at=utcnow()))
        conn.execute(sa.insert(posts).values(
            id=1, author_id=1, media_key="c" * 32 + ".jpg", media_kind="image", mime_type="image/jpeg", created_at=utcnow()
        ))
        conn.execute(sa.insert(votes).values(user_id=1, post_id=1, value="AI", created_at=utcnow(), updated_at=utcnow()))

    def counts():
        with engine.connect() as conn:
            return tuple(conn.execute(sa.select(sa.func.count()).select_from(t)).scalar() for t in (users, posts, votes))

    command.upgrade(cfg, "head")
    assert counts() == (1, 1, 1)
    command.downgrade(cfg, "0001")
    assert counts() == (1, 1, 1)
    engine.dispose()


def test_0003_removes_only_the_seed_videos(settings, tmp_path):
    """Old databases lose the seeded videos; a user's own video upload stays."""
    import shutil

    from sqlalchemy import select

    from app.db.session import build_session_factory
    from tests.conftest import SEED_MEDIA

    cfg = alembic_config(settings.database_url, settings.upload_dir)
    command.upgrade(cfg, "0002")  # the state before the cleanup migration
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    seed_key, user_key = "a" * 32 + ".mp4", "b" * 32 + ".mp4"
    shutil.copy(SEED_MEDIA / "ai-video-1.mp4", settings.upload_dir / seed_key)
    user_video = (SEED_MEDIA / "real-video-1.mp4").read_bytes() + b"\x00"  # different bytes, same format
    (settings.upload_dir / user_key).write_bytes(user_video)

    # Core inserts with only the columns that exist at revision 0002 (the ORM
    # models describe the latest schema, which has more columns).
    import sqlalchemy as sa

    from app.db.base import utcnow

    users = sa.table("users", *(sa.column(c) for c in ("id", "handle", "display_name", "avatar_id", "xp", "created_at")))
    posts = sa.table("posts", *(sa.column(c) for c in ("author_id", "media_key", "media_kind", "mime_type", "created_at")))
    engine = build_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(sa.insert(users).values(id=1, handle="u1", display_name="u1", avatar_id=1, xp=0, created_at=utcnow()))
        for key in (seed_key, user_key):
            conn.execute(sa.insert(posts).values(
                author_id=1, media_key=key, media_kind="video", mime_type="video/mp4", created_at=utcnow()
            ))

    command.upgrade(cfg, "head")

    with build_session_factory(engine)() as db:
        assert list(db.scalars(select(Post.media_key))) == [user_key]
    engine.dispose()
    assert not (settings.upload_dir / seed_key).exists()
    assert (settings.upload_dir / user_key).exists()


def _user(db, handle="u1", xp=0):
    user = User(handle=handle, display_name=handle, avatar_id=1, xp=xp)
    db.add(user)
    db.flush()
    return user


def _post(db, author):
    post = Post(author_id=author.id, media_key=f"{author.id:032x}.jpg", media_kind="image", mime_type="image/jpeg")
    db.add(post)
    db.flush()
    return post


def test_db_rejects_duplicate_vote(db):
    user = _user(db)
    post = _post(db, user)
    db.add(Vote(user_id=user.id, post_id=post.id, value="AI"))
    db.flush()
    db.add(Vote(user_id=user.id, post_id=post.id, value="REAL"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_db_rejects_duplicate_reaction(db):
    user = _user(db)
    post = _post(db, user)
    db.add(Reaction(user_id=user.id, post_id=post.id, kind="heart"))
    db.flush()
    db.add(Reaction(user_id=user.id, post_id=post.id, kind="laugh"))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "factory",
    [
        lambda db, u, p: Vote(user_id=u.id, post_id=p.id, value="MAYBE"),
        lambda db, u, p: Reaction(user_id=u.id, post_id=p.id, kind="angry"),
        lambda db, u, p: Vote(user_id=u.id, post_id=99999, value="AI"),  # foreign key
    ],
)
def test_db_check_and_fk_constraints(db, factory):
    user = _user(db)
    post = _post(db, user)
    db.add(factory(db, user, post))
    with pytest.raises(IntegrityError):
        db.flush()


def test_db_rejects_negative_xp_and_bad_avatar(db):
    db.add(User(handle="neg", display_name="neg", avatar_id=1, xp=-5))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    db.add(User(handle="av", display_name="av", avatar_id=11, xp=0))
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_post_cascades_votes(db):
    user = _user(db)
    post = _post(db, user)
    db.add(Vote(user_id=user.id, post_id=post.id, value="AI"))
    db.flush()
    db.delete(post)
    db.flush()
    db.expire_all()
    assert db.query(Vote).count() == 0
