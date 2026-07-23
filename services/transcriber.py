"""Transcribe video/audio files using OpenAI's Whisper API (verbose JSON)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
TRANSCRIPTS_DIR = PROJECT_ROOT / "transcripts"

# Whisper API hard limit is 25MB; stay under with a safety margin
MAX_WHISPER_UPLOAD_BYTES = 24 * 1024 * 1024

# Load OPENAI_API_KEY (and any other secrets) from the project .env
load_dotenv(PROJECT_ROOT / ".env")

SUPPORTED_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".oga",
    ".ogg",
    ".wav",
    ".webm",
}


def extract_compressed_audio(
    video_path: str,
    output_audio_path: str = "temp_audio.mp3",
) -> str:
    """
    Extract a small, speech-optimized MP3 from a video for Whisper uploads.

    Settings: no video (``-vn``), ``libmp3lame``, mono (``-ac 1``),
    16 kHz (``-ar 16000``), 64 kbps (``-ab 64k``).
    """
    input_path = Path(video_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Video file not found: {input_path}")

    output_path = Path(output_audio_path)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-ab",
        "64k",
        str(output_path),
    ]

    logger.info(
        "Extracting compressed audio from %s → %s",
        input_path.name,
        output_path.name,
    )

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        logger.error("FFmpeg executable not found on PATH: %s", exc)
        raise RuntimeError(
            "FFmpeg is not installed or not on PATH. Install FFmpeg and retry."
        ) from exc

    if completed.returncode != 0:
        stderr_tail = (completed.stderr or "")[-4000:]
        logger.error(
            "FFmpeg audio extraction failed (exit %s)\n%s",
            completed.returncode,
            stderr_tail,
        )
        raise RuntimeError(
            f"FFmpeg failed extracting audio from {input_path.name} "
            f"(exit {completed.returncode})."
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Compressed audio missing or empty: {output_path}")

    size_bytes = output_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    logger.info("Compressed audio size: %.2f MB (%s bytes)", size_mb, size_bytes)

    if size_bytes > MAX_WHISPER_UPLOAD_BYTES:
        message = (
            f"Compressed audio is still {size_mb:.2f} MB "
            f"(limit {MAX_WHISPER_UPLOAD_BYTES / (1024 * 1024):.0f} MB for Whisper). "
            "Split the video into shorter chunks or lower the bitrate further."
        )
        logger.error(message)
        raise ValueError(message)

    return str(output_path)


def transcribe_video(
    video_path: str | Path,
    *,
    output_dir: Path | str | None = None,
    save_json: bool = True,
) -> dict[str, Any]:
    """
    Transcribe a local video/audio file with Whisper and return structured data.

    Compresses audio to a mono 16 kHz / 64 kbps MP3 first to stay under the
    Whisper 25 MB upload limit. Uses ``response_format="verbose_json"`` for
    segment-level timestamps.
    """
    path = Path(video_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to your .env file at the project root."
        )

    dest = Path(output_dir) if output_dir is not None else TRANSCRIPTS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    client = OpenAI(api_key=api_key)
    temp_audio = PROJECT_ROOT / "temp_audio.mp3"
    audio_path: Path | None = None

    try:
        audio_file = extract_compressed_audio(
            str(path),
            output_audio_path=str(temp_audio),
        )
        audio_path = Path(audio_file)

        with audio_path.open("rb") as media_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=media_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        # Normalize to a plain dict (SDK returns a pydantic model)
        result: dict[str, Any] = transcription.model_dump()

        # Keep a clean, predictable shape for downstream clip selection
        segments = [
            {
                "id": seg.get("id"),
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": (seg.get("text") or "").strip(),
            }
            for seg in (result.get("segments") or [])
        ]

        structured: dict[str, Any] = {
            "source_file": str(path),
            "language": result.get("language"),
            "duration": result.get("duration"),
            "text": result.get("text", ""),
            "segments": segments,
        }

        if save_json:
            out_path = dest / f"{path.stem}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(structured, f, ensure_ascii=False, indent=2)
            structured["transcript_path"] = str(out_path.resolve())
            logger.info("Saved transcript to %s", structured["transcript_path"])

        logger.info(
            "Transcribed %s (%s segments, %.1fs)",
            path.name,
            len(segments),
            float(result.get("duration") or 0),
        )
        return structured

    except OpenAIError as exc:
        logger.error("OpenAI Whisper API error for %s: %s", path, exc)
        raise
    except OSError as exc:
        logger.error("File I/O error while transcribing %s: %s", path, exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error transcribing %s: %s", path, exc)
        raise
    finally:
        # Always remove temp_audio.mp3 after transcription (success or failure)
        for candidate in {audio_path, temp_audio}:
            if candidate is None:
                continue
            try:
                resolved = Path(candidate).resolve()
                if resolved.is_file():
                    resolved.unlink()
                    logger.info("Deleted temp audio: %s", resolved.name)
            except OSError as cleanup_exc:
                logger.warning(
                    "Could not delete temp audio %s: %s",
                    candidate,
                    cleanup_exc,
                )


def _pick_sample_video(downloads_dir: Path = DOWNLOADS_DIR) -> Path:
    """Return the first supported media file in downloads/, or raise if none."""
    if not downloads_dir.is_dir():
        raise FileNotFoundError(
            f"Downloads directory not found: {downloads_dir}. "
            "Run services/video_downloader.py first."
        )

    candidates = sorted(
        p
        for p in downloads_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not candidates:
        raise FileNotFoundError(
            f"No video files found in {downloads_dir}. "
            "Run services/video_downloader.py first."
        )
    return candidates[0]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    sample = _pick_sample_video()
    print(f"Transcribing: {sample}")
    data = transcribe_video(sample)

    print(f"Language: {data.get('language')}")
    print(f"Duration: {data.get('duration')}s")
    print(f"Full text: {data.get('text')}")
    print(f"Segments ({len(data['segments'])}):")
    for seg in data["segments"]:
        print(f"  [{seg['start']:.2f}s -> {seg['end']:.2f}s] {seg['text']}")
    if data.get("transcript_path"):
        print(f"Saved JSON: {data['transcript_path']}")
