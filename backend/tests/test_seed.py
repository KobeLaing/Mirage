from pathlib import Path

from PIL import Image
from sqlalchemy import select

from app.db.models import Post, User
from app.db.session import build_engine, build_session_factory
from app.progression import progress_to_next, rank_for_xp
from scripts.seed import seed


def _load(settings):
    engine = build_engine(settings.database_url)
    with build_session_factory(engine)() as db:
        users = {u.handle: u for u in db.scalars(select(User))}
        posts = list(db.scalars(select(Post).order_by(Post.created_at)))
    engine.dispose()
    return users, posts


def test_seed_creates_users_and_posts(settings):
    result = seed(settings)
    assert result == {"users": 2, "posts": 6, "skipped": 0}

    users, posts = _load(settings)
    silver, gold = users["Kobe"], users["KaraM"]
    assert silver.xp == 150 and rank_for_xp(silver.xp).key == "silver" and progress_to_next(silver.xp) == 0.25
    assert gold.xp == 600 and rank_for_xp(gold.xp).key == "gold" and progress_to_next(gold.xp) == 0.75

    assert [p.ground_truth for p in posts] == ["AI", "AI", "REAL", "AI", "AI", "REAL"]
    assert [p.media_kind for p in posts] == ["image"] * 3 + ["video"] * 3
    assert all(p.caption is None for p in posts)
    for p in posts:
        assert (Path(settings.upload_dir) / p.media_key).is_file()


def test_seed_is_idempotent_and_cleans_old_files(settings):
    seed(settings)
    first_files = set(Path(settings.upload_dir).iterdir())
    seed(settings)
    users, posts = _load(settings)
    assert len(users) == 2 and len(posts) == 6
    files = set(Path(settings.upload_dir).iterdir())
    assert len(files) == 6
    assert not (files & first_files)  # previous run's files were removed


def test_seed_strips_image_metadata(settings):
    seed(settings)
    _, posts = _load(settings)
    for p in posts:
        if p.media_kind == "image":
            with Image.open(Path(settings.upload_dir) / p.media_key) as img:
                assert not img.getexif()
                assert "exif" not in img.info and "xmp" not in img.info


def test_seed_skips_missing_media(settings, seed_media_copy):
    (seed_media_copy / "ai-video-2.mp4").unlink()
    settings.seed_media_dir = seed_media_copy
    result = seed(settings)
    assert result == {"users": 2, "posts": 5, "skipped": 1}
