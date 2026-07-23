"""Media download routes — serve clips from output_clips only."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])


def _resolve_clip_in_output_dir(filename: str) -> Path:
    """
    Map a client filename to a file strictly inside ``output_clips``.

    Rejects path traversal (``..``, absolute paths, nested segments).
    """
    output_dir = get_settings().output_clips_dir.resolve()
    raw = (filename or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Filename is required")

    if "/" in raw or "\\" in raw:
        raise HTTPException(status_code=400, detail="Invalid filename")

    safe_name = Path(raw).name
    if safe_name != raw or safe_name in {".", ".."} or not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    candidate = (output_dir / safe_name).resolve()
    try:
        candidate.relative_to(output_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename") from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Clip not found")

    return candidate


@router.get("/download/{filename}")
async def download_clip(filename: str) -> FileResponse:
    """
    Return a clip as an attachment so the browser downloads it.

    Only files that exist under the project ``output_clips/`` directory.
    """
    clip_path = _resolve_clip_in_output_dir(filename)
    logger.info("Download clip filename=%s", clip_path.name)
    return FileResponse(
        path=clip_path,
        media_type="video/mp4",
        filename=clip_path.name,
        content_disposition_type="attachment",
    )
