"""Reset the database to the demo state (FR-70..74). Safe to re-run.

    python -m scripts.seed

Creates two users and six caption-less posts. Media from SEED_MEDIA_DIR goes
through the same validation and metadata stripping as real uploads. The seeded
users' XP is set directly to the requested values; seeding does not award the
usual +25 per post.
"""

import logging
import secrets
import sys
from dataclasses import dataclass
from datetime import timedelta

from app.config import Settings, get_settings
from app.db.base import utcnow
from app.db.migrate import upgrade_head
from app.db.session import build_engine, build_session_factory
from app.errors import AppError
from app.logging_setup import configure_logging
from app.media import pipeline
from app.repositories import maintenance_repo, post_repo, user_repo
from app.storage.local import LocalDiskStorage

log = logging.getLogger("mirage.seed")


@dataclass(frozen=True)
class SeedUser:
    handle: str
    display_name: str
    avatar_id: int
    xp: int


@dataclass(frozen=True)
class SeedPost:
    filename: str
    ground_truth: str
    author_handle: str


USERS = (
    SeedUser("Kobe", "Kobe Laing", 3, 150),  # Silver Verifier, 1/4 of the way to Gold
    SeedUser("KaraM", "Kara Mercer", 7, 600),  # Gold Verifier, 3/4 of the way to Platinum
)

# Listed oldest first; the feed shows them newest first.
POSTS = (
    SeedPost("aiphote1.jpg", "AI", "Kobe"),
    SeedPost("Phoenix_Sun.jpg", "AI", "KaraM"),
    SeedPost("sandy-hook.png", "REAL", "Kobe"),
    SeedPost("ai-video-1.mp4", "AI", "KaraM"),
    SeedPost("ai-video-2.mp4", "AI", "Kobe"),
    SeedPost("real-video-1.mp4", "REAL", "KaraM"),
)


def seed(settings: Settings) -> dict[str, int]:
    upgrade_head(settings.database_url)
    engine = build_engine(settings.database_url)
    storage = LocalDiskStorage(settings.upload_dir, settings.public_api_url)
    limits = pipeline.MediaLimits(settings.max_image_bytes, settings.max_video_bytes, settings.max_image_pixels)
    session_factory = build_session_factory(engine)
    created = {"users": 0, "posts": 0, "skipped": 0}

    with session_factory() as db:
        old_keys = maintenance_repo.all_media_keys(db)
        maintenance_repo.wipe_all(db)

        users = {}
        for u in USERS:
            users[u.handle] = user_repo.create(
                db, handle=u.handle, display_name=u.display_name, avatar_id=u.avatar_id, xp=u.xp
            )
            created["users"] += 1

        base_time = utcnow() - timedelta(hours=len(POSTS))
        new_keys = []
        for index, p in enumerate(POSTS):
            source = settings.seed_media_dir / p.filename
            if not source.is_file():
                log.warning("seed.media_missing", extra={"file": p.filename})
                created["skipped"] += 1
                continue
            workdir = pipeline.new_workdir()
            try:
                with source.open("rb") as src:
                    media = pipeline.process(src, limits, workdir)
                key = f"{secrets.token_hex(16)}.{media.ext}"
                with media.open() as data:
                    storage.save(key, data)
            except AppError as exc:
                log.warning("seed.media_rejected", extra={"file": p.filename, "reason": exc.code})
                created["skipped"] += 1
                continue
            finally:
                pipeline.cleanup(workdir)
            new_keys.append(key)
            post_repo.create(
                db,
                author_id=users[p.author_handle].id,
                caption=None,
                media_key=key,
                media_kind=media.kind,
                mime_type=media.mime,
                width=media.width,
                height=media.height,
                ground_truth=p.ground_truth,
                created_at=base_time + timedelta(hours=index),
            )
            created["posts"] += 1

        try:
            db.commit()
        except Exception:
            for key in new_keys:
                storage.delete(key)
            raise

    # Old files are removed only after the new state is committed.
    for key in old_keys:
        storage.delete(key)
    engine.dispose()
    return created


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    result = seed(settings)
    log.info("seed.done", extra=result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
