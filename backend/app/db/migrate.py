from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False  # keep our JSON logging
    return cfg


def upgrade_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")
