"""Comments: create, list (newest last), delete own only, limits, plain text, no XP, rate limit."""

import pytest

from tests.conftest import FRONTEND_ORIGIN, KARA, KOBE, as_user

POST = 1


def comment(client, user, body, post=POST):
    return client.post(f"/api/v1/posts/{post}/comments", headers=as_user(user), json={"body": body})


def comments(client, user=KOBE, post=POST):
    return client.get(f"/api/v1/posts/{post}/comments", headers=as_user(user))


def xp(client, user):
    return client.get("/api/v1/me", headers=as_user(user)).json()["xp"]


def test_comment_shows_author_avatar_name_and_badge(seeded_client):
    r = comment(seeded_client, KARA, "  Looks AI to me  ")
    assert r.status_code == 201
    body = r.json()
    assert body["body"] == "Looks AI to me"
    assert body["author"]["display_name"] == "Kara Mercer"
    assert body["author"]["avatar_id"] == 7 and body["author"]["rank"] == "gold"
    assert body["mine"] is True


def test_comments_are_listed_newest_last(seeded_client):
    for text in ("first", "second", "third"):
        comment(seeded_client, KOBE, text)
    items = comments(seeded_client).json()["items"]
    assert [c["body"] for c in items] == ["first", "second", "third"]


def test_mine_flag_is_per_viewer(seeded_client):
    comment(seeded_client, KOBE, "hello")
    assert comments(seeded_client, KOBE).json()["items"][0]["mine"] is True
    assert comments(seeded_client, KARA).json()["items"][0]["mine"] is False


def test_feed_shows_comment_count(seeded_client):
    comment(seeded_client, KARA, "one")
    comment(seeded_client, KOBE, "two")
    feed = seeded_client.get("/api/v1/posts", headers=as_user(KOBE)).json()["items"]
    assert {p["id"]: p["comment_count"] for p in feed}[POST] == 2


def test_can_delete_own_comment(seeded_client):
    cid = comment(seeded_client, KOBE, "oops").json()["id"]
    assert seeded_client.delete(f"/api/v1/comments/{cid}", headers=as_user(KOBE)).status_code == 204
    assert comments(seeded_client).json()["items"] == []


def test_cannot_delete_someone_elses_comment(seeded_client):
    cid = comment(seeded_client, KOBE, "mine").json()["id"]
    r = seeded_client.delete(f"/api/v1/comments/{cid}", headers=as_user(KARA))
    assert r.status_code == 403
    assert len(comments(seeded_client).json()["items"]) == 1


def test_delete_missing_comment_is_404(seeded_client):
    assert seeded_client.delete("/api/v1/comments/9999", headers=as_user(KOBE)).status_code == 404


def test_comment_length_limit(seeded_client):
    assert comment(seeded_client, KOBE, "x" * 500).status_code == 201
    assert comment(seeded_client, KOBE, "x" * 501).status_code == 422


@pytest.mark.parametrize("body", ["", "   ", "\n\t"])
def test_blank_comment_rejected(seeded_client, body):
    assert comment(seeded_client, KOBE, body).status_code in (400, 422)


def test_control_characters_rejected(seeded_client):
    assert comment(seeded_client, KOBE, "hi\x00there").status_code == 422


def test_html_is_stored_as_plain_text(seeded_client):
    payload = "<img src=x onerror=alert(1)><script>alert(2)</script>"
    r = comment(seeded_client, KOBE, payload)
    assert r.status_code == 201
    assert r.json()["body"] == payload  # stored verbatim; the frontend renders it as text, never HTML


def test_commenting_earns_no_xp(seeded_client):
    before = xp(seeded_client, KOBE)
    for i in range(5):
        comment(seeded_client, KOBE, f"comment {i}")
    assert xp(seeded_client, KOBE) == before


def test_body_cannot_name_another_author(seeded_client):
    r = seeded_client.post(
        f"/api/v1/posts/{POST}/comments", headers=as_user(KOBE), json={"body": "hi", "user_id": KARA}
    )
    assert r.status_code == 422


def test_comment_on_missing_post_is_404(seeded_client):
    assert comment(seeded_client, KOBE, "hi", post=9999).status_code == 404
    assert comments(seeded_client, post=9999).status_code == 404


def test_commenting_requires_sign_in(seeded_client):
    r = seeded_client.post(f"/api/v1/posts/{POST}/comments", json={"body": "hi"}, headers={"Origin": FRONTEND_ORIGIN})
    assert r.status_code == 401
    assert seeded_client.get(f"/api/v1/posts/{POST}/comments").status_code == 401


def test_comment_rate_limit_is_per_user(seeded, app, client):
    app.state.settings.rate_limit_comments_per_minute = 2
    assert comment(client, KOBE, "1").status_code == 201
    assert comment(client, KOBE, "2").status_code == 201
    r = comment(client, KOBE, "3")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert comment(client, KARA, "still fine").status_code == 201


def test_deleting_a_post_removes_its_comments(seeded_client):
    from tests.conftest import make_jpeg, upload

    post = upload(seeded_client, KOBE, make_jpeg()).json()
    comment(seeded_client, KARA, "nice", post=post["id"])
    assert seeded_client.delete(f"/api/v1/posts/{post['id']}", headers=as_user(KOBE)).status_code == 204
    assert comments(seeded_client, post=post["id"]).status_code == 404
