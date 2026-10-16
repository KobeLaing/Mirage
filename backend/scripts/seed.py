"""Reset the database to the demo state (FR-70..74). Safe to re-run.

    python -m scripts.seed

Creates six users, seven caption-less image posts and a set of votes. Media
from SEED_MEDIA_DIR goes through the same validation and metadata stripping as
real uploads.

Passwords are never written in this file. Each account's password comes from
an environment variable (SEED_KOBE_PASSWORD, ...; see .env.example) and is
stored only as an Argon2 hash. If any are missing the script stops before
touching the database.

XP: Kobe and Kara get fixed demo values. The four community accounts get
exactly the XP their seeded posts and votes would have earned, so their
profiles add up.
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
from app.progression import XP_PER_POST, XP_PER_VOTE
from app.repositories import maintenance_repo, post_repo, user_repo, vote_repo
from app.security.passwords import Passwords
from app.storage.local import LocalDiskStorage

log = logging.getLogger("mirage.seed")


class SeedConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedUser:
    handle: str  # also the login username
    display_name: str
    avatar_id: int
    password_setting: str  # name of the Settings field holding the password
    xp: int | None = None  # None = whatever the seeded posts and votes earn


@dataclass(frozen=True)
class SeedPost:
    filename: str
    ground_truth: str
    author_handle: str
    votes: tuple[tuple[str, str], ...] = ()  # (voter handle, "AI" | "REAL")


USERS = (
    SeedUser("KobeLaing", "Kobe Laing", 3, "seed_kobe_password", xp=150),  # Silver, 1/4 of the way to Gold
    SeedUser("KaraMercer", "Kara Mercer", 7, "seed_kara_password", xp=600),  # Gold, 3/4 of the way to Platinum
    SeedUser("AltairVance", "Altair Vance", 1, "seed_altair_password"),
    SeedUser("JosieHart", "Josie Hart", 5, "seed_josie_password"),
    SeedUser("TerraOkafor", "Terra Okafor", 9, "seed_terra_password"),
    SeedUser("RiverCalloway", "River Calloway", 10, "seed_river_password"),
)

# Listed oldest first; the feed shows them newest first.
POSTS = (
    SeedPost("aiphote1.jpg", "AI", "KobeLaing"),
    SeedPost("Phoenix_Sun.jpg", "AI", "KaraMercer"),
    SeedPost("sandy-hook.png", "REAL", "KobeLaing"),
    SeedPost(
        "AIoasis.jpg", "AI", "AltairVance",
        votes=(("JosieHart", "AI"), ("TerraOkafor", "AI"), ("RiverCalloway", "AI"), ("KobeLaing", "REAL")),
    ),
    SeedPost(
        "bluehummingbird.jpg", "AI", "JosieHart",
        votes=(("AltairVance", "AI"), ("TerraOkafor", "AI"), ("RiverCalloway", "REAL")),
    ),
    SeedPost(
        "realpainting3.jpg", "REAL", "TerraOkafor",
        votes=(("AltairVance", "REAL"), ("JosieHart", "REAL"), ("RiverCalloway", "REAL")),
    ),
    SeedPost(
        "realpainting4.jpg", "REAL", "RiverCalloway",
        votes=(("AltairVance", "REAL"), ("JosieHart", "REAL"), ("TerraOkafor", "REAL")),
    ),
)


def _passwords_from(settings: Settings) -> dict[str, str]:
    found, missing = {}, []
    for u in USERS:
        secret = getattr(settings, u.password_setting)
        if secret is None or not secret.get_secret_value():
            missing.append(u.password_setting.upper())
        else:
            found[u.handle] = secret.get_secret_value()
    if missing:
        raise SeedConfigError(f"Set these in backend/.env before seeding: {', '.join(missing)}")
    return found


def _earned_xp(handle: str) -> int:
    posts = sum(1 for p in POSTS if p.author_handle == handle)
    votes = sum(1 for p in POSTS for voter, _ in p.votes if voter == handle)
    return posts * XP_PER_POST + votes * XP_PER_VOTE


def seed(settings: Settings) -> dict[str, int]:
    passwords = _passwords_from(settings)  # fail fast, before anything is deleted
    hasher = Passwords(fast=settings.environment == "test")

    upgrade_head(settings.database_url, settings.upload_dir)
    engine = build_engine(settings.database_url)
    storage = LocalDiskStorage(settings.upload_dir, settings.public_api_url)
    limits = pipeline.MediaLimits(settings.max_image_bytes, settings.max_video_bytes, settings.max_image_pixels)
    session_factory = build_session_factory(engine)
    created = {"users": 0, "posts": 0, "votes": 0, "skipped": 0}

    with session_factory() as db:
        old_keys = maintenance_repo.all_media_keys(db)
        maintenance_repo.wipe_all(db)

        users = {}
        for u in USERS:
            users[u.handle] = user_repo.create(
                db,
                handle=u.handle,
                display_name=u.display_name,
                avatar_id=u.avatar_id,
                xp=u.xp if u.xp is not None else _earned_xp(u.handle),
                password_hash=hasher.hash(passwords[u.handle]),
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
            post = post_repo.create(
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
            for voter, value in p.votes:
                vote_repo.create(db, users[voter].id, post.id, value)
                created["votes"] += 1

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
    try:
        result = seed(settings)
    except SeedConfigError as exc:
        log.error("seed.config_missing", extra={"detail": str(exc)})
        return 1
    log.info("seed.done", extra=result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
