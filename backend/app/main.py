"""FastAPI entry point for the AI Video Repurposer backend."""

from __future__ import annotations

from fastapi import FastAPI

from app.routes.videos import router as videos_router

app = FastAPI(
    title="AI Video Repurposer API",
    description="HTTP API for submitting YouTube videos to the clip pipeline.",
    version="0.1.0",
)

app.include_router(videos_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok"}
