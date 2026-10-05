import io
import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.config import BACKEND_DIR, Settings
from app.db.migrate import upgrade_head
from app.db.session import build_engine, build_session_factory

SEED_MEDIA = BACKEND_DIR.parent / "seed-media"


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
        frontend_origin="http://localhost:3000",
        log_level="WARNING",
    )


@pytest.fixture
def migrated(settings: Settings) -> Settings:
    upgrade_head(settings.database_url)
    return settings


@pytest.fixture
def db(migrated: Settings):
    engine = build_engine(migrated.database_url)
    session = build_session_factory(engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def app(migrated: Settings):
    from app.main import create_app

    application = create_app(migrated)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
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


def as_user(user_id: int) -> dict:
    return {"X-User-Id": str(user_id)}


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
