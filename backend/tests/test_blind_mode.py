"""Blind Mode is enforced by the API: nothing about the crowd's opinion on a
post is sent until the user has voted on it."""

from tests.conftest import JOSIE, KARA, KOBE, as_user, make_jpeg, upload

# Post 2 is Kara's (seeded). Kobe hasn't voted on it.
POST = 2
SECRET_COMMENT = "the-hidden-comment-text"


def _enable(client, user=KOBE, enabled=True):
    r = client.put("/api/v1/me/blind-mode", headers=as_user(user), json={"enabled": enabled})
    assert r.status_code == 200
    return r.json()


def _feed_post(client, user=KOBE, post=POST):
    r = client.get("/api/v1/posts", headers=as_user(user))
    return next(p for p in r.json()["items"] if p["id"] == post), r.text


def _setup(client):
    # Some opinions exist on the post before Kobe looks at it.
    client.put(f"/api/v1/posts/{POST}/vote", headers=as_user(JOSIE), json={"value": "AI"})
    client.put(f"/api/v1/posts/{POST}/reaction", headers=as_user(JOSIE), json={"kind": "heart"})
    client.post(f"/api/v1/posts/{POST}/comments", headers=as_user(JOSIE), json={"body": SECRET_COMMENT})


def test_setting_is_saved_on_the_server(seeded_client):
    assert _enable(seeded_client) == {"blind_mode": True}
    session = seeded_client.get("/api/v1/auth/session", headers=as_user(KOBE)).json()
    assert session["blind_mode"] is True
    assert _enable(seeded_client, enabled=False) == {"blind_mode": False}


def test_counts_and_comments_absent_before_voting(seeded_client):
    _setup(seeded_client)
    _enable(seeded_client)

    post, raw = _feed_post(seeded_client)
    assert post["blind"] is True
    assert post["votes"] is None
    assert post["reactions"] is None
    assert post["comment_count"] is None
    assert post["media"]["url"]  # the image itself is still shown
    assert SECRET_COMMENT not in raw

    single = seeded_client.get(f"/api/v1/posts/{POST}", headers=as_user(KOBE)).json()
    assert single["votes"] is None and single["comment_count"] is None

    comments = seeded_client.get(f"/api/v1/posts/{POST}/comments", headers=as_user(KOBE))
    assert comments.status_code == 403
    assert SECRET_COMMENT not in comments.text


def test_counts_and_comments_present_after_voting(seeded_client):
    _setup(seeded_client)
    _enable(seeded_client)

    vote = seeded_client.put(f"/api/v1/posts/{POST}/vote", headers=as_user(KOBE), json={"value": "REAL"})
    assert vote.status_code == 200
    assert vote.json()["votes"] == {"ai": 1, "real": 1}  # the vote response reveals the counts

    post, _ = _feed_post(seeded_client)
    assert post["blind"] is False
    assert post["votes"] == {"ai": 1, "real": 1}
    assert post["reactions"]["heart"] == 1
    assert post["comment_count"] == 1

    comments = seeded_client.get(f"/api/v1/posts/{POST}/comments", headers=as_user(KOBE)).json()
    assert [c["body"] for c in comments["items"]] == [SECRET_COMMENT]


def test_removing_the_vote_hides_everything_again(seeded_client):
    _setup(seeded_client)
    _enable(seeded_client)
    seeded_client.put(f"/api/v1/posts/{POST}/vote", headers=as_user(KOBE), json={"value": "AI"})
    r = seeded_client.delete(f"/api/v1/posts/{POST}/vote", headers=as_user(KOBE))
    assert r.json()["votes"] is None
    post, _ = _feed_post(seeded_client)
    assert post["votes"] is None


def test_reacting_and_commenting_are_blocked_until_voting(seeded_client):
    _enable(seeded_client)
    react = seeded_client.put(f"/api/v1/posts/{POST}/reaction", headers=as_user(KOBE), json={"kind": "like"})
    assert react.status_code == 403  # a reaction response would include everyone's counts
    comment = seeded_client.post(f"/api/v1/posts/{POST}/comments", headers=as_user(KOBE), json={"body": "hi"})
    assert comment.status_code == 403


def test_caption_is_hidden_too(seeded_client):
    post = upload(seeded_client, KARA, make_jpeg(), caption="Definitely real, I took this").json()
    _enable(seeded_client)
    view, raw = _feed_post(seeded_client, post=post["id"])
    assert view["caption"] is None
    assert "Definitely real" not in raw


def test_own_posts_are_never_hidden(seeded_client):
    mine = upload(seeded_client, KOBE, make_jpeg()).json()
    _enable(seeded_client)
    post, _ = _feed_post(seeded_client, post=mine["id"])
    assert post["blind"] is False and post["votes"] == {"ai": 0, "real": 0}


def test_profile_activity_hides_other_peoples_votes(seeded_client):
    seeded_client.put(f"/api/v1/posts/{POST}/vote", headers=as_user(JOSIE), json={"value": "AI"})
    _enable(seeded_client)
    items = seeded_client.get(f"/api/v1/users/{JOSIE}/activity", headers=as_user(KOBE)).json()["items"]
    item = next(i for i in items if i["post"]["id"] == POST)
    assert item["vote"] is None  # how Josie voted is an opinion on the post too
    assert item["post"]["votes"] is None


def test_other_users_are_unaffected(seeded_client):
    _setup(seeded_client)
    _enable(seeded_client, user=KOBE)
    post, _ = _feed_post(seeded_client, user=KARA)
    assert post["blind"] is False and post["votes"] is not None


def test_blind_mode_body_is_strict(seeded_client):
    r = seeded_client.put("/api/v1/me/blind-mode", headers=as_user(KOBE), json={"enabled": True, "user_id": KARA})
    assert r.status_code == 422
