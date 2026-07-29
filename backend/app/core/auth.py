"""Supabase JWT verification and authenticated user identity (Phase 1).

No profiles, ownership, teams, or API keys — verify Bearer tokens only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.supabase_config import (
    SupabaseConfig,
    load_supabase_config,
    normalize_app_environment,
)

logger = logging.getLogger(__name__)

# Clock skew allowance (seconds) for Railway / client clock drift.
_JWT_LEEWAY_SECONDS = 30

# Dev-only identity when AUTH_DISABLED or Supabase unset in development.
_DEV_USER_ID = "00000000-0000-0000-0000-000000000000"


class AuthError(Exception):
    """Token missing or invalid (maps to HTTP 401)."""

    def __init__(self, detail: str = "Could not validate credentials") -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Identity extracted from a verified Supabase access token."""

    user_id: str
    email: str | None = None
    role: str | None = None  # Supabase JWT ``role`` claim (e.g. authenticated)


def auth_is_enforced(settings: Settings | None = None) -> bool:
    """
    Whether protected routes must receive a valid JWT.

    - ``AUTH_DISABLED=true`` only honored outside production.
    - If Supabase config is absent (development/test only), auth is not enforced
      so local CLI/API smoke still works without tokens.
    """
    app_settings = settings or get_settings()
    environment = normalize_app_environment(app_settings.app_env)

    if app_settings.auth_disabled:
        if environment == "production":
            logger.error(
                "AUTH_DISABLED is set but APP_ENV is production — ignoring bypass",
            )
        else:
            logger.warning(
                "AUTH_DISABLED=true — JWT not required (non-production only)",
            )
            return False

    config = load_supabase_config(app_settings)
    if config is None:
        # Only reachable in development/test (production fails at startup).
        return False

    return True


def _issuer_for(config: SupabaseConfig) -> str:
    return f"{config.url.rstrip('/')}/auth/v1"


def _decode_with_secret(token: str, config: SupabaseConfig) -> dict[str, Any]:
    if not config.jwt_secret:
        raise AuthError("Server JWT secret is not configured")
    return jwt.decode(
        token,
        config.jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
        issuer=_issuer_for(config),
        leeway=_JWT_LEEWAY_SECONDS,
        options={"require": ["exp", "sub"]},
    )


def _decode_with_jwks(token: str, config: SupabaseConfig) -> dict[str, Any]:
    if not config.jwks_url:
        raise AuthError("Server JWKS URL is not configured")
    jwks_client = PyJWKClient(config.jwks_url, cache_keys=True)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience="authenticated",
        issuer=_issuer_for(config),
        leeway=_JWT_LEEWAY_SECONDS,
        options={"require": ["exp", "sub"]},
    )


def verify_supabase_access_token(
    token: str,
    config: SupabaseConfig,
) -> AuthenticatedUser:
    """
    Verify a Supabase access token and return ``AuthenticatedUser``.

    Prefers ``SUPABASE_JWT_SECRET`` (HS256) when set; otherwise JWKS.
    Never logs the raw token.
    """
    cleaned = (token or "").strip()
    if not cleaned:
        raise AuthError("Not authenticated")

    try:
        if config.jwt_secret:
            claims = _decode_with_secret(cleaned, config)
        else:
            claims = _decode_with_jwks(cleaned, config)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthError("Invalid token audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthError("Invalid token issuer") from exc
    except jwt.PyJWTError as exc:
        logger.info("JWT verification failed: %s", type(exc).__name__)
        raise AuthError("Could not validate credentials") from exc

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise AuthError("Token missing subject")

    email = claims.get("email")
    if email is not None and not isinstance(email, str):
        email = None

    role = claims.get("role")
    if role is not None and not isinstance(role, str):
        role = None

    return AuthenticatedUser(
        user_id=user_id.strip(),
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        role=role,
    )


def development_bypass_user() -> AuthenticatedUser:
    """Synthetic user when auth is not enforced (local smoke only)."""
    return AuthenticatedUser(
        user_id=_DEV_USER_ID,
        email=None,
        role="authenticated",
    )
