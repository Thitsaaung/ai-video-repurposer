"""Convert internal absolute paths into API-safe public values."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _basename(path_value: str | None) -> str | None:
    if not path_value:
        return None
    return Path(path_value).name


def _project_relative(path_value: str | None) -> str | None:
    """Return a repo-relative POSIX path when possible, else the basename."""
    if not path_value:
        return None
    path = Path(path_value)
    try:
        relative = path.resolve().relative_to(get_settings().project_root.resolve())
        return relative.as_posix()
    except ValueError:
        return path.name


def clip_media_url(path_or_name: str) -> str:
    """Public relative URL for preview/download under ``/media/clips``."""
    return f"/media/clips/{Path(path_or_name).name}"


def to_public_job(job: dict[str, Any]) -> dict[str, Any]:
    """
    Copy a job dict for API responses without absolute filesystem paths.

    - ``video_path`` → filename
    - ``curated_json_path`` → project-relative path when possible
    - ``output_clip_paths`` → ``/media/clips/{filename}``
    """
    public = dict(job)
    public["video_path"] = _basename(job.get("video_path"))
    public["curated_json_path"] = _project_relative(job.get("curated_json_path"))

    clips = job.get("output_clip_paths")
    if clips is None:
        public["output_clip_paths"] = None
    else:
        public["output_clip_paths"] = [clip_media_url(p) for p in clips]

    return public
