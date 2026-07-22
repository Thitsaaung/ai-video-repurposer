"""Video-related API routes — queue jobs; engine runs in the background."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.services import job_store
from app.services.video_processor import process_video_job

router = APIRouter(prefix="/api", tags=["videos"])


class ProcessVideoRequest(BaseModel):
    """Body for submitting a YouTube URL to process."""

    url: HttpUrl = Field(..., description="YouTube video URL to repurpose")


class JobResponse(BaseModel):
    """In-memory job record returned by the API."""

    job_id: str
    status: str
    url: str
    created_at: str
    video_path: str | None = None
    curated_json_path: str | None = None
    output_clip_paths: list[str] | None = None
    error: str | None = None


@router.post("/process-video", response_model=JobResponse)
async def process_video(
    payload: ProcessVideoRequest,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """
    Create a queued job, schedule real engine processing, return immediately.
    """
    job = job_store.create_job(str(payload.url))
    background_tasks.add_task(process_video_job, job["job_id"], job["url"])
    return JobResponse(**job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Fetch a previously created job by id."""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobResponse(**job)
