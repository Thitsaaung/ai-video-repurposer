"""End-to-end ingestion: download a video URL, transcribe it, sanitize timestamps."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from services.transcriber import TRANSCRIPTS_DIR, transcribe_video
from services.video_downloader import download_video

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


def _emit_progress(on_progress: ProgressCallback | None, stage: str) -> None:
    if on_progress is not None:
        on_progress(stage)

# Filename pattern from video_downloader: "Title [id].ext"
_FILENAME_ID_RE = re.compile(r"\[([^\]]+)\]$")


def _extract_video_id(video_url: str, video_path: str | Path) -> str:
    """Resolve a stable video id from the URL, then fall back to the filename."""
    parsed = urlparse(video_url.strip())
    host = (parsed.hostname or "").lower()

    if "youtu.be" in host:
        slug = parsed.path.strip("/").split("/")[0]
        if slug:
            return slug

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
            return parts[1]

    stem = Path(video_path).stem
    match = _FILENAME_ID_RE.search(stem)
    if match:
        return match.group(1)

    # Last resort: safe stem so the sanitized file can still be written
    safe = re.sub(r"[^\w\-]+", "_", stem).strip("_") or "unknown"
    return safe


def sanitize_segments(raw_segments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep only id, start, end, and text from Whisper segment payloads."""
    cleaned: list[dict[str, Any]] = []
    for seg in raw_segments or []:
        cleaned.append(
            {
                "id": seg.get("id"),
                "start": float(seg["start"]) if seg.get("start") is not None else None,
                "end": float(seg["end"]) if seg.get("end") is not None else None,
                "text": (seg.get("text") or "").strip(),
            }
        )
    return cleaned


def run_ingestion_pipeline(
    video_url: str,
    on_progress: ProgressCallback | None = None,
) -> dict[str, str]:
    """
    Download ``video_url``, transcribe with Whisper, and save a sanitized transcript.

    Optional ``on_progress(stage)`` is called with pipeline stage names
    (``downloading``, ``transcribing``). Callers may ignore it (CLI).

    Returns:
        ``{"video_path": ..., "sanitized_transcript_path": ...}``
    """
    if not video_url or not video_url.strip():
        raise ValueError("A non-empty video URL is required.")

    try:
        logger.info("Step 1/3 — downloading video")
        _emit_progress(on_progress, "downloading")
        video_path = download_video(video_url)
        video_id = _extract_video_id(video_url, video_path)
        logger.info("Downloaded %s (id=%s)", video_path, video_id)

        logger.info("Step 2/3 — transcribing with Whisper")
        _emit_progress(on_progress, "transcribing")
        # Skip the intermediate transcript file; pipeline writes the sanitized one
        transcript = transcribe_video(video_path, save_json=False)

        logger.info("Step 3/3 — sanitizing segments and saving JSON")
        sanitized: dict[str, Any] = {
            "video_id": video_id,
            "video_url": video_url.strip(),
            "video_path": video_path,
            "language": transcript.get("language"),
            "duration": transcript.get("duration"),
            "text": transcript.get("text", ""),
            "segments": sanitize_segments(transcript.get("segments")),
        }

        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        sanitized_path = TRANSCRIPTS_DIR / f"sanitized_{video_id}.json"
        with sanitized_path.open("w", encoding="utf-8") as f:
            json.dump(sanitized, f, ensure_ascii=False, indent=2)

        result = {
            "video_path": video_path,
            "sanitized_transcript_path": str(sanitized_path.resolve()),
        }
        logger.info(
            "Ingestion complete — %s segments → %s",
            len(sanitized["segments"]),
            result["sanitized_transcript_path"],
        )
        return result

    except Exception as exc:
        logger.error("Ingestion pipeline failed for %s: %s", video_url, exc)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Pass a URL as a CLI arg, or paste one when prompted
    if len(sys.argv) > 1:
        url = sys.argv[1].strip()
    else:
        url = input("Enter a YouTube URL: ").strip()

    if not url:
        print("No URL provided. Exiting.")
        sys.exit(1)

    print(f"Running ingestion pipeline for: {url}")
    output = run_ingestion_pipeline(url)
    print(f"video_path: {output['video_path']}")
    print(f"sanitized_transcript_path: {output['sanitized_transcript_path']}")
