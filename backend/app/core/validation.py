"""Shared validation helpers for API inputs."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException

from app.core.user_errors import INVALID_YOUTUBE_LINK_MESSAGE

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

    Safe to use inside Pydantic field validators. Client-facing message is
    intentionally generic (see ``user_errors.INVALID_YOUTUBE_LINK_MESSAGE``).
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError(INVALID_YOUTUBE_LINK_MESSAGE)

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(INVALID_YOUTUBE_LINK_MESSAGE)

    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        raise ValueError(INVALID_YOUTUBE_LINK_MESSAGE)

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
        if not video_id:
            raise ValueError(INVALID_YOUTUBE_LINK_MESSAGE)
        return raw

    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id:
        return raw

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v", "watch"}:
        return raw

    raise ValueError(INVALID_YOUTUBE_LINK_MESSAGE)
