"""Video-related API routes — queue jobs; engine runs in the background."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.core.auth import AuthenticatedUser
from app.core.enums import JobStatus
from app.core.paths import to_public_job
from app.core.validation import assert_youtube_url, validate_job_id
from app.deps.auth import require_authenticated_user
from app.services import job_store
from app.services.video_processor import process_video_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["videos"])


class ProcessVideoRequest(BaseModel):
    """Body for submitting a YouTube URL to process."""

    url: HttpUrl = Field(..., description="YouTube video URL to repurpose")

    @field_validator("url")
    @classmethod
    def _must_be_youtube(cls, value: HttpUrl) -> HttpUrl:
        assert_youtube_url(str(value))
        return value


class JobResponse(BaseModel):
    """Public job record (no absolute filesystem paths)."""

    job_id: str
    status: JobStatus
    url: str
    created_at: str
    updated_at: str | None = None
    video_path: str | None = None
    curated_json_path: str | None = None
    output_clip_paths: list[str] | None = None
    error: str | None = None
    stage: str | None = None


@router.post("/process-video", response_model=JobResponse)
async def process_video(
    payload: ProcessVideoRequest,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_authenticated_user),
) -> JobResponse:
    """
    Create a queued job, schedule real engine processing, return immediately.
    """
    url = str(payload.url)
    job = job_store.create_job(url)
    background_tasks.add_task(process_video_job, job["job_id"], job["url"])
    logger.info(
        "Enqueued job_id=%s user_id=%s for processing",
        job["job_id"],
        user.user_id,
    )
    return JobResponse(**to_public_job(job))


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
) -> JobResponse:
    """Fetch a previously created job by id."""
    validated_id = validate_job_id(job_id)
    job = job_store.get_job(validated_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    logger.debug("Job fetch job_id=%s user_id=%s", validated_id, user.user_id)
    return JobResponse(**to_public_job(job))
