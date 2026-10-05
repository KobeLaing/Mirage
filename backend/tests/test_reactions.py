import pytest

from tests.conftest import KARA, KOBE, as_user

POST = 2


def react(client, user, kind, post=POST):
    return client.put(f"/api/v1/posts/{post}/reaction", headers=as_user(user), json={"kind": kind})


def unreact(client, user, post=POST):
    return client.delete(f"/api/v1/posts/{post}/reaction", headers=as_user(user))


def test_react_change_and_remove(seeded_client):
    r = react(seeded_client, KOBE, "heart")
    assert r.status_code == 200
    assert r.json() == {"post_id": POST, "my_reaction": "heart", "reactions": {"heart": 1, "like": 0, "laugh": 0}}

    r = react(seeded_client, KOBE, "laugh")  # change, still one reaction
    assert r.json()["reactions"] == {"heart": 0, "like": 0, "laugh": 1}

    r = unreact(seeded_client, KOBE)
    assert r.json()["my_reaction"] is None
    assert r.json()["reactions"] == {"heart": 0, "like": 0, "laugh": 0}


def test_repeat_reaction_is_idempotent(seeded_client):
    for _ in range(4):
        r = react(seeded_client, KOBE, "like")
    assert r.json()["reactions"]["like"] == 1


def test_reactions_do_not_award_xp(seeded_client):
    react(seeded_client, KOBE, "heart")
    react(seeded_client, KOBE, "like")
    unreact(seeded_client, KOBE)
    assert seeded_client.get("/api/v1/me", headers=as_user(KOBE)).json()["xp"] == 150


def test_users_cannot_touch_each_others_reactions(seeded_client):
    react(seeded_client, KOBE, "heart")
    unreact(seeded_client, KARA)
    r = react(seeded_client, KARA, "laugh")
    assert r.json()["reactions"] == {"heart": 1, "like": 0, "laugh": 1}
    r = seeded_client.put(
        f"/api/v1/posts/{POST}/reaction", headers=as_user(KARA), json={"kind": "like", "user_id": KOBE}
    )
    assert r.status_code == 422


@pytest.mark.parametrize("kind", ["angry", "HEART", "", "wow"])
def test_unknown_reaction_kind_is_422(seeded_client, kind):
    assert react(seeded_client, KOBE, kind).status_code == 422


def test_reaction_on_missing_post_is_404(seeded_client):
    assert react(seeded_client, KOBE, "heart", post=9999).status_code == 404


def test_reaction_rate_limit(seeded, app, client):
    app.state.settings.rate_limit_reactions_per_minute = 2
    assert react(client, KOBE, "heart").status_code == 200
    assert react(client, KOBE, "like").status_code == 200
    assert react(client, KOBE, "laugh").status_code == 429


def test_feed_includes_reaction_counts_and_mine(seeded_client):
    react(seeded_client, KOBE, "laugh")
    react(seeded_client, KARA, "laugh")
    posts = {p["id"]: p for p in seeded_client.get("/api/v1/posts", headers=as_user(KOBE)).json()["items"]}
    assert posts[POST]["reactions"]["laugh"] == 2
    assert posts[POST]["my_reaction"] == "laugh"
