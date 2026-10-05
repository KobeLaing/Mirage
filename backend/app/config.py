"""Deployment configuration, read only from environment variables (and .env).

Game rules (XP values, rank thresholds) are NOT here; they live in
app/progression.py so a stray env var can't change the economy.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'var' / 'mirage.db').as_posix()}"
    upload_dir: Path = BACKEND_DIR / "var" / "uploads"
    public_api_url: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:3000"
    auth_mode: Literal["dev_header"] = "dev_header"

    max_image_bytes: int = 10 * 1024 * 1024
    max_video_bytes: int = 50 * 1024 * 1024
    max_image_pixels: int = 40_000_000

    rate_limit_posts_per_hour: int = 10
    rate_limit_votes_per_minute: int = 120
    rate_limit_reactions_per_minute: int = 120

    log_level: str = "INFO"
    seed_media_dir: Path = BACKEND_DIR.parent / "seed-media"

    @field_validator("upload_dir", "seed_media_dir")
    @classmethod
    def _relative_to_backend(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("database_url")
    @classmethod
    def _sqlite_relative_to_backend(cls, value: str) -> str:
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            return f"sqlite:///{(BACKEND_DIR / value[len(prefix):]).resolve().as_posix()}"
        return value

    @model_validator(mode="after")
    def _no_dev_auth_in_production(self) -> "Settings":
        if self.environment == "production" and self.auth_mode == "dev_header":
            raise ValueError(
                "AUTH_MODE=dev_header trusts a client-supplied user id and must not run in production"
            )
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
