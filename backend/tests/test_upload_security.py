"""SR-1..7: allow-list, content sniffing, size limits, metadata stripping, safe serving."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from tests.conftest import KOBE, WEBM_HEADER, as_user, gps_exif, make_jpeg, make_webp, upload


@pytest.mark.parametrize(
    "filename, content_type, data",
    [
        # HTML renamed to .jpg and labelled image/jpeg by the client
        ("cat.jpg", "image/jpeg", b"<!DOCTYPE html><html><script>alert(document.cookie)</script></html>"),
        ("logo.svg", "image/svg+xml", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'),
        ("doc.pdf", "application/pdf", b"%PDF-1.4 fake"),
        ("run.exe", "video/mp4", b"MZ\x90\x00\x03\x00\x00\x00"),
        ("notes.txt", "text/plain", b"just text"),
        # Real files in formats that are no longer on the allow-list
        ("photo.webp", "image/webp", make_webp()),
        ("clip.webm", "video/webm", WEBM_HEADER + b"\x00" * 64),
    ],
)
def test_disallowed_file_type_rejected(seeded_client, filename, content_type, data):
    r = upload(seeded_client, KOBE, data, filename=filename, content_type=content_type)
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


def test_real_image_accepted_despite_wrong_client_labels(seeded_client):
    r = upload(seeded_client, KOBE, make_jpeg(), filename="whatever.exe", content_type="application/octet-stream")
    assert r.status_code == 201
    assert r.json()["media"]["mime_type"] == "image/jpeg"


def _small_limit_client(settings):
    settings.max_image_bytes = 20_000
    settings.max_video_bytes = 40_000
    return TestClient(create_app(settings))


def test_oversized_image_rejected(seeded):
    big = io.BytesIO()
    Image.effect_noise((300, 300), 100).convert("RGB").save(big, "PNG")
    assert 20_000 < len(big.getvalue()) < 40_000 + 1024 * 1024
    with _small_limit_client(seeded) as client:
        r = upload(client, KOBE, big.getvalue(), filename="big.png", content_type="image/png")
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


def test_oversized_body_cut_off_before_parsing(seeded):
    huge = b"\xff\xd8\xff" + b"\x00" * (40_000 + 2 * 1024 * 1024)
    with _small_limit_client(seeded) as client:
        r = upload(client, KOBE, huge)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


def test_oversized_json_body_rejected(seeded_client):
    r = seeded_client.put(
        "/api/v1/me/avatar", headers={**as_user(KOBE), "Content-Type": "application/json"},
        content=b'{"avatar_id": 1, "x": "' + b"a" * 100_000 + b'"}',
    )
    assert r.status_code == 413


def test_uploaded_image_has_no_exif_or_gps(seeded_client):
    r = upload(seeded_client, KOBE, make_jpeg(exif=gps_exif()))
    assert r.status_code == 201
    media = seeded_client.get(r.json()["media"]["url"])
    assert media.status_code == 200
    with Image.open(io.BytesIO(media.content)) as img:
        assert dict(img.getexif()) == {}
    assert b"SpyCam" not in media.content


def test_media_served_with_safe_headers(seeded_client):
    r = upload(seeded_client, KOBE, make_jpeg())
    media = seeded_client.get(r.json()["media"]["url"])
    assert media.headers["content-type"] == "image/jpeg"
    assert media.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in media.headers["content-security-policy"]
    assert "default-src 'none'" in media.headers["content-security-policy"]


@pytest.mark.parametrize(
    "key",
    ["..%2F..%2Fapp%2Fmain.py", "..%5C..%5Capp%5Cmain.py", "not-a-key.html", "0" * 32 + ".html", "0" * 32 + ".jpg",
     "0" * 32 + ".webp", "0" * 32 + ".webm"],
)
def test_media_route_rejects_bad_or_unknown_keys(seeded_client, key):
    r = seeded_client.get(f"/api/v1/media/{key}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_video_range_requests_supported(seeded_client):
    post = seeded_client.get("/api/v1/posts").json()["items"][0]
    assert post["media"]["kind"] == "video"
    r = seeded_client.get(post["media"]["url"], headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert len(r.content) == 100
