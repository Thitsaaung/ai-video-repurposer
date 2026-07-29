"""Supabase configuration foundation (Phase 0 — no auth logic).

Loads and validates env-based Supabase settings for FastAPI / Railway.
JWT verification, middleware, and client SDKs arrive in later phases.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import BACKEND_ROOT, Settings, get_settings

logger = logging.getLogger(__name__)

_REPO_ROOT = BACKEND_ROOT.parent

AppEnvironment = Literal["development", "production", "test"]


class SupabaseConfigError(ValueError):
    """Raised when Supabase env configuration is missing or invalid."""


class SupabaseSettings(BaseSettings):
    """Raw Supabase-related environment variables (backend)."""

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), str(BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "supabase_url"),
    )
    supabase_anon_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_ANON_KEY",
            "supabase_anon_key",
        ),
    )
    supabase_jwt_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_JWT_SECRET",
            "supabase_jwt_secret",
        ),
    )
    supabase_jwks_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_JWKS_URL",
            "supabase_jwks_url",
        ),
    )
    supabase_service_role_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY",
            "supabase_service_role_key",
        ),
    )

    @field_validator(
        "supabase_url",
        "supabase_anon_key",
        "supabase_jwt_secret",
        "supabase_jwks_url",
        "supabase_service_role_key",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@dataclass(frozen=True)
class SupabaseConfig:
    """Validated Supabase configuration object (safe to pass around)."""

    url: str
    anon_key: str
    jwt_secret: str | None
    jwks_url: str | None
    service_role_key: str | None
    environment: AppEnvironment

    @property
    def has_jwt_verification_material(self) -> bool:
        """True when Phase 1 JWT verification will have a secret or JWKS URL."""
        return bool(self.jwt_secret) or bool(self.jwks_url)

    def public_summary(self) -> dict[str, object]:
        """Log-/health-safe summary (no secrets)."""
        host = urlparse(self.url).hostname or "(unknown)"
        return {
            "url_host": host,
            "anon_key_present": bool(self.anon_key),
            "jwt_secret_present": bool(self.jwt_secret),
            "jwks_url_present": bool(self.jwks_url),
            "service_role_key_present": bool(self.service_role_key),
            "environment": self.environment,
        }


def normalize_app_environment(value: str | None) -> AppEnvironment:
    """Map APP_ENV / ENVIRONMENT into development | production | test."""
    raw = (value or "development").strip().lower()
    if raw in {"prod", "production"}:
        return "production"
    if raw in {"test", "testing", "ci"}:
        return "test"
    if raw in {"dev", "development", "local"}:
        return "development"
    # Staging/preview are config-strict like production (Railway-safe).
    if raw in {"staging", "preview"}:
        return "production"
    return "development"


def _validate_https_or_local_url(url: str, *, field_name: str) -> str:
    cleaned = url.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise SupabaseConfigError(
            f"{field_name} must be an http(s) URL (got scheme={parsed.scheme!r}).",
        )
    if not parsed.netloc:
        raise SupabaseConfigError(f"{field_name} is missing a host.")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "0.0.0.0"}:
        raise SupabaseConfigError(
            f"{field_name} must use https unless the host is localhost "
            f"(got host={host!r}).",
        )
    return cleaned


def _any_supabase_env_set(raw: SupabaseSettings) -> bool:
    return any(
        [
            raw.supabase_url,
            raw.supabase_anon_key,
            raw.supabase_jwt_secret,
            raw.supabase_jwks_url,
            raw.supabase_service_role_key,
        ],
    )


def validate_supabase_settings(
    raw: SupabaseSettings,
    *,
    environment: AppEnvironment,
    require_complete: bool | None = None,
) -> SupabaseConfig | None:
    """
    Validate raw settings into a ``SupabaseConfig``.

    - **production** (and staging/preview): always require a complete config.
    - **development / test:** if no Supabase env vars are set, return ``None``.
      If any var is set, require a complete set.

    Complete set (Phase 0):
    - ``SUPABASE_URL``
    - ``SUPABASE_ANON_KEY``
    - ``SUPABASE_JWT_SECRET`` **or** ``SUPABASE_JWKS_URL``

    ``SUPABASE_SERVICE_ROLE_KEY`` is optional in Phase 0 (never log its value).
    """
    if require_complete is None:
        require_complete = environment == "production"

    if not require_complete and not _any_supabase_env_set(raw):
        return None

    missing: list[str] = []
    if not raw.supabase_url:
        missing.append("SUPABASE_URL")
    if not raw.supabase_anon_key:
        missing.append("SUPABASE_ANON_KEY")
    if not raw.supabase_jwt_secret and not raw.supabase_jwks_url:
        missing.append("SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL")

    if missing:
        joined = ", ".join(missing)
        raise SupabaseConfigError(
            "Supabase configuration incomplete. Missing: "
            f"{joined}. See .env.example and docs/auth_implementation_plan.md "
            "(Phase 0).",
        )

    assert raw.supabase_url is not None
    assert raw.supabase_anon_key is not None

    url = _validate_https_or_local_url(raw.supabase_url, field_name="SUPABASE_URL")
    anon = raw.supabase_anon_key.strip()
    if len(anon) < 20:
        raise SupabaseConfigError(
            "SUPABASE_ANON_KEY looks too short; paste the anon/public key "
            "from the Supabase project settings.",
        )

    jwks_url: str | None = None
    if raw.supabase_jwks_url:
        jwks_url = _validate_https_or_local_url(
            raw.supabase_jwks_url,
            field_name="SUPABASE_JWKS_URL",
        )

    jwt_secret = (
        raw.supabase_jwt_secret.strip() if raw.supabase_jwt_secret else None
    )
    if jwt_secret is not None and len(jwt_secret) < 16:
        raise SupabaseConfigError(
            "SUPABASE_JWT_SECRET looks too short; use the JWT secret from "
            "Supabase Project Settings → API.",
        )

    service_role = (
        raw.supabase_service_role_key.strip()
        if raw.supabase_service_role_key
        else None
    )

    return SupabaseConfig(
        url=url,
        anon_key=anon,
        jwt_secret=jwt_secret,
        jwks_url=jwks_url,
        service_role_key=service_role,
        environment=environment,
    )


@lru_cache
def get_supabase_settings() -> SupabaseSettings:
    return SupabaseSettings()


def load_supabase_config(
    settings: Settings | None = None,
    *,
    raw: SupabaseSettings | None = None,
) -> SupabaseConfig | None:
    """Load and validate Supabase config for the current app environment."""
    app_settings = settings if settings is not None else get_settings()
    environment = normalize_app_environment(app_settings.app_env)
    source = raw if raw is not None else get_supabase_settings()
    return validate_supabase_settings(source, environment=environment)


def assert_supabase_config_at_startup(settings: Settings) -> SupabaseConfig | None:
    """
    Fail-fast at API startup when Supabase config is required but invalid.

    - production: must load a complete ``SupabaseConfig`` or raise.
    - development/test: optional; logs a clear warning when absent.
    """
    environment = normalize_app_environment(settings.app_env)
    try:
        config = validate_supabase_settings(
            get_supabase_settings(),
            environment=environment,
        )
    except SupabaseConfigError as exc:
        logger.error("Supabase configuration invalid: %s", exc)
        raise RuntimeError(
            f"Supabase configuration invalid for APP_ENV={environment!r}: {exc}",
        ) from exc

    if config is None:
        logger.warning(
            "Supabase is not configured (APP_ENV=%s). "
            "Phase 0 allows this in development/test only. "
            "Set SUPABASE_URL, SUPABASE_ANON_KEY, and "
            "SUPABASE_JWT_SECRET (or SUPABASE_JWKS_URL) before Phase 1.",
            environment,
        )
        return None

    summary = config.public_summary()
    logger.info(
        "Supabase config OK — host=%s env=%s anon_key=%s jwt_secret=%s "
        "jwks=%s service_role=%s",
        summary["url_host"],
        summary["environment"],
        summary["anon_key_present"],
        summary["jwt_secret_present"],
        summary["jwks_url_present"],
        summary["service_role_key_present"],
    )
    return config


def clear_supabase_settings_cache() -> None:
    """Test helper: reset cached settings."""
    get_supabase_settings.cache_clear()
