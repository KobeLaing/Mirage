import io
import secrets
import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.config import BACKEND_DIR, Settings
from app.db.migrate import upgrade_head
from app.db.session import build_engine, build_session_factory

SEED_MEDIA = BACKEND_DIR.parent / "seed-media"


FRONTEND_ORIGIN = "http://localhost:3000"
# Fresh random signing key per test run: nothing secret-looking lives in the repo.
TEST_SECRET = secrets.token_urlsafe(48)

# Test-only passwords for the seeded accounts. Real ones come from backend/.env.
SEED_PASSWORDS = {
    "seed_kobe_password": "kobe-test-pw",
    "seed_kara_password": "kara-test-pw",
    "seed_altair_password": "altair-test-pw",
    "seed_josie_password": "josie-test-pw",
    "seed_terra_password": "terra-test-pw",
    "seed_river_password": "river-test-pw",
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / "test.db"
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{db_path.as_posix()}",
        upload_dir=tmp_path / "uploads",
        seed_media_dir=SEED_MEDIA,
        public_api_url="http://testserver",
        frontend_origin=FRONTEND_ORIGIN,
        session_secret=TEST_SECRET,
        log_level="WARNING",
        **SEED_PASSWORDS,
    )


@pytest.fixture
def migrated(settings: Settings) -> Settings:
    upgrade_head(settings.database_url, settings.upload_dir)
    return settings


@pytest.fixture
def db(migrated: Settings):
    engine = build_engine(migrated.database_url)
    session = build_session_factory(engine)()
    yield session
    session.close()
    engine.dispose()


_session_minter = None  # set by the `app` fixture; used by as_user()


@pytest.fixture
def app(migrated: Settings):
    global _session_minter
    from app.main import create_app

    application = create_app(migrated)
    _session_minter = _make_session_minter(application)
    yield application
    _session_minter = None
    application.state.engine.dispose()


def _make_session_minter(application):
    """Creates a real server-side session for a user, exactly as login would,
    and returns the headers a signed-in browser would send: the session cookie,
    the matching CSRF token, and our frontend's Origin. One session per user,
    reused for the whole test."""
    from datetime import timedelta

    from app.db.base import utcnow
    from app.repositories import session_repo
    from app.security.tokens import SESSION_COOKIE, session_id

    cache: dict[int, dict] = {}

    def mint(user_id: int) -> dict:
        if user_id not in cache:
            tokens = application.state.tokens
            raw = tokens.new_secret()
            with application.state.session_factory() as db:
                session_repo.create(
                    db, session_id=session_id(raw), user_id=user_id, expires_at=utcnow() + timedelta(hours=1)
                )
                db.commit()
            cookie = tokens.sign(raw)
            cache[user_id] = {
                "Cookie": f"{SESSION_COOKIE}={cookie}",
                "X-CSRF-Token": tokens.csrf_for(cookie),
                "Origin": FRONTEND_ORIGIN,
            }
        return dict(cache[user_id])

    return mint


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    # https, so Secure cookies set by /auth/login are sent back like a browser would.
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture
def seeded(migrated: Settings) -> Settings:
    from scripts.seed import seed

    seed(migrated)
    return migrated


@pytest.fixture
def seeded_client(seeded, client):
    return client


KOBE, KARA = 1, 2  # ids of the seeded users (Silver 150 XP, Gold 600 XP)
ALTAIR, JOSIE, TERRA, RIVER = 3, 4, 5, 6  # the seeded community accounts


def as_user(user_id: int) -> dict:
    """Request headers for a signed-in user (needs the `app` fixture)."""
    assert _session_minter is not None, "as_user() needs the app/client fixture"
    return _session_minter(user_id)


def login(client, username: str, password: str, website: str = ""):
    """The real login flow, through the HTTP API, as the frontend does it."""
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "website": website},
        headers={"Origin": FRONTEND_ORIGIN},
    )


def upload(client, user_id: int, data: bytes, filename="photo.jpg", content_type="image/jpeg", caption=None):
    form = {"caption": caption} if caption is not None else {}
    return client.post(
        "/api/v1/posts", headers=as_user(user_id), files={"file": (filename, data, content_type)}, data=form
    )


@pytest.fixture
def seed_media_copy(tmp_path: Path) -> Path:
    target = tmp_path / "seed-media"
    shutil.copytree(SEED_MEDIA, target)
    return target


def make_jpeg(size=(64, 48), color=(200, 30, 30), exif: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    kwargs = {"exif": exif} if exif else {}
    Image.new("RGB", size, color).save(buf, "JPEG", **kwargs)
    return buf.getvalue()


def make_png(size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, (0, 128, 255, 200)).save(buf, "PNG")
    return buf.getvalue()


def make_webp(size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 200, 90)).save(buf, "WEBP")
    return buf.getvalue()


# Start of a genuine WebM file: EBML header declaring DocType "webm".
WEBM_HEADER = bytes.fromhex("1a45dfa39f4286810142f7810142f2810442f381084282847765626d42878104428581021853806701")


def gps_exif() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "SpyCam Inc"  # Make
    exif[0x0110] = "Model X"  # Model
    gps = {1: "N", 2: (51.0, 30.0, 0.0), 3: "W", 4: (0.0, 7.0, 0.0)}
    exif[0x8825] = gps  # GPSInfo IFD
    return exif.tobytes()
