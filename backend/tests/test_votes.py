"""Voting rules (FR-20..24, FR-52), the vote+XP transaction (NFR-3), and authorization (SR-11)."""

import pytest
from sqlalchemy import func, select

from app.db.models import User, Vote
from app.db.session import build_engine, build_session_factory
from app.repositories import vote_repo
from tests.conftest import FRONTEND_ORIGIN, KARA, KOBE, as_user

POST = 1


def vote(client, user, value, post=POST):
    return client.put(f"/api/v1/posts/{post}/vote", headers=as_user(user), json={"value": value})


def unvote(client, user, post=POST):
    return client.delete(f"/api/v1/posts/{post}/vote", headers=as_user(user))


def xp(client, user):
    return client.get("/api/v1/me", headers=as_user(user)).json()["xp"]


def db_rows(settings):
    engine = build_engine(settings.database_url)
    with build_session_factory(engine)() as db:
        # Only the post under test: the seed adds votes on other posts.
        rows = db.execute(select(Vote.user_id, Vote.post_id, Vote.value).where(Vote.post_id == POST)).all()
        xps = dict(db.execute(select(User.id, User.xp)).all())
    engine.dispose()
    return rows, xps


def test_first_vote_counts_and_awards_xp(seeded_client):
    r = vote(seeded_client, KOBE, "AI")
    assert r.status_code == 200
    body = r.json()
    assert body["my_vote"] == "AI"
    assert body["votes"] == {"ai": 1, "real": 0}
    assert body["me"] == {"xp": 160, "rank": "silver"}


def test_repeating_the_same_vote_does_not_double_count(seeded_client, seeded):
    for _ in range(5):
        r = vote(seeded_client, KOBE, "REAL")
        assert r.status_code == 200
    assert r.json()["votes"] == {"ai": 0, "real": 1}
    assert xp(seeded_client, KOBE) == 160
    rows, _ = db_rows(seeded)
    assert rows == [(KOBE, POST, "REAL")]


def test_one_vote_per_user_per_post_and_mutually_exclusive(seeded_client, seeded):
    vote(seeded_client, KOBE, "AI")
    vote(seeded_client, KOBE, "REAL")
    rows, _ = db_rows(seeded)
    assert rows == [(KOBE, POST, "REAL")]  # one row, latest choice


def test_switching_moves_counts_without_changing_xp(seeded_client):
    vote(seeded_client, KOBE, "AI")
    r = vote(seeded_client, KOBE, "REAL")
    assert r.json()["votes"] == {"ai": 0, "real": 1}
    assert r.json()["my_vote"] == "REAL"
    assert r.json()["me"]["xp"] == 160
    r = vote(seeded_client, KOBE, "AI")
    assert r.json()["votes"] == {"ai": 1, "real": 0}
    assert r.json()["me"]["xp"] == 160


def test_removing_a_vote_removes_its_xp(seeded_client):
    vote(seeded_client, KOBE, "AI")
    r = unvote(seeded_client, KOBE)
    assert r.status_code == 200
    assert r.json()["my_vote"] is None
    assert r.json()["votes"] == {"ai": 0, "real": 0}
    assert r.json()["me"]["xp"] == 150


def test_removing_twice_is_harmless(seeded_client):
    vote(seeded_client, KOBE, "AI")
    unvote(seeded_client, KOBE)
    r = unvote(seeded_client, KOBE)
    assert r.status_code == 200
    assert r.json()["me"]["xp"] == 150
    # Removing a vote you never cast doesn't take XP either.
    assert unvote(seeded_client, KARA).json()["me"]["xp"] == 600


def test_vote_toggle_farming_nets_zero(seeded_client):
    for _ in range(10):
        vote(seeded_client, KOBE, "AI")
        unvote(seeded_client, KOBE)
    assert xp(seeded_client, KOBE) == 150


def test_votes_from_different_users_are_counted_separately(seeded_client):
    vote(seeded_client, KOBE, "AI")
    r = vote(seeded_client, KARA, "AI")
    assert r.json()["votes"] == {"ai": 2, "real": 0}
    r = vote(seeded_client, KARA, "REAL")
    assert r.json()["votes"] == {"ai": 1, "real": 1}


def test_vote_crosses_rank_threshold(seeded_client, seeded):
    engine = build_engine(seeded.database_url)
    with build_session_factory(engine)() as db:
        db.get(User, KOBE).xp = 295
        db.commit()
    engine.dispose()
    r = vote(seeded_client, KOBE, "AI")
    assert r.json()["me"] == {"xp": 305, "rank": "gold"}
    r = unvote(seeded_client, KOBE)
    assert r.json()["me"] == {"xp": 295, "rank": "silver"}


def test_feed_shows_my_vote_per_user(seeded_client):
    vote(seeded_client, KOBE, "AI")
    posts = {p["id"]: p for p in seeded_client.get("/api/v1/posts", headers=as_user(KOBE)).json()["items"]}
    assert posts[POST]["my_vote"] == "AI" and posts[POST]["votes"]["ai"] == 1
    posts = {p["id"]: p for p in seeded_client.get("/api/v1/posts", headers=as_user(KARA)).json()["items"]}
    assert posts[POST]["my_vote"] is None and posts[POST]["votes"]["ai"] == 1


def test_concurrent_insert_race_counts_once(seeded_client, seeded, monkeypatch):
    """Simulate losing a race: another request inserts the vote between our read and insert."""
    real_get = vote_repo.get
    calls = {"n": 0}

    def racing_get(db, user_id, post_id):
        calls["n"] += 1
        if calls["n"] == 1:
            engine = build_engine(seeded.database_url)
            with build_session_factory(engine)() as other:
                other.add(Vote(user_id=user_id, post_id=post_id, value="AI"))
                other.query(User).filter(User.id == user_id).update({User.xp: User.xp + 10})
                other.commit()
            engine.dispose()
            return None  # we didn't see it yet
        return real_get(db, user_id, post_id)

    monkeypatch.setattr(vote_repo, "get", racing_get)
    r = vote(seeded_client, KOBE, "REAL")
    assert r.status_code == 200
    rows, xps = db_rows(seeded)
    assert rows == [(KOBE, POST, "REAL")]
    assert xps[KOBE] == 160  # +10 once (by the winner), not twice


def test_missing_post_is_404(seeded_client):
    assert vote(seeded_client, KOBE, "AI", post=9999).status_code == 404
    assert unvote(seeded_client, KOBE, post=9999).status_code == 404


@pytest.mark.parametrize("payload", [{"value": "MAYBE"}, {"value": "ai"}, {}, {"value": None}])
def test_invalid_vote_value_is_422(seeded_client, payload):
    r = seeded_client.put(f"/api/v1/posts/{POST}/vote", headers=as_user(KOBE), json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_voting_requires_a_user(seeded_client):
    r = seeded_client.put(f"/api/v1/posts/{POST}/vote", json={"value": "AI"}, headers={"Origin": FRONTEND_ORIGIN})
    assert r.status_code == 401


# --- SR-11 / AC-6: one user cannot change another user's vote ----------------

def test_user_cannot_change_another_users_vote(seeded_client, seeded):
    vote(seeded_client, KOBE, "AI")
    # Kara acting on the same post only ever affects Kara's own vote.
    vote(seeded_client, KARA, "REAL")
    unvote(seeded_client, KARA)
    rows, xps = db_rows(seeded)
    assert rows == [(KOBE, POST, "AI")]
    assert xps[KOBE] == 160 and xps[KARA] == 600


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "REAL", "user_id": KOBE},
        {"value": "REAL", "voter_id": KOBE},
        {"value": "REAL", "xp": 99999},
    ],
)
def test_body_cannot_name_another_user_or_set_xp(seeded_client, seeded, payload):
    vote(seeded_client, KOBE, "AI")
    r = seeded_client.put(f"/api/v1/posts/{POST}/vote", headers=as_user(KARA), json=payload)
    assert r.status_code == 422  # extra fields are rejected outright (SR-20)
    rows, xps = db_rows(seeded)
    assert rows == [(KOBE, POST, "AI")]
    assert xps[KARA] == 600


def test_query_string_cannot_name_another_user(seeded_client, seeded):
    vote(seeded_client, KOBE, "AI")
    seeded_client.delete(f"/api/v1/posts/{POST}/vote?user_id={KOBE}", headers=as_user(KARA))
    rows, _ = db_rows(seeded)
    assert rows == [(KOBE, POST, "AI")]


def test_vote_rate_limit(seeded, app, client):
    app.state.settings.rate_limit_votes_per_minute = 3
    for value in ("AI", "REAL", "AI"):
        assert vote(client, KOBE, value).status_code == 200
    r = vote(client, KOBE, "REAL")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert vote(client, KARA, "AI").status_code == 200  # per user


def test_vote_and_xp_roll_back_together(seeded_client, seeded, monkeypatch):
    """If the XP update fails, the vote must not be saved either."""
    from app.repositories import user_repo

    def boom(*args, **kwargs):
        raise RuntimeError("xp store unavailable")

    monkeypatch.setattr(user_repo, "add_xp", boom)
    r = vote(seeded_client, KOBE, "AI")
    assert r.status_code == 500
    rows, xps = db_rows(seeded)
    assert rows == [] and xps[KOBE] == 150


def test_db_has_exactly_one_row_after_many_mixed_requests(seeded_client, seeded):
    for value in ("AI", "AI", "REAL", "AI", "REAL", "REAL"):
        vote(seeded_client, KOBE, value)
    engine = build_engine(seeded.database_url)
    with build_session_factory(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Vote).where(Vote.post_id == POST)) == 1
    engine.dispose()
    assert xp(seeded_client, KOBE) == 160
