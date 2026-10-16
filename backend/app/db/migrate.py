from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR


def alembic_config(database_url: str, upload_dir: Path | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False  # keep our JSON logging
    # Data migrations that touch stored media (0003) need to know where it lives.
    if upload_dir is not None:
        cfg.attributes["upload_dir"] = str(upload_dir)
    return cfg


def upgrade_head(database_url: str, upload_dir: Path | None = None) -> None:
    command.upgrade(alembic_config(database_url, upload_dir), "head")
