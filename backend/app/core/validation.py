"""Shared validation helpers for API inputs."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
    "www.youtu.be",
}


def validate_job_id(job_id: str) -> str:
    """Ensure ``job_id`` looks like a UUID (as produced by the job store)."""
    value = (job_id or "").strip()
    if not _UUID_RE.match(value):
        raise HTTPException(status_code=422, detail="Invalid job_id format")
    return value


def assert_youtube_url(url: str) -> str:
    """
    Return ``url`` if it is a supported YouTube link; otherwise raise ValueError.

    Safe to use inside Pydantic field validators.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("A YouTube URL is required")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")

    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        raise ValueError("Only YouTube URLs are supported")

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
        if not video_id:
            raise ValueError("Missing YouTube video id")
        return raw

    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id:
        return raw

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v", "watch"}:
        return raw

    raise ValueError("Could not find a YouTube video id in the URL")
