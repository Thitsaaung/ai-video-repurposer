"""Application settings loaded from environment (and optional ``.env`` files)."""

from __future__ import annotations

import base64
import binascii
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
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
        populate_by_name=True,
    )

    app_name: str = "AI Video Repurposer API"
    # development | production | test (also accepts prod/dev/local/staging)
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices(
            "APP_ENV",
            "ENVIRONMENT",
            "app_env",
        ),
    )
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
    )

    # YouTube / yt-dlp cookie auth (Phase 1). Never log these values.
    youtube_cookies_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "YOUTUBE_COOKIES_FILE",
            "youtube_cookies_file",
        ),
    )
    youtube_cookies_base64: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "YOUTUBE_COOKIES_BASE64",
            "youtube_cookies_base64",
        ),
    )

    # Editorial padding applied only at cut time (not in curated JSON).
    clip_pad_start_seconds: float = Field(
        default=3.0,
        validation_alias=AliasChoices(
            "CLIP_PAD_START_SECONDS",
            "clip_pad_start_seconds",
        ),
    )
    clip_pad_end_seconds: float = Field(
        default=1.0,
        validation_alias=AliasChoices(
            "CLIP_PAD_END_SECONDS",
            "clip_pad_end_seconds",
        ),
    )

    # Storage cleanup / retention (disk hygiene for downloads, temps, clips).
    storage_cleanup_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "STORAGE_CLEANUP_ENABLED",
            "storage_cleanup_enabled",
        ),
    )
    storage_cleanup_interval_minutes: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "STORAGE_CLEANUP_INTERVAL_MINUTES",
            "storage_cleanup_interval_minutes",
        ),
    )
    storage_downloads_retention_hours: float = Field(
        default=24.0,
        validation_alias=AliasChoices(
            "STORAGE_DOWNLOADS_RETENTION_HOURS",
            "storage_downloads_retention_hours",
        ),
    )
    storage_transcripts_retention_hours: float = Field(
        default=24.0,
        validation_alias=AliasChoices(
            "STORAGE_TRANSCRIPTS_RETENTION_HOURS",
            "storage_transcripts_retention_hours",
        ),
    )
    storage_clips_retention_hours: float = Field(
        default=48.0,
        validation_alias=AliasChoices(
            "STORAGE_CLIPS_RETENTION_HOURS",
            "storage_clips_retention_hours",
        ),
    )
    storage_temp_retention_hours: float = Field(
        default=1.0,
        validation_alias=AliasChoices(
            "STORAGE_TEMP_RETENTION_HOURS",
            "storage_temp_retention_hours",
        ),
    )
    storage_failed_job_retention_hours: float = Field(
        default=12.0,
        validation_alias=AliasChoices(
            "STORAGE_FAILED_JOB_RETENTION_HOURS",
            "storage_failed_job_retention_hours",
        ),
    )
    storage_completed_job_retention_hours: float = Field(
        default=48.0,
        validation_alias=AliasChoices(
            "STORAGE_COMPLETED_JOB_RETENTION_HOURS",
            "storage_completed_job_retention_hours",
        ),
    )

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

    @field_validator("app_env")
    @classmethod
    def _normalize_app_env(cls, value: str) -> str:
        return (value or "development").strip().lower() or "development"

    @field_validator("youtube_cookies_file", "youtube_cookies_base64", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("clip_pad_start_seconds", "clip_pad_end_seconds")
    @classmethod
    def _non_negative_pad(cls, value: float) -> float:
        if value < 0:
            raise ValueError("clip padding seconds must be >= 0")
        return float(value)

    @field_validator(
        "storage_cleanup_interval_minutes",
        "storage_downloads_retention_hours",
        "storage_transcripts_retention_hours",
        "storage_clips_retention_hours",
        "storage_temp_retention_hours",
        "storage_failed_job_retention_hours",
        "storage_completed_job_retention_hours",
    )
    @classmethod
    def _positive_storage_numbers(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("storage retention/interval values must be > 0")
        return float(value)

    @property
    def project_root(self) -> Path:
        """Application root (backend/). Kept name for existing callers."""
        return BACKEND_ROOT

    @property
    def output_clips_dir(self) -> Path:
        path = BACKEND_ROOT / "output_clips"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def downloads_dir(self) -> Path:
        path = BACKEND_ROOT / "downloads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def transcripts_dir(self) -> Path:
        path = BACKEND_ROOT / "transcripts"
        path.mkdir(parents=True, exist_ok=True)
        return path


def _env_cookie_value(name: str) -> str | None:
    """Read a cookie-related env var (case-insensitive key match). Never log value."""
    target = name.upper()
    for key, value in os.environ.items():
        if key.upper() == target:
            cleaned = value.strip() if isinstance(value, str) else ""
            return cleaned or None
    return None


def _write_cookies_from_base64(encoded: str) -> Path:
    """Decode Netscape cookies from base64 into a restricted temp file (mode 0600)."""
    # Railway / paste UIs often inject whitespace or newlines into secrets.
    normalized = "".join(encoded.split())
    missing_padding = len(normalized) % 4
    if missing_padding:
        normalized += "=" * (4 - missing_padding)

    try:
        raw = base64.b64decode(normalized, validate=False)
    except binascii.Error as exc:
        raise ValueError("YOUTUBE_COOKIES_BASE64 is not valid base64") from exc

    if not raw.strip():
        raise ValueError("YOUTUBE_COOKIES_BASE64 decoded to an empty cookie file")

    fd, name = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Best-effort on platforms that ignore POSIX modes.
            pass
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

    env_file_set = _env_cookie_value("YOUTUBE_COOKIES_FILE") is not None
    env_b64_set = _env_cookie_value("YOUTUBE_COOKIES_BASE64") is not None
    logger.info(
        "YouTube cookie env: YOUTUBE_COOKIES_FILE_present=%s "
        "YOUTUBE_COOKIES_BASE64_present=%s settings_file=%s settings_base64=%s",
        env_file_set,
        env_b64_set,
        bool(settings.youtube_cookies_file),
        bool(settings.youtube_cookies_base64),
    )

    # Prefer Settings, fall back to raw environ (Railway / case variants).
    file_value = settings.youtube_cookies_file or _env_cookie_value(
        "YOUTUBE_COOKIES_FILE",
    )
    if file_value:
        candidate = Path(file_value).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        logger.warning(
            "YOUTUBE_COOKIES_FILE is set but file was not found; trying base64 next",
        )

    encoded = settings.youtube_cookies_base64 or _env_cookie_value(
        "YOUTUBE_COOKIES_BASE64",
    )
    if encoded:
        try:
            path = _write_cookies_from_base64(encoded)
        except Exception:
            logger.exception("Failed to materialize YOUTUBE_COOKIES_BASE64")
            return None
        return str(path)

    return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
