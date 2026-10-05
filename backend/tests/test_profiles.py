import pytest

from tests.conftest import KARA, KOBE, as_user, make_jpeg, upload


def test_seeded_profiles(seeded_client):
    kobe = seeded_client.get(f"/api/v1/users/{KOBE}").json()
    assert kobe["display_name"] == "Kobe Laing"
    assert kobe["xp"] == 150
    assert kobe["rank"] == {"key": "silver", "name": "Silver Verifier", "min_xp": 100}
    assert kobe["next_rank"]["key"] == "gold"
    assert kobe["progress"] == 0.25

    kara = seeded_client.get(f"/api/v1/users/{KARA}").json()
    assert kara["rank"]["name"] == "Gold Verifier"
    assert kara["next_rank"]["name"] == "Platinum Verifier"
    assert kara["progress"] == 0.75


def test_unknown_profile_404(seeded_client):
    assert seeded_client.get("/api/v1/users/999").status_code == 404
    assert seeded_client.get("/api/v1/users/999/activity").status_code == 404


def test_user_list_for_switcher(seeded_client):
    users = seeded_client.get("/api/v1/users").json()
    assert [(u["handle"], u["rank"]) for u in users] == [("Kobe", "silver"), ("KaraM", "gold")]


def test_change_own_avatar(seeded_client):
    r = seeded_client.put("/api/v1/me/avatar", headers=as_user(KOBE), json={"avatar_id": 9})
    assert r.status_code == 200
    assert r.json()["avatar_id"] == 9
    assert seeded_client.get(f"/api/v1/users/{KOBE}").json()["avatar_id"] == 9
    assert seeded_client.get(f"/api/v1/users/{KARA}").json()["avatar_id"] == 7  # untouched


@pytest.mark.parametrize("avatar_id", [0, 11, -1, "1; DROP TABLE users", None])
def test_avatar_must_be_one_of_ten(seeded_client, avatar_id):
    r = seeded_client.put("/api/v1/me/avatar", headers=as_user(KOBE), json={"avatar_id": avatar_id})
    assert r.status_code == 422


def test_cannot_change_someone_elses_avatar(seeded_client, app):
    # No route accepts a target user for this write...
    paths = app.openapi()["paths"]
    assert "put" not in paths.get("/api/v1/users/{user_id}", {})
    assert seeded_client.put(f"/api/v1/users/{KARA}/avatar", headers=as_user(KOBE), json={"avatar_id": 2}).status_code in (404, 405)
    # ...and smuggling one into the body is rejected.
    r = seeded_client.put("/api/v1/me/avatar", headers=as_user(KOBE), json={"avatar_id": 2, "user_id": KARA})
    assert r.status_code == 422
    assert seeded_client.get(f"/api/v1/users/{KARA}").json()["avatar_id"] == 7


def test_avatar_requires_a_user(seeded_client):
    assert seeded_client.put("/api/v1/me/avatar", json={"avatar_id": 2}).status_code == 401


def test_activity_lists_votes_with_labels_and_own_posts(seeded_client):
    # Kobe votes on two of Kara's posts (seed posts 2 and 4 are Kara's).
    seeded_client.put("/api/v1/posts/2/vote", headers=as_user(KOBE), json={"value": "AI"})
    seeded_client.put("/api/v1/posts/4/vote", headers=as_user(KOBE), json={"value": "REAL"})
    # And on one of her own posts (post 1).
    seeded_client.put("/api/v1/posts/1/vote", headers=as_user(KOBE), json={"value": "REAL"})

    items = seeded_client.get(f"/api/v1/users/{KOBE}/activity").json()["items"]
    voted = {i["post"]["id"]: i["vote"] for i in items if i["type"] == "voted"}
    posted = {i["post"]["id"]: i["vote"] for i in items if i["type"] == "posted"}
    assert voted == {2: "AI", 4: "REAL"}
    assert posted == {1: "REAL", 3: None, 5: None}  # her three seeded posts, no duplicates
    times = [i["at"] for i in items]
    assert times == sorted(times, reverse=True)
    # Votes are dated by when they were cast, own posts by when they were posted,
    # so the vote just cast on post 4 is the most recent item.
    assert items[0]["post"]["id"] == 4


def test_activity_my_vote_reflects_the_viewer(seeded_client):
    seeded_client.put("/api/v1/posts/2/vote", headers=as_user(KOBE), json={"value": "AI"})
    item = seeded_client.get(f"/api/v1/users/{KOBE}/activity", headers=as_user(KARA)).json()["items"][0]
    assert item["vote"] == "AI"  # how Kobe voted (the profile owner)
    assert item["post"]["my_vote"] is None  # Kara, the viewer, hasn't voted


def test_activity_limit(seeded_client):
    for _ in range(3):
        upload(seeded_client, KOBE, make_jpeg())
    assert len(seeded_client.get(f"/api/v1/users/{KOBE}/activity?limit=2").json()["items"]) == 2
    assert seeded_client.get(f"/api/v1/users/{KOBE}/activity?limit=51").status_code == 422


def test_profile_reflects_xp_changes(seeded_client):
    seeded_client.put("/api/v1/posts/2/vote", headers=as_user(KOBE), json={"value": "AI"})
    upload(seeded_client, KOBE, make_jpeg())
    me = seeded_client.get("/api/v1/me", headers=as_user(KOBE)).json()
    assert me["xp"] == 150 + 10 + 25
    assert me["progress"] == pytest.approx((185 - 100) / 200)


def test_xp_cannot_be_set_through_any_endpoint(seeded_client, app):
    """No request schema exposes an xp/rank field (SR-20)."""
    schemas = app.openapi()["components"]["schemas"]
    for name, schema in schemas.items():
        if name.endswith("In") or name in ("AvatarUpdate",) or name.startswith("Body_"):
            props = set(schema.get("properties", {}))
            assert not props & {"xp", "rank", "votes", "reactions", "ground_truth"}, name
