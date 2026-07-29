"""FastAPI dependencies for authentication (Phase 1)."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import (
    AuthError,
    AuthenticatedUser,
    auth_is_enforced,
    development_bypass_user,
    verify_supabase_access_token,
)
from app.core.config import get_settings
from app.core.supabase_config import load_supabase_config

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def _extract_bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Prefer Authorization: Bearer; allow ``access_token`` query for media."""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = (credentials.credentials or "").strip()
        if token:
            return token

    query_token = request.query_params.get("access_token")
    if isinstance(query_token, str) and query_token.strip():
        return query_token.strip()

    return None


async def require_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    """
    Require a valid Supabase JWT (or local auth bypass).

    Raises ``401`` when auth is enforced and the token is missing/invalid.
    """
    settings = get_settings()
    if not auth_is_enforced(settings):
        return development_bypass_user()

    config = load_supabase_config(settings)
    if config is None:
        # Should not happen when enforced; fail closed.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    token = _extract_bearer_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = verify_supabase_access_token(token, config)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    logger.debug("Authenticated user_id=%s", user.user_id)
    return user
