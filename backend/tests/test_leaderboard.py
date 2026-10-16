from app.db.models import User
from app.db.session import build_engine, build_session_factory
from tests.conftest import KARA, KOBE, as_user, make_jpeg, upload


def _board(client, user=KOBE):
    return client.get("/api/v1/leaderboard", headers=as_user(user))


def test_sorted_by_xp_highest_first_with_positions(seeded_client):
    items = _board(seeded_client).json()["items"]
    xps = [i["xp"] for i in items]
    assert xps == sorted(xps, reverse=True)
    assert [i["position"] for i in items] == list(range(1, len(items) + 1))
    first = items[0]
    assert first["user"]["id"] == KARA and first["xp"] == 600
    assert first["rank_name"] == "Gold Verifier" and first["user"]["rank"] == "gold"
    assert items[1]["user"]["id"] == KOBE


def test_reflects_new_xp(seeded_client):
    upload(seeded_client, KOBE, make_jpeg())
    kobe = next(i for i in _board(seeded_client).json()["items"] if i["user"]["id"] == KOBE)
    assert kobe["xp"] == 170


def test_capped_at_fifty(seeded, client):
    engine = build_engine(seeded.database_url)
    with build_session_factory(engine)() as db:
        for n in range(60):
            db.add(User(handle=f"bulk{n}", display_name=f"Bulk {n}", avatar_id=1, xp=n))
        db.commit()
    engine.dispose()
    assert len(_board(client).json()["items"]) == 50


def test_no_private_fields(seeded_client):
    entry = _board(seeded_client).json()["items"][0]
    assert set(entry) == {"position", "user", "xp", "rank_name"}
    assert "password_hash" not in str(entry)


def test_requires_sign_in(seeded_client):
    assert seeded_client.get("/api/v1/leaderboard").status_code == 401
