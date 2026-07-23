"""Shared enums for the FastAPI backend."""

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle states for a video-processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
