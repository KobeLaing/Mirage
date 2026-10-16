"""Data migration: remove the three seeded video posts from existing databases.

The seed no longer creates them, but databases seeded earlier still have them.

How the posts are found: videos are stored byte-for-byte (they are never
re-encoded), so a stored seed video has exactly the same SHA-256 as the
original file. We hash each stored video and delete the post only on an exact
match. A video a user uploaded can never match by accident, unlike matching on
author or caption.

Votes and reactions on those posts are removed by ON DELETE CASCADE. Voters
keep the XP they earned, the same as when an author deletes their own post.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16
"""
import hashlib
import os
from pathlib import Path

from alembic import context, op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# SHA-256 of seed-media/ai-video-1.mp4, ai-video-2.mp4 and real-video-1.mp4.
SEED_VIDEO_HASHES = frozenset({
    "38ae40360ac62e3a064e57327ed45b2ac1b0f7c6614b10cc9b3cbddcc859e3d6",
    "a118b256b3c0a8c99d061a91f93ea38a023baaab2f03e9135422e7fc2a5ad5cb",
    "e2bc75c707a101582d3b23d51731ccc3580dcb560e2e92c4ea95393d75c8fccb",
})

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def _upload_dir() -> Path:
    # Passed in by app.db.migrate when the app or seed runs migrations; falls
    # back to UPLOAD_DIR / the default for a bare `alembic upgrade head`.
    configured = context.config.attributes.get("upload_dir") or os.environ.get("UPLOAD_DIR") or "var/uploads"
    path = Path(configured)
    return path if path.is_absolute() else (_BACKEND_DIR / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upgrade() -> None:
    posts = sa.table("posts", sa.column("id", sa.Integer), sa.column("media_key", sa.String), sa.column("media_kind", sa.String))
    bind = op.get_bind()
    upload_dir = _upload_dir()

    doomed: list[tuple[int, Path]] = []
    for post_id, key in bind.execute(sa.select(posts.c.id, posts.c.media_key).where(posts.c.media_kind == "video")):
        file = upload_dir / key
        if file.parent == upload_dir and file.is_file() and _sha256(file) in SEED_VIDEO_HASHES:
            doomed.append((post_id, file))

    if doomed:
        bind.execute(sa.delete(posts).where(posts.c.id.in_([post_id for post_id, _ in doomed])))
    # Files go only after the rows: a crash in between leaves an orphaned file,
    # never a post pointing at a missing file.
    for _, file in doomed:
        file.unlink(missing_ok=True)


def downgrade() -> None:
    # Deleted demo content can't be restored by a migration; re-run the seed instead.
    pass
