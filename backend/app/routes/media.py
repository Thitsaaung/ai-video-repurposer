"""Media download routes — serve clips from output_clips only."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/media", tags=["media"])

# backend/app/routes/media.py → repo root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_OUTPUT_CLIPS_DIR = (_PROJECT_ROOT / "output_clips").resolve()
_OUTPUT_CLIPS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_clip_in_output_dir(filename: str) -> Path:
    """
    Map a client filename to a file strictly inside ``output_clips``.

    Rejects path traversal (``..``, absolute paths, nested segments).
    """
    raw = (filename or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Disallow any directory separators in the request value.
    if "/" in raw or "\\" in raw:
        raise HTTPException(status_code=400, detail="Invalid filename")

    safe_name = Path(raw).name
    if safe_name != raw or safe_name in {".", ".."} or not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    candidate = (_OUTPUT_CLIPS_DIR / safe_name).resolve()
    try:
        candidate.relative_to(_OUTPUT_CLIPS_DIR)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        ) from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Clip not found: {safe_name}")

    return candidate


@router.get("/download/{filename}")
async def download_clip(filename: str) -> FileResponse:
    """
    Return a clip as an attachment so the browser downloads it.

    Only files that exist under the project ``output_clips/`` directory.
    """
    clip_path = _resolve_clip_in_output_dir(filename)
    return FileResponse(
        path=clip_path,
        media_type="video/mp4",
        filename=clip_path.name,
        content_disposition_type="attachment",
    )
