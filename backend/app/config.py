"""Deployment configuration, read only from environment variables (and .env).

Game rules (XP values, rank thresholds) are NOT here; they live in
app/progression.py so a stray env var can't change the economy. Scanner
weights live in app/scanner/scanner.toml for the same reason.

Secrets (SESSION_SECRET, seed passwords) are typed as SecretStr so they never
show up if the settings object is printed or logged.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'var' / 'mirage.db').as_posix()}"
    upload_dir: Path = BACKEND_DIR / "var" / "uploads"
    public_api_url: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:3000"

    # No default on purpose: the app refuses to start without a signing key,
    # because a guessable key would let anyone forge a session cookie.
    session_secret: SecretStr
    session_ttl_minutes: int = Field(default=240, ge=5, le=24 * 60)
    # Browsers treat http://localhost as a secure context, so Secure cookies work
    # in local development too. Only turn this off for unusual local setups.
    cookie_secure: bool = True

    max_image_bytes: int = 10 * 1024 * 1024
    max_video_bytes: int = 50 * 1024 * 1024
    max_image_pixels: int = 40_000_000

    rate_limit_posts_per_hour: int = 10
    rate_limit_votes_per_minute: int = 120
    rate_limit_reactions_per_minute: int = 120
    rate_limit_comments_per_minute: int = 10
    rate_limit_scans_per_hour: int = 20
    # Login attempts in a 15-minute window, counted per client IP and per username.
    rate_limit_login_per_ip: int = 30
    rate_limit_login_per_username: int = 10

    log_level: str = "INFO"
    seed_media_dir: Path = BACKEND_DIR.parent / "seed-media"

    # Seed account passwords. Only the seed script reads these; they are never
    # hardcoded in source. Missing ones make the seed script stop with an error.
    seed_kobe_password: SecretStr | None = None
    seed_kara_password: SecretStr | None = None
    seed_altair_password: SecretStr | None = None
    seed_josie_password: SecretStr | None = None
    seed_terra_password: SecretStr | None = None
    seed_river_password: SecretStr | None = None

    # Optional face-swap model for the scanner (see README "AI Authenticity Scanner").
    deepfake_model_path: Path | None = None

    @field_validator("upload_dir", "seed_media_dir")
    @classmethod
    def _relative_to_backend(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("deepfake_model_path")
    @classmethod
    def _optional_relative_to_backend(cls, value: Path | None) -> Path | None:
        if value is None or str(value) == "":
            return None
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("database_url")
    @classmethod
    def _sqlite_relative_to_backend(cls, value: str) -> str:
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            return f"sqlite:///{(BACKEND_DIR / value[len(prefix):]).resolve().as_posix()}"
        return value

    @field_validator("session_secret")
    @classmethod
    def _strong_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_SECRET_LENGTH:
            raise ValueError(f"SESSION_SECRET must be at least {MIN_SECRET_LENGTH} characters")
        return value

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
