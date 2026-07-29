"""FastAPI entry point for the AI Video Repurposer backend."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.routes.media import router as media_router
from app.routes.videos import router as videos_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="HTTP API for submitting YouTube videos to the clip pipeline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos_router)
app.include_router(media_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    logger.warning(
        "HTTP %s %s → %s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.info(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    # jsonable_encoder strips non-JSON ctx (e.g. embedded ValueError).
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "Starting %s — app_env=%s cors_origins=%s output_clips=%s "
        "cleanup_enabled=%s",
        settings.app_name,
        settings.app_env,
        settings.cors_origins,
        settings.output_clips_dir,
        settings.storage_cleanup_enabled,
    )
    # Phase 0–1: validate Supabase env; JWT enforced on protected routes when configured.
    # Production fails fast on missing/invalid config; development may omit.
    from app.core.auth import auth_is_enforced
    from app.core.supabase_config import assert_supabase_config_at_startup

    assert_supabase_config_at_startup(settings)
    logger.info(
        "Auth enforcement active=%s (AUTH_DISABLED=%s)",
        auth_is_enforced(settings),
        settings.auth_disabled,
    )

    # Best-effort disk hygiene; never raises into ASGI startup.
    try:
        from app.services.storage_cleanup import run_startup_cleanup

        run_startup_cleanup()
    except Exception:
        logger.exception("Storage cleanup startup failed (ignored)")
