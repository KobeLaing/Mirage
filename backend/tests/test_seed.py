from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.db.models import Post, User, Vote
from app.db.session import build_engine, build_session_factory
from app.progression import XP_PER_POST, XP_PER_VOTE, progress_to_next, rank_for_xp
from scripts.seed import SeedConfigError, seed
from tests.conftest import SEED_PASSWORDS, login


def _load(settings):
    engine = build_engine(settings.database_url)
    with build_session_factory(engine)() as db:
        users = {u.handle: u for u in db.scalars(select(User))}
        posts = list(db.scalars(select(Post).order_by(Post.created_at)))
        votes = {
            post_id: dict(db.execute(
                select(Vote.value, func.count()).where(Vote.post_id == post_id).group_by(Vote.value)
            ).all())
            for post_id in [p.id for p in posts]
        }
    engine.dispose()
    return users, posts, votes


def test_seed_creates_users_and_posts(settings):
    result = seed(settings)
    assert result == {"users": 6, "posts": 7, "votes": 13, "skipped": 0}

    users, posts, _ = _load(settings)
    silver, gold = users["KobeLaing"], users["KaraMercer"]
    assert silver.xp == 150 and rank_for_xp(silver.xp).key == "silver" and progress_to_next(silver.xp) == 0.25
    assert gold.xp == 600 and rank_for_xp(gold.xp).key == "gold" and progress_to_next(gold.xp) == 0.75
    assert {"AltairVance", "JosieHart", "TerraOkafor", "RiverCalloway"} <= set(users)

    assert [p.ground_truth for p in posts] == ["AI", "AI", "REAL", "AI", "AI", "REAL", "REAL"]
    assert all(p.media_kind == "image" for p in posts)  # the seeded videos are gone
    assert all(p.caption is None for p in posts)
    for p in posts:
        assert (Path(settings.upload_dir) / p.media_key).is_file()


def test_seed_votes_match_the_brief(settings):
    seed(settings)
    users, posts, votes = _load(settings)
    by_author = {p.author_id: p for p in posts if p.author_id > 2}
    oasis = by_author[users["AltairVance"].id]
    hummingbird = by_author[users["JosieHart"].id]
    painting3 = by_author[users["TerraOkafor"].id]
    painting4 = by_author[users["RiverCalloway"].id]
    assert votes[oasis.id] == {"AI": 3, "REAL": 1}
    assert votes[hummingbird.id] == {"AI": 2, "REAL": 1}
    assert votes[painting3.id] == {"REAL": 3}
    assert votes[painting4.id] == {"REAL": 3}


def test_community_accounts_have_the_xp_they_earned(settings):
    seed(settings)
    users, _, _ = _load(settings)
    # Each community account made one post and cast three votes.
    for handle in ("AltairVance", "JosieHart", "TerraOkafor", "RiverCalloway"):
        assert users[handle].xp == XP_PER_POST + 3 * XP_PER_VOTE


def test_seed_stores_only_password_hashes(settings):
    seed(settings)
    users, _, _ = _load(settings)
    plaintexts = set(SEED_PASSWORDS.values())
    for user in users.values():
        assert user.password_hash.startswith("$argon2id$")
        assert not any(pw in user.password_hash for pw in plaintexts)


def test_seeded_accounts_can_sign_in(seeded, client):
    assert login(client, "KobeLaing", SEED_PASSWORDS["seed_kobe_password"]).status_code == 200
    assert login(client, "KaraMercer", SEED_PASSWORDS["seed_kara_password"]).status_code == 200
    assert login(client, "RiverCalloway", SEED_PASSWORDS["seed_river_password"]).status_code == 200


def test_seed_refuses_to_run_without_passwords(settings):
    settings.seed_kara_password = None
    with pytest.raises(SeedConfigError, match="SEED_KARA_PASSWORD"):
        seed(settings)


def test_seed_is_idempotent_and_cleans_old_files(settings):
    seed(settings)
    first_files = set(Path(settings.upload_dir).iterdir())
    seed(settings)
    users, posts, _ = _load(settings)
    assert len(users) == 6 and len(posts) == 7
    files = set(Path(settings.upload_dir).iterdir())
    assert len(files) == 7
    assert not (files & first_files)  # previous run's files were removed


def test_seed_strips_image_metadata(settings):
    seed(settings)
    _, posts, _ = _load(settings)
    for p in posts:
        with Image.open(Path(settings.upload_dir) / p.media_key) as img:
            assert not img.getexif()
            assert "exif" not in img.info and "xmp" not in img.info


def test_seed_skips_missing_media(settings, seed_media_copy):
    (seed_media_copy / "realpainting4.jpg").unlink()
    settings.seed_media_dir = seed_media_copy
    result = seed(settings)
    assert result == {"users": 6, "posts": 6, "votes": 10, "skipped": 1}
