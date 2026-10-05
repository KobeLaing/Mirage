from pathlib import Path

from tests.conftest import KARA, KOBE, SEED_MEDIA, as_user, make_jpeg, upload


def _xp(client, user_id):
    return client.get("/api/v1/me", headers=as_user(user_id)).json()["xp"]


def test_create_image_post_awards_xp(seeded_client):
    before = _xp(seeded_client, KOBE)
    r = upload(seeded_client, KOBE, make_jpeg(), caption="  Is this real?  ")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["caption"] == "Is this real?"
    assert body["media"]["kind"] == "image" and body["media"]["mime_type"] == "image/jpeg"
    assert body["author"]["id"] == KOBE
    assert body["votes"] == {"ai": 0, "real": 0}
    assert _xp(seeded_client, KOBE) == before + 25


def test_create_video_post_without_caption(seeded_client):
    data = (SEED_MEDIA / "real-video-1.mp4").read_bytes()
    r = upload(seeded_client, KARA, data, filename="clip.mp4", content_type="video/mp4")
    assert r.status_code == 201, r.text
    assert r.json()["caption"] is None
    assert r.json()["media"]["kind"] == "video"


def test_blank_caption_becomes_null(seeded_client):
    r = upload(seeded_client, KOBE, make_jpeg(), caption="   ")
    assert r.status_code == 201
    assert r.json()["caption"] is None


def test_caption_too_long_rejected(seeded_client):
    r = upload(seeded_client, KOBE, make_jpeg(), caption="x" * 501)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_caption_control_characters_rejected(seeded_client):
    r = upload(seeded_client, KOBE, make_jpeg(), caption="hi\x00there")
    assert r.status_code == 422


def test_caption_html_is_stored_as_plain_text(seeded_client):
    payload = "<img src=x onerror=alert(1)>"
    r = upload(seeded_client, KOBE, make_jpeg(), caption=payload)
    assert r.status_code == 201
    assert r.json()["caption"] == payload  # stored verbatim; the frontend renders it as text


def test_posting_requires_a_user(seeded_client):
    r = seeded_client.post("/api/v1/posts", files={"file": ("a.jpg", make_jpeg(), "image/jpeg")})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_stored_filename_is_random(seeded_client, seeded):
    r = upload(seeded_client, KOBE, make_jpeg(), filename="../../../app/main.py")
    assert r.status_code == 201
    url = r.json()["media"]["url"]
    key = url.rsplit("/", 1)[1]
    assert len(key) == 36 and key.endswith(".jpg") and "main" not in key
    assert (Path(seeded.upload_dir) / key).is_file()


def test_delete_own_post_removes_xp_and_file(seeded_client, seeded):
    created = upload(seeded_client, KOBE, make_jpeg()).json()
    key = created["media"]["url"].rsplit("/", 1)[1]
    xp = _xp(seeded_client, KOBE)

    r = seeded_client.delete(f"/api/v1/posts/{created['id']}", headers=as_user(KOBE))
    assert r.status_code == 204
    assert _xp(seeded_client, KOBE) == xp - 25
    assert not (Path(seeded.upload_dir) / key).exists()
    assert seeded_client.get(f"/api/v1/posts/{created['id']}").status_code == 404


def test_cannot_delete_someone_elses_post(seeded_client):
    created = upload(seeded_client, KOBE, make_jpeg()).json()
    r = seeded_client.delete(f"/api/v1/posts/{created['id']}", headers=as_user(KARA))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"
    assert seeded_client.get(f"/api/v1/posts/{created['id']}").status_code == 200


def test_delete_missing_post(seeded_client):
    assert seeded_client.delete("/api/v1/posts/9999", headers=as_user(KOBE)).status_code == 404


def test_post_rate_limit(seeded, app, client):
    app.state.settings.rate_limit_posts_per_hour = 2
    assert upload(client, KOBE, make_jpeg()).status_code == 201
    assert upload(client, KOBE, make_jpeg()).status_code == 201
    r = upload(client, KOBE, make_jpeg())
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    assert r.json()["error"]["code"] == "rate_limited"
    # Per user: someone else can still post.
    assert upload(client, KARA, make_jpeg()).status_code == 201
