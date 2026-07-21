"""Download videos from a URL using yt-dlp (best quality up to 1080p)."""

from __future__ import annotations

import logging
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)

# Project root / downloads — independent of the caller's working directory
DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"

# Best video + best audio, capped at 1080p; fall back to best combined ≤1080p
FORMAT_SELECTOR = "bv*[height<=1080]+ba/b[height<=1080]"


def download_video(url: str, output_dir: Path | str | None = None) -> str:
    """
    Download a video from ``url`` and return the local file path.

    Uses yt-dlp to fetch the best video and audio streams (up to 1080p),
    merges them into a single file under ``downloads/``, and returns that path.
    """
    if not url or not url.strip():
        raise ValueError("A non-empty video URL is required.")

    dest = Path(output_dir) if output_dir is not None else DOWNLOADS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    ydl_opts: dict = {
        "format": FORMAT_SELECTOR,
        "outtmpl": str(dest / "%(title)s [%(id)s].%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise RuntimeError(f"yt-dlp returned no info for URL: {url}")

            # Prefer the post-merge filepath when available
            requested = info.get("requested_downloads") or []
            if requested and requested[0].get("filepath"):
                filepath = requested[0]["filepath"]
            else:
                filepath = ydl.prepare_filename(info)
                # After merge, extension may be mp4 even if prepare_filename differs
                if info.get("ext"):
                    filepath = str(Path(filepath).with_suffix(f".{info['ext']}"))

            resolved = str(Path(filepath).resolve())
            logger.info("Downloaded video to %s", resolved)
            return resolved

    except yt_dlp.utils.DownloadError as exc:
        logger.error("Failed to download video from %s: %s", url, exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error downloading video from %s: %s", url, exc)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Short Creative Commons sample — replace with any YouTube URL to test
    sample_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

    print(f"Downloading: {sample_url}")
    path = download_video(sample_url)
    print(f"Saved to: {path}")
