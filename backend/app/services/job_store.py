"""In-memory job registry for the HTTP API (not persisted; process-local)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.enums import JobStatus

logger = logging.getLogger(__name__)

# Optional progress detail while status == processing. Cleared on terminal states.
ALLOWED_STAGES = frozenset(
    {
        "downloading",
        "transcribing",
        "curating",
        "creating_clips",
    }
)

# job_id → job dict. Cleared when the process restarts.
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()


def create_job(url: str) -> dict[str, Any]:
    """Create a queued job for ``url`` and store it in memory."""
    job_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    job: dict[str, Any] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED.value,
        "url": url,
        "created_at": now,
        "updated_at": now,
        "video_path": None,
        "curated_json_path": None,
        "output_clip_paths": None,
        "error": None,
        "stage": None,
    }
    with _lock:
        _jobs[job_id] = job
        logger.info("Created job_id=%s status=%s", job_id, JobStatus.QUEUED.value)
        return dict(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return a copy of the job, or ``None`` if unknown."""
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None


def list_jobs() -> list[dict[str, Any]]:
    """Return copies of all in-memory jobs."""
    with _lock:
        return [dict(job) for job in _jobs.values()]


def delete_job(job_id: str) -> bool:
    """
    Remove a job from the registry.

    Returns ``True`` if removed. Refuses to delete active (queued/processing) jobs.
    """
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return False
        status = job.get("status")
        if status in {JobStatus.QUEUED.value, JobStatus.PROCESSING.value}:
            logger.warning(
                "Refusing to delete active job_id=%s status=%s",
                job_id,
                status,
            )
            return False
        del _jobs[job_id]
        logger.info("Deleted job_id=%s status=%s", job_id, status)
        return True


def update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    """
    Merge ``fields`` into an existing job.

    Allowed extras: ``status``, ``video_path``, ``curated_json_path``,
    ``output_clip_paths``, ``error``, ``stage``. Returns updated copy or ``None``.
    """
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None

        allowed = {
            "status",
            "video_path",
            "curated_json_path",
            "output_clip_paths",
            "error",
            "stage",
        }
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"Unsupported job field: {key}")
            if key == "status":
                if isinstance(value, JobStatus):
                    value = value.value
                elif value not in {s.value for s in JobStatus}:
                    raise ValueError(f"Unsupported job status: {value}")
            if key == "stage" and value is not None and value not in ALLOWED_STAGES:
                raise ValueError(f"Unsupported job stage: {value}")
            job[key] = value

        job["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.debug(
            "Updated job_id=%s fields=%s",
            job_id,
            {k: fields[k] for k in fields if k != "error"},
        )
        return dict(job)


def update_job_status(
    job_id: str,
    status: JobStatus | str,
    error: str | None = None,
) -> dict[str, Any] | None:
    """
    Update ``status`` for an existing job.

    Optionally set ``error`` when failing; clears ``error`` when not failed.
    """
    status_value = status.value if isinstance(status, JobStatus) else status
    fields: dict[str, Any] = {"status": status_value}
    if error is not None:
        fields["error"] = error
    elif status_value != JobStatus.FAILED.value:
        fields["error"] = None
    return update_job(job_id, **fields)
