"""Application settings loaded from environment (and optional ``.env`` files)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → backend/ (Railway / API application root)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
# Monorepo root (local .env may still live here during development)
_REPO_ROOT = BACKEND_ROOT.parent


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

    @property
    def project_root(self) -> Path:
        """Application root (backend/). Kept name for existing callers."""
        return BACKEND_ROOT

    @property
    def output_clips_dir(self) -> Path:
        path = BACKEND_ROOT / "output_clips"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
