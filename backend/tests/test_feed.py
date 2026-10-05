from datetime import timedelta

import pytest
from sqlalchemy import event

from app.db.base import utcnow
from app.db.models import Post, User
from app.db.session import build_engine, build_session_factory
from tests.conftest import KOBE, as_user


def test_feed_is_newest_first(seeded_client):
    items = seeded_client.get("/api/v1/posts").json()["items"]
    assert len(items) == 6
    times = [i["created_at"] for i in items]
    assert times == sorted(times, reverse=True)
    assert items[0]["media"]["kind"] == "video" and items[-1]["media"]["kind"] == "image"


def _bulk_posts(settings, count, same_time=False):
    engine = build_engine(settings.database_url)
    with build_session_factory(engine)() as db:
        user = db.get(User, KOBE) or User(handle="bulk", display_name="Bulk", avatar_id=1)
        db.add(user)
        db.flush()
        now = utcnow()
        for i in range(count):
            created = now if same_time else now - timedelta(seconds=i)
            db.add(Post(author_id=user.id, media_key=f"{i:032x}.jpg", media_kind="image",
                        mime_type="image/jpeg", created_at=created))
        db.commit()
    engine.dispose()


@pytest.mark.parametrize("same_time", [False, True])
def test_cursor_pages_cover_everything_once(migrated, client, same_time):
    _bulk_posts(migrated, 23, same_time=same_time)
    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 5} | ({"cursor": cursor} if cursor else {})
        page = client.get("/api/v1/posts", params=params).json()
        seen += [p["id"] for p in page["items"]]
        pages += 1
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert pages == 5
    assert len(seen) == 23 and len(set(seen)) == 23  # no gaps, no duplicates


@pytest.mark.parametrize("cursor", ["garbage!!", "eyJ0IjogMX0", "e30", "a" * 199])
def test_bad_cursor_is_400(seeded_client, cursor):
    r = seeded_client.get("/api/v1/posts", params={"cursor": cursor})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


def test_limit_is_bounded(seeded_client):
    assert seeded_client.get("/api/v1/posts", params={"limit": 51}).status_code == 422
    assert seeded_client.get("/api/v1/posts", params={"limit": 0}).status_code == 422


def _count_queries(app, fn):
    statements = []

    def before(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(app.state.engine, "before_cursor_execute", before)
    try:
        fn()
    finally:
        event.remove(app.state.engine, "before_cursor_execute", before)
    return len(statements)


def test_feed_has_no_n_plus_one(migrated, app, client):
    _bulk_posts(migrated, 1)
    small = _count_queries(app, lambda: client.get("/api/v1/posts", headers=as_user(KOBE)))
    _bulk_posts(migrated, 0)
    engine = build_engine(migrated.database_url)
    with build_session_factory(engine)() as db:
        for i in range(30):
            db.add(Post(author_id=KOBE, media_key=f"{i + 100:032x}.jpg", media_kind="image",
                        mime_type="image/jpeg", created_at=utcnow()))
        db.commit()
    engine.dispose()
    large = _count_queries(app, lambda: client.get("/api/v1/posts?limit=30", headers=as_user(KOBE)))
    assert small == large
    # identity lookup + posts(+authors) + vote counts + reaction counts + my votes + my reactions
    assert large <= 6
