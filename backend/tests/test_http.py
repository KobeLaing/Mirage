"""Cross-cutting HTTP behaviour: health, error shape, headers, CORS, identity."""

from fastapi import APIRouter

from tests.conftest import KOBE, as_user


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
                 "Access-Control-Request-Headers": "x-user-id"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"

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
    r = seeded_client.get("/api/v1/posts", params={"limit": "<script>alert(1)</script>"})
    assert r.status_code == 422
    assert "<script>" not in r.text


def test_unknown_or_malformed_user_header_is_401(seeded_client):
    for value in ("999", "abc", "1 OR 1=1", "-1", "１".encode(), "9" * 40):
        r = seeded_client.get("/api/v1/me", headers={"X-User-Id": value})
        assert r.status_code == 401, value


def test_missing_user_header_is_401_for_writes_but_reads_are_open(seeded_client):
    assert seeded_client.get("/api/v1/me").status_code == 401
    assert seeded_client.get("/api/v1/posts").status_code == 200


def test_request_id_is_echoed_when_valid(client):
    rid = "0123456789abcdef0123456789abcdef"
    assert client.get("/health", headers={"X-Request-ID": rid}).headers["x-request-id"] == rid
    other = client.get("/health", headers={"X-Request-ID": "<bad id>"}).headers["x-request-id"]
    assert other != "<bad id>"


def test_production_refuses_dev_header_identity():
    import pytest
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", auth_mode="dev_header")