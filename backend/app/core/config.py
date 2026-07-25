"""Application settings loaded from environment (and optional ``.env`` files)."""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → backend/ (Railway / API application root)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
# Monorepo root (local .env may still live here during development)
_REPO_ROOT = BACKEND_ROOT.parent

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration for the FastAPI app."""

    model_config = SettingsConfigDict(
        # backend/.env wins over repo-root .env when both define a key
        env_file=(str(_REPO_ROOT / ".env"), str(BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI Video Repurposer API"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
    )

    # YouTube / yt-dlp cookie auth (Phase 1). Never log these values.
    youtube_cookies_file: str | None = None
    youtube_cookies_base64: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("youtube_cookies_file", "youtube_cookies_base64", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def project_root(self) -> Path:
        """Application root (backend/). Kept name for existing callers."""
        return BACKEND_ROOT

    @property
    def output_clips_dir(self) -> Path:
        path = BACKEND_ROOT / "output_clips"
        path.mkdir(parents=True, exist_ok=True)
        return path


def _write_cookies_from_base64(encoded: str) -> Path:
    """Decode Netscape cookies from base64 into a restricted temp file."""
    raw = base64.b64decode(encoded.strip(), validate=False)
    # Netscape cookie files are text; reject empty payloads.
    if not raw.strip():
        raise ValueError("YOUTUBE_COOKIES_BASE64 decoded to an empty cookie file")

    fd, name = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.chmod(path, 0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


@lru_cache
def resolve_youtube_cookiefile() -> str | None:
    """
    Resolve a Netscape cookies path for yt-dlp ``cookiefile``.

    Order:
    1. ``YOUTUBE_COOKIES_FILE`` when the path exists
    2. ``YOUTUBE_COOKIES_BASE64`` written once to a temp file
    3. ``None`` (continue without cookies)
    """
    settings = get_settings()

    file_value = settings.youtube_cookies_file
    if file_value:
        candidate = Path(file_value).expanduser()
        if candidate.is_file():
            resolved = str(candidate.resolve())
            logger.info("Using YouTube cookies from YOUTUBE_COOKIES_FILE")
            return resolved
        logger.warning(
            "YOUTUBE_COOKIES_FILE is set but file was not found; trying base64 next",
        )

    encoded = settings.youtube_cookies_base64
    if encoded:
        try:
            path = _write_cookies_from_base64(encoded)
        except Exception:
            logger.exception("Failed to materialize YOUTUBE_COOKIES_BASE64")
            return None
        logger.info("Using YouTube cookies from YOUTUBE_COOKIES_BASE64 (temp file)")
        return str(path)

    return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
