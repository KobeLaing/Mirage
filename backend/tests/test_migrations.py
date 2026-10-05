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
