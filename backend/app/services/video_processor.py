"""Background video job runner — wires FastAPI jobs to the offline engine."""

from __future__ import annotations

import logging
import threading

from app.core.enums import JobStatus
from app.core.user_errors import to_user_facing_error
from app.services import job_store
from services.engine import process_video_to_clips

logger = logging.getLogger(__name__)

# Serialize pipeline runs so shared temp files (temp.srt / temp_audio.mp3)
# are not corrupted by concurrent BackgroundTasks — without changing the engine.
_pipeline_lock = threading.Lock()


def process_video_job(job_id: str, url: str) -> None:
    """
    Run the real video pipeline for a job (background).

    Status flow: ``queued`` → ``processing`` → ``completed`` | ``failed``.
    Optional ``stage`` is updated via engine progress callbacks; cleared on
    terminal status. On success, stores ``video_path``, ``curated_json_path``,
    ``output_clip_paths``.
    """
    updated = job_store.update_job_status(job_id, JobStatus.PROCESSING)
    if updated is None:
        logger.error("Cannot process unknown job_id=%s url=%s", job_id, url)
        return

    logger.info("Job %s processing started url=%s", job_id, url)

    def on_progress(stage: str) -> None:
        """Persist engine stage names onto the job (HTTP/job ownership stays here)."""
        job_store.update_job(job_id, stage=stage)
        logger.info("Job %s stage=%s", job_id, stage)

    try:
        with _pipeline_lock:
            result = process_video_to_clips(url, on_progress=on_progress)

        if result.get("status") == "success":
            clip_count = len(result.get("output_clip_paths") or [])
            job_store.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                video_path=result.get("video_path"),
                curated_json_path=result.get("curated_json_path"),
                output_clip_paths=result.get("output_clip_paths") or [],
                error=None,
                stage=None,
            )
            logger.info("Job %s completed clip_count=%s", job_id, clip_count)
            return

        message = result.get("message") or "Engine returned an error status"
        logger.error("Job %s failed: %s", job_id, message)
        job_store.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=to_user_facing_error(message),
            stage=None,
        )

    except Exception as exc:
        logger.exception("Job %s failed with exception: %s", job_id, exc)
        job_store.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=to_user_facing_error(str(exc)),
            stage=None,
        )
