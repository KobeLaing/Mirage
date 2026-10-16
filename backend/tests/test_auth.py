"""Login, sessions, logout, CSRF, login rate limiting, and the honeypot field."""

import logging

from app.security.tokens import SESSION_COOKIE
from tests.conftest import FRONTEND_ORIGIN, KOBE, SEED_PASSWORDS, as_user, login

KOBE_PW = SEED_PASSWORDS["seed_kobe_password"]
GENERIC = "Invalid username or password"


def _csrf_headers(session_body: dict) -> dict:
    return {"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": session_body["csrf_token"]}


# --- Login ---------------------------------------------------------------------

def test_login_sets_a_hardened_session_cookie(seeded, client):
    r = login(client, "KobeLaing", KOBE_PW)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["display_name"] == "Kobe Laing"
    assert body["csrf_token"]
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    lowered = cookie.lower()
    assert "httponly" in lowered and "secure" in lowered and "samesite=lax" in lowered
    assert "max-age=" in lowered


def test_session_cookie_identifies_the_user(seeded, client):
    login(client, "KobeLaing", KOBE_PW)
    me = client.get("/api/v1/me")
    assert me.status_code == 200 and me.json()["id"] == KOBE
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200 and session.json()["user"]["id"] == KOBE


def test_username_is_case_insensitive(seeded, client):
    assert login(client, "kobelaing", KOBE_PW).status_code == 200


def test_every_login_failure_looks_identical(seeded, client):
    wrong_password = login(client, "KobeLaing", "nope")
    unknown_user = login(client, "NoSuchUser", KOBE_PW)
    for r in (wrong_password, unknown_user):
        assert r.status_code == 401
        assert r.json()["error"]["message"] == GENERIC
        assert r.json()["error"]["code"] == "invalid_credentials"
        assert "set-cookie" not in r.headers
    assert wrong_password.json()["error"]["details"] == unknown_user.json()["error"]["details"]


def test_failed_login_is_logged_without_the_password(seeded, client, caplog):
    caplog.set_level(logging.WARNING, logger="mirage.auth")
    login(client, "KobeLaing", "my-secret-guess-123")
    assert any(r.getMessage() == "auth.login_failed" for r in caplog.records)
    assert "my-secret-guess-123" not in caplog.text


def test_login_rejects_unknown_fields(seeded, client):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "KobeLaing", "password": KOBE_PW, "user_id": 2},
        headers={"Origin": FRONTEND_ORIGIN},
    )
    assert r.status_code == 422


def test_login_requires_our_origin(seeded, client):
    """Another website can't submit our login form (login CSRF)."""
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "KobeLaing", "password": KOBE_PW},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


# --- Honeypot --------------------------------------------------------------------

def test_honeypot_filled_is_rejected_like_a_wrong_password(seeded, client, caplog):
    caplog.set_level(logging.WARNING, logger="mirage.auth")
    # Correct credentials, but the hidden "website" field has a value: a bot.
    r = login(client, "KobeLaing", KOBE_PW, website="http://spam.example")
    assert r.status_code == 401
    assert r.json()["error"]["message"] == GENERIC
    assert "set-cookie" not in r.headers
    assert client.get("/api/v1/me").status_code == 401
    assert any(rec.getMessage() == "auth.suspected_bot" for rec in caplog.records)


def test_honeypot_empty_allows_normal_login(seeded, client):
    r = login(client, "KobeLaing", KOBE_PW, website="")
    assert r.status_code == 200
    assert client.get("/api/v1/me").json()["id"] == KOBE


def test_honeypot_omitted_allows_normal_login(seeded, client):
    r = client.post(
        "/api/v1/auth/login", json={"username": "KobeLaing", "password": KOBE_PW}, headers={"Origin": FRONTEND_ORIGIN}
    )
    assert r.status_code == 200


# --- Logout ----------------------------------------------------------------------

def test_logout_revokes_the_session_server_side(seeded, client):
    body = login(client, "KobeLaing", KOBE_PW).json()
    stolen_cookie = client.cookies.get(SESSION_COOKIE)
    r = client.post("/api/v1/auth/logout", headers=_csrf_headers(body))
    assert r.status_code == 204
    assert client.get("/api/v1/me").status_code == 401
    # Even someone who copied the cookie before logout can't use it now.
    replay = client.get("/api/v1/me", headers={"Cookie": f"{SESSION_COOKIE}={stolen_cookie}"})
    assert replay.status_code == 401


def test_expired_session_is_rejected(seeded, app, client):
    login(client, "KobeLaing", KOBE_PW)
    app.state.tokens.ttl_seconds = -1  # every signature is now "too old"
    assert client.get("/api/v1/me").status_code == 401


# --- CSRF ------------------------------------------------------------------------

def test_write_without_csrf_token_is_blocked(seeded, client):
    login(client, "KobeLaing", KOBE_PW)
    r = client.put("/api/v1/posts/1/vote", json={"value": "AI"}, headers={"Origin": FRONTEND_ORIGIN})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


def test_write_with_wrong_csrf_token_is_blocked(seeded, client):
    login(client, "KobeLaing", KOBE_PW)
    r = client.put(
        "/api/v1/posts/1/vote", json={"value": "AI"}, headers={"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": "0" * 64}
    )
    assert r.status_code == 403


def test_write_from_another_origin_is_blocked(seeded, client):
    body = login(client, "KobeLaing", KOBE_PW).json()
    r = client.put(
        "/api/v1/posts/1/vote", json={"value": "AI"},
        headers={"Origin": "https://evil.example", "X-CSRF-Token": body["csrf_token"]},
    )
    assert r.status_code == 403


def test_write_with_valid_csrf_token_succeeds(seeded, client):
    body = login(client, "KobeLaing", KOBE_PW).json()
    r = client.put("/api/v1/posts/1/vote", json={"value": "AI"}, headers=_csrf_headers(body))
    assert r.status_code == 200


def test_csrf_token_from_another_session_is_rejected(seeded_client):
    kobe = as_user(KOBE)
    kara_token = as_user(2)["X-CSRF-Token"]
    r = seeded_client.put("/api/v1/posts/1/vote", json={"value": "AI"}, headers={**kobe, "X-CSRF-Token": kara_token})
    assert r.status_code == 403


# --- Rate limiting -----------------------------------------------------------------

def test_login_is_rate_limited_per_username(seeded, app, client):
    app.state.settings.rate_limit_login_per_username = 3
    for _ in range(3):
        assert login(client, "KobeLaing", "wrong").status_code == 401
    r = login(client, "KobeLaing", KOBE_PW)  # even the right password waits now
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    # A different account isn't affected by Kobe's limit.
    assert login(client, "KaraMercer", SEED_PASSWORDS["seed_kara_password"]).status_code == 200


def test_login_is_rate_limited_per_ip(seeded, app, client):
    app.state.settings.rate_limit_login_per_ip = 3
    for name in ("a", "b", "c"):
        assert login(client, name, "wrong").status_code == 401
    assert login(client, "KobeLaing", KOBE_PW).status_code == 429
