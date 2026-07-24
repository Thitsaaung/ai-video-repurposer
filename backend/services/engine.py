"""Single entry point: YouTube URL → download → curate → cut short clips."""

from __future__ import annotations

import logging
import sys
from typing import Any

from services.curator import curate_clips
from services.pipeline import run_ingestion_pipeline
from services.video_cutter import process_all_curated_clips

logger = logging.getLogger(__name__)


def process_video_to_clips(video_url: str) -> dict[str, Any]:
    """
    End-to-end engine: ingest a video URL, curate clips, cut them, return results.

    Success:
        ``{
            "status": "success",
            "video_path": ...,
            "curated_json_path": ...,
            "clips": [...],
            "output_clip_paths": [...],
        }``

    Failure:
        ``{"status": "error", "message": "..."}``
    """
    try:
        if not video_url or not str(video_url).strip():
            raise ValueError("A non-empty video URL is required.")

        url = str(video_url).strip()

        # Ingestion covers download + Whisper transcription + sanitized JSON
        logger.info("[1/4] Downloading...")
        logger.info("[2/4] Transcribing...")
        ingestion = run_ingestion_pipeline(url)
        video_path = ingestion["video_path"]
        sanitized_path = ingestion["sanitized_transcript_path"]
        logger.info("[1/4] Download complete → %s", video_path)
        logger.info("[2/4] Transcript ready → %s", sanitized_path)

        logger.info("[3/4] Curating with AI...")
        curation = curate_clips(sanitized_path)
        curated_json_path = curation.get("curated_path")
        clips = curation.get("clips") or []
        if not curated_json_path:
            raise RuntimeError("curate_clips() did not return curated_path")
        logger.info(
            "[3/4] Curation complete → %s clip(s) at %s",
            len(clips),
            curated_json_path,
        )

        # Strict hand-off: use THIS run's video + curated JSON only (no auto-detect)
        logger.info("[4/4] Cutting clips from this run's video + curated JSON...")
        logger.info("[4/4] video_path=%s", video_path)
        logger.info("[4/4] curated_json_path=%s", curated_json_path)
        output_clip_paths = process_all_curated_clips(
            video_path=video_path,
            curated_json_path=curated_json_path,
        )
        logger.info("[4/4] Cut %s clip file(s)", len(output_clip_paths))

        return {
            "status": "success",
            "video_path": video_path,
            "curated_json_path": curated_json_path,
            "clips": clips,
            "output_clip_paths": output_clip_paths,
        }

    except Exception as exc:
        logger.error("process_video_to_clips failed: %s", exc)
        return {
            "status": "error",
            "message": str(exc),
        }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if len(sys.argv) > 1:
        url = sys.argv[1].strip()
    else:
        url = input("Enter a YouTube URL: ").strip()

    if not url:
        print("No URL provided. Exiting.")
        sys.exit(1)

    print(f"Processing: {url}")
    result = process_video_to_clips(url)

    if result.get("status") != "success":
        print(f"ERROR: {result.get('message')}")
        sys.exit(1)

    print(f"status: {result['status']}")
    print(f"video_path: {result['video_path']}")
    print(f"curated_json_path: {result['curated_json_path']}")
    print(f"clips ({len(result['clips'])}):")
    for clip in result["clips"]:
        print(
            f"  [{clip.get('clip_id')}] {clip.get('title')} "
            f"({clip.get('start_time'):.2f}s → {clip.get('end_time'):.2f}s, "
            f"score={clip.get('virality_score')})"
        )
    print(f"output_clip_paths ({len(result.get('output_clip_paths') or [])}):")
    for path in result.get("output_clip_paths") or []:
        print(f"  {path}")
