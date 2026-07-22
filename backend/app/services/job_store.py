"""In-memory job registry for the HTTP API (not persisted; process-local)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# job_id → job dict. Cleared when the process restarts.
_jobs: dict[str, dict[str, Any]] = {}


def create_job(url: str) -> dict[str, Any]:
    """Create a queued job for ``url`` and store it in memory."""
    job_id = str(uuid4())
    job: dict[str, Any] = {
        "job_id": job_id,
        "status": "queued",
        "url": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_path": None,
        "curated_json_path": None,
        "output_clip_paths": None,
        "error": None,
    }
    _jobs[job_id] = job
    return dict(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return a copy of the job, or ``None`` if unknown."""
    job = _jobs.get(job_id)
    return dict(job) if job is not None else None


def update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    """
    Merge ``fields`` into an existing job.

    Allowed extras: ``status``, ``video_path``, ``curated_json_path``,
    ``output_clip_paths``, ``error``. Returns updated copy or ``None``.
    """
    job = _jobs.get(job_id)
    if job is None:
        return None

    allowed = {
        "status",
        "video_path",
        "curated_json_path",
        "output_clip_paths",
        "error",
    }
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"Unsupported job field: {key}")
        job[key] = value
    return dict(job)


def update_job_status(
    job_id: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any] | None:
    """
    Update ``status`` for an existing job.

    Optionally set ``error`` when failing; clears ``error`` when not failed.
    """
    fields: dict[str, Any] = {"status": status}
    if error is not None:
        fields["error"] = error
    elif status != "failed":
        fields["error"] = None
    return update_job(job_id, **fields)
