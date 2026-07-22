"""Background video job runner — wires FastAPI jobs to the offline engine."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.services import job_store

logger = logging.getLogger(__name__)

# Repo root (…/ai-video-repurposer) so ``from services.engine import …`` resolves
# when uvicorn is started from ``backend/``.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.engine import process_video_to_clips  # noqa: E402


def process_video_job(job_id: str, url: str) -> None:
    """
    Run the real video pipeline for a job (background).

    Status flow: ``queued`` → ``processing`` → ``completed`` | ``failed``.
    On success, stores ``video_path``, ``curated_json_path``, ``output_clip_paths``.
    """
    updated = job_store.update_job_status(job_id, "processing")
    if updated is None:
        logger.error("Cannot process unknown job_id=%s url=%s", job_id, url)
        return

    logger.info("Job %s processing started for url=%s", job_id, url)

    try:
        result = process_video_to_clips(url)

        if result.get("status") == "success":
            job_store.update_job(
                job_id,
                status="completed",
                video_path=result.get("video_path"),
                curated_json_path=result.get("curated_json_path"),
                output_clip_paths=result.get("output_clip_paths") or [],
                error=None,
            )
            logger.info(
                "Job %s completed — %s clip(s)",
                job_id,
                len(result.get("output_clip_paths") or []),
            )
            return

        message = result.get("message") or "Engine returned an error status"
        job_store.update_job(
            job_id,
            status="failed",
            error=str(message),
        )
        logger.error("Job %s failed: %s", job_id, message)

    except Exception as exc:
        logger.exception("Job %s failed with exception: %s", job_id, exc)
        job_store.update_job(
            job_id,
            status="failed",
            error=str(exc),
        )
