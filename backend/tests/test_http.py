"""Cross-cutting HTTP behaviour: health, error shape, headers, CORS, identity."""

from fastapi import APIRouter

from tests.conftest import FRONTEND_ORIGIN, KOBE, as_user


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_unknown_route_uses_error_shape(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    body = r.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == r.headers["x-request-id"]


def test_security_headers_on_api_responses(client):
    r = client.get("/api/v1/posts")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["referrer-policy"] == "no-referrer"


def test_cors_allows_only_frontend_origin(client):
    ok = client.options(
        "/api/v1/posts",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "x-csrf-token"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    # Credentials (the session cookie) are allowed, but only for that one exact origin.
    assert ok.headers.get("access-control-allow-credentials") == "true"

    evil = client.options(
        "/api/v1/posts",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers
    simple = client.get("/api/v1/posts", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


def test_unhandled_error_hides_internals(app, client):
    router = APIRouter()

    @router.get("/boom")
    def boom():
        raise RuntimeError("database password is hunter2 at C:\\secret\\path.py")

    app.include_router(router)
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"]
    text = r.text
    assert "hunter2" not in text and "Traceback" not in text and "secret" not in text
    assert r.headers["x-content-type-options"] == "nosniff"


def test_validation_errors_do_not_echo_input(seeded_client):
    r = seeded_client.get("/api/v1/posts", params={"limit": "<script>alert(1)</script>"}, headers=as_user(KOBE))
    assert r.status_code == 422
    assert "<script>" not in r.text


def test_forged_or_malformed_session_cookie_is_401(seeded_client):
    for value in ("", "garbage", "1", "eyJ1c2VyX2lkIjoxfQ.forged.signature", "x" * 4000):
        r = seeded_client.get("/api/v1/me", headers={"Cookie": f"mirage_session={value}"})
        assert r.status_code == 401, value


def test_old_dev_identity_header_is_ignored(seeded_client):
    """X-User-Id used to pick the account. It must have no effect any more."""
    assert seeded_client.get("/api/v1/me", headers={"X-User-Id": str(KOBE)}).status_code == 401


def test_reads_and_writes_both_require_sign_in(seeded_client):
    assert seeded_client.get("/api/v1/me").status_code == 401
    assert seeded_client.get("/api/v1/posts").status_code == 401
    r = seeded_client.put("/api/v1/posts/1/vote", json={"value": "AI"}, headers={"Origin": FRONTEND_ORIGIN})
    assert r.status_code == 401

def test_request_id_is_echoed_when_valid(client):
    rid = "0123456789abcdef0123456789abcdef"
    assert client.get("/health", headers={"X-Request-ID": rid}).headers["x-request-id"] == rid
    other = client.get("/health", headers={"X-Request-ID": "<bad id>"}).headers["x-request-id"]
    assert other != "<bad id>"


def test_settings_refuse_missing_or_weak_session_secret():
    import pytest
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # no SESSION_SECRET at all
    with pytest.raises(ValidationError):
        Settings(_env_file=None, session_secret="too-short")