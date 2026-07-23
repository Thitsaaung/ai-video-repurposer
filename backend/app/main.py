"""FastAPI entry point for the AI Video Repurposer backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.media import router as media_router
from app.routes.videos import router as videos_router

# backend/app/main.py → repo root (contains output_clips/)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_CLIPS_DIR = _PROJECT_ROOT / "output_clips"
_OUTPUT_CLIPS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AI Video Repurposer API",
    description="HTTP API for submitting YouTube videos to the clip pipeline.",
    version="0.1.0",
)

# Allow the Next.js dev server to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos_router)
# Download route must be registered before the /media/clips static mount.
app.include_router(media_router)

# Serve generated MP4s for in-browser preview (does not touch the AI pipeline).
app.mount(
    "/media/clips",
    StaticFiles(directory=str(_OUTPUT_CLIPS_DIR)),
    name="clips",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok"}
