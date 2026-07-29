"""Cut short clips from a source video using curated timestamp JSON + FFmpeg."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings
from services.subtitle_layout import layout_segment

logger = logging.getLogger(__name__)

# backend/ is the application root (Railway deploy root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CLIPS_DIR = PROJECT_ROOT / "output_clips"
TRANSCRIPTS_DIR = PROJECT_ROOT / "transcripts"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"

# libass force_style for Shorts/TikTok readability (SRT content unchanged).
# Colours are ASS &HAABBGGRR. Alignment=2 is bottom-center. No FontName —
# rely on the runtime default so Windows/Railway both render without a
# missing-font failure.
#
# Safe-area notes (Sprint 5.5):
# - MarginV is distance from the bottom for Alignment=2. Lower than 90 moves
#   captions down; keep enough gap above typical player / Shorts UI controls.
# - Slightly smaller FontSize + modest side margins prefer ~2-line wraps over
#   tall 3–4 line stacks (without changing SRT cue text or timing).
_SUBTITLE_FORCE_STYLE = (
    "FontSize=22,"
    "Bold=1,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BorderStyle=1,"
    "Outline=4,"
    "Shadow=1,"
    "Alignment=2,"
    "MarginL=18,"
    "MarginR=18,"
    "MarginV=58"
)


def _probe_video_duration_seconds(video_path: Path) -> float | None:
    """Return media duration via ffprobe, or None if unavailable."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not on PATH; clip padding will clamp start to 0 only")
        return None
    if completed.returncode != 0:
        logger.warning(
            "ffprobe failed for %s; clip padding will clamp start to 0 only",
            video_path.name,
        )
        return None
    try:
        duration = float((completed.stdout or "").strip())
    except ValueError:
        return None
    if duration <= 0:
        return None
    return duration


def _apply_editorial_padding(
    start_time: float,
    end_time: float,
    *,
    pad_start: float,
    pad_end: float,
    video_duration: float | None,
) -> tuple[float, float]:
    """
    Expand a curated window for Shorts packaging only.

    Padding belongs in the cutter (not Whisper/curator/validator): curated JSON
    stays the semantic speech window; render-time pad is editorial pre/post-roll.
    """
    start = float(start_time)
    end = float(end_time)
    cut_start = max(0.0, start - max(0.0, pad_start))
    cut_end = end + max(0.0, pad_end)

    if video_duration is not None and video_duration > 0:
        cut_start = min(max(0.0, cut_start), video_duration)
        cut_end = min(max(0.0, cut_end), video_duration)

    if cut_end <= cut_start:
        # Degenerate after clamp — keep original curated window (still clamped).
        cut_start = max(0.0, start)
        cut_end = end
        if video_duration is not None and video_duration > 0:
            cut_start = min(cut_start, video_duration)
            cut_end = min(max(cut_end, cut_start), video_duration)

    return round(cut_start, 3), round(cut_end, 3)


def _sanitize_title(title: str, max_len: int = 60) -> str:
    """Make a filesystem-safe slug from a clip title."""
    slug = re.sub(r"[^\w\-]+", "_", (title or "clip").strip(), flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return (slug or "clip")[:max_len]


def _clip_field(clip: object, key: str) -> object:
    """Read a field from a dict or object-style clip."""
    if isinstance(clip, dict):
        return clip.get(key)
    return getattr(clip, key, None)


def _seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp ``HH:MM:SS,mmm``."""
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_for_clip(
    clip: object,
    sanitized_json_path: str,
    output_srt_path: str,
) -> str:
    """
    Build an SRT for ``clip`` using segments from ``sanitized_json_path``.

    Timestamps are relative to the clip start (clip at 120s → speech at 122s
    becomes ``00:00:02,000``).
    """
    clip_start = _clip_field(clip, "start_time")
    clip_end = _clip_field(clip, "end_time")
    if clip_start is None or clip_end is None:
        raise ValueError("clip must include start_time and end_time")

    clip_start_f = float(clip_start)
    clip_end_f = float(clip_end)
    if clip_end_f <= clip_start_f:
        raise ValueError(f"Invalid clip range: {clip_start_f} → {clip_end_f}")

    transcript_path = Path(sanitized_json_path).resolve()
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Sanitized transcript not found: {transcript_path}")

    with transcript_path.open("r", encoding="utf-8") as f:
        transcript = json.load(f)

    segments = transcript.get("segments") or []
    # (rel_start, rel_end, cue_body_with_newlines)
    entries: list[tuple[float, float, str]] = []

    for seg in segments:
        text = " ".join(str(seg.get("text") or "").split())
        if not text:
            continue
        if seg.get("start") is None or seg.get("end") is None:
            continue

        seg_start = float(seg["start"])
        seg_end = float(seg["end"])

        # Keep only segments overlapping the clip window
        if seg_end <= clip_start_f or seg_start >= clip_end_f:
            continue

        # Layout uses the clipped absolute window so times stay inside the clip.
        abs_start = max(seg_start, clip_start_f)
        abs_end = min(seg_end, clip_end_f)
        if abs_end <= abs_start:
            continue

        for cue in layout_segment(abs_start, abs_end, text):
            rel_start = cue.start - clip_start_f
            rel_end = cue.end - clip_start_f
            if rel_end <= rel_start:
                continue
            entries.append((rel_start, rel_end, cue.text))

    srt_path = Path(output_srt_path)
    if not srt_path.is_absolute():
        srt_path = PROJECT_ROOT / srt_path
    srt_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for index, (rel_start, rel_end, text) in enumerate(entries, start=1):
        lines.append(str(index))
        lines.append(
            f"{_seconds_to_srt_timestamp(rel_start)} --> {_seconds_to_srt_timestamp(rel_end)}"
        )
        lines.append(text)
        lines.append("")

    srt_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(
        "Wrote SRT with %s cue(s) → %s (relative to clip start %.3fs)",
        len(entries),
        srt_path.name,
        clip_start_f,
    )
    return str(srt_path.resolve())


def cut_clip(
    input_video_path: str,
    start_time: float,
    end_time: float,
    output_clip_path: str,
    *,
    relative_srt_path: str | None = None,
) -> str:
    """
    Trim ``input_video_path`` from ``start_time`` to ``end_time`` with FFmpeg.

    Uses fast seeking (``-ss`` before ``-i``), center-crops to 9:16 portrait,
    optionally burns in subtitles from a *relative* ``.srt`` path, and re-encodes
    with libx264/aac.
    """
    input_path = Path(input_video_path).resolve()
    output_path = Path(output_clip_path).resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    start = float(start_time)
    end = float(end_time)
    if start < 0 or end <= start:
        raise ValueError(f"Invalid time range: start={start}, end={end}")

    duration = end - start
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Relative SRT only — avoids Windows absolute-path escaping in subtitles=
    if relative_srt_path:
        # Normalize to forward slashes; keep it relative (no drive letter)
        srt_for_filter = Path(relative_srt_path).as_posix()
        if Path(srt_for_filter).is_absolute():
            raise ValueError(
                "relative_srt_path must be relative (e.g. 'temp.srt'), "
                f"got absolute: {relative_srt_path}"
            )
        video_filter = (
            f"crop=ih*9/16:ih,"
            f"subtitles={srt_for_filter}:force_style='{_SUBTITLE_FORCE_STYLE}'"
        )
    else:
        video_filter = "crop=ih*9/16:ih"

    # Fast seek before input; 9:16 crop (+ optional burn-in); re-encode
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    logger.info(
        "Cutting clip %.3fs → %.3fs (%.3fs) vf=%s → %s",
        start,
        end,
        duration,
        video_filter,
        output_path.name,
    )

    try:
        # cwd=PROJECT_ROOT so relative temp.srt resolves for the subtitles filter
        # encoding=utf-8: avoid Windows cp1252 decode crashes on Unicode paths in FFmpeg logs
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(PROJECT_ROOT),
        )
    except FileNotFoundError as exc:
        logger.error("FFmpeg executable not found on PATH: %s", exc)
        raise RuntimeError(
            "FFmpeg is not installed or not on PATH. Install FFmpeg and retry."
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error launching FFmpeg: %s", exc)
        raise

    if completed.returncode != 0:
        stderr_tail = (completed.stderr or "")[-4000:]
        stdout_tail = (completed.stdout or "")[-1000:]
        logger.error(
            "FFmpeg failed (exit %s) for %s\n--- stderr ---\n%s\n--- stdout ---\n%s",
            completed.returncode,
            output_path,
            stderr_tail,
            stdout_tail,
        )
        raise RuntimeError(
            f"FFmpeg failed while writing {output_path.name} "
            f"(exit {completed.returncode}). See logs for stderr."
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg reported success but output is missing/empty: {output_path}")

    logger.info("Wrote clip: %s", output_path)
    return str(output_path)


def _resolve_sanitized_path(payload: dict, curated_path: Path) -> Path:
    """Locate the sanitized transcript for subtitle generation."""
    source = payload.get("source_transcript")
    if source:
        candidate = Path(source)
        if candidate.is_file():
            return candidate.resolve()

    video_id = payload.get("video_id")
    if video_id:
        candidate = TRANSCRIPTS_DIR / f"sanitized_{video_id}.json"
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError(
        f"Could not resolve sanitized transcript for {curated_path.name}"
    )


def process_all_curated_clips(video_path: str, curated_json_path: str) -> list[str]:
    """
    Cut every clip listed in ``curated_json_path`` from ``video_path``.

    STRICT: uses only the ``video_path`` and ``curated_json_path`` arguments.
    Does not auto-detect or fall back to other files in downloads/ or transcripts/.

    Saves files as ``output_clips/clip_<clip_id>_<sanitized_title>.mp4`` and
    returns the list of generated local paths. Burns relative-timestamp
    subtitles using the sanitized transcript referenced by the curated JSON.
    """
    video = Path(video_path).resolve()
    curated_path = Path(curated_json_path).resolve()

    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    if not curated_path.is_file():
        raise FileNotFoundError(f"Curated JSON not found: {curated_path}")

    logger.info(
        "process_all_curated_clips using EXACT args — video=%s curated=%s",
        video,
        curated_path,
    )

    try:
        with curated_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid curated JSON %s: %s", curated_path, exc)
        raise

    clips = payload.get("clips") or []
    if not clips:
        raise ValueError(f"No clips found in {curated_path}")

    # Sanitized transcript comes only from THIS curated JSON (not "latest" scan)
    sanitized_path = _resolve_sanitized_path(payload, curated_path)

    # Editorial pad is cutter-only; curated JSON on disk is never rewritten.
    settings = get_settings()
    pad_start = float(settings.clip_pad_start_seconds)
    pad_end = float(settings.clip_pad_end_seconds)
    video_duration = _probe_video_duration_seconds(video)
    logger.info(
        "Editorial padding pad_start=%.3fs pad_end=%.3fs video_duration=%s",
        pad_start,
        pad_end,
        f"{video_duration:.3f}s" if video_duration is not None else "unknown",
    )

    OUTPUT_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    failures: list[str] = []

    for clip in clips:
        clip_id = clip.get("clip_id")
        title = clip.get("title") or f"clip_{clip_id}"
        start_time = clip.get("start_time")
        end_time = clip.get("end_time")

        if clip_id is None or start_time is None or end_time is None:
            logger.warning("Skipping incomplete clip object: %s", clip)
            failures.append(f"incomplete:{clip}")
            continue

        out_name = f"clip_{clip_id}_{_sanitize_title(str(title))}.mp4"
        out_path = OUTPUT_CLIPS_DIR / out_name

        # Relative name only — FFmpeg runs with cwd=PROJECT_ROOT
        relative_srt = "temp.srt"
        temp_srt_path = PROJECT_ROOT / relative_srt

        try:
            cut_start, cut_end = _apply_editorial_padding(
                float(start_time),
                float(end_time),
                pad_start=pad_start,
                pad_end=pad_end,
                video_duration=video_duration,
            )
            # Same padded window for SRT + FFmpeg (curated clip object untouched).
            render_clip = {
                **clip,
                "start_time": cut_start,
                "end_time": cut_end,
                "duration": round(cut_end - cut_start, 3),
            }
            if cut_start != float(start_time) or cut_end != float(end_time):
                logger.info(
                    "clip_id=%s padded window %.3f→%.3f (curated %.3f→%.3f)",
                    clip_id,
                    cut_start,
                    cut_end,
                    float(start_time),
                    float(end_time),
                )

            generate_srt_for_clip(
                clip=render_clip,
                sanitized_json_path=str(sanitized_path),
                output_srt_path=str(temp_srt_path),
            )
            path = cut_clip(
                input_video_path=str(video),
                start_time=cut_start,
                end_time=cut_end,
                output_clip_path=str(out_path),
                relative_srt_path=relative_srt,
            )
            generated.append(path)
        except Exception as exc:
            logger.error(
                "Failed to cut clip_id=%s (%s): %s",
                clip_id,
                title,
                exc,
            )
            failures.append(f"clip_{clip_id}:{exc}")
        finally:
            try:
                if temp_srt_path.is_file():
                    temp_srt_path.unlink()
                    logger.info("Deleted temporary SRT: %s", relative_srt)
            except OSError as cleanup_exc:
                logger.warning(
                    "Could not delete temporary SRT %s: %s",
                    temp_srt_path,
                    cleanup_exc,
                )

    if not generated:
        raise RuntimeError(
            f"No clips were generated from {curated_path.name}. "
            f"Failures: {failures}"
        )

    if failures:
        logger.warning(
            "Generated %s clip(s); %s failed: %s",
            len(generated),
            len(failures),
            failures,
        )
    else:
        logger.info("Generated %s clip(s) → %s", len(generated), OUTPUT_CLIPS_DIR)

    return generated


def _find_download_by_video_id(video_id: str) -> Path | None:
    """Find a file in downloads/ whose name contains the YouTube video id."""
    if not video_id or not DOWNLOADS_DIR.is_dir():
        return None

    # Prefer the yt-dlp naming pattern: "Title [id].ext"
    bracketed = [
        p
        for p in DOWNLOADS_DIR.iterdir()
        if p.is_file() and f"[{video_id}]" in p.name
    ]
    if bracketed:
        return sorted(bracketed)[0].resolve()

    # Fallback: id appears anywhere in the filename
    loose = [
        p
        for p in DOWNLOADS_DIR.iterdir()
        if p.is_file() and video_id in p.name
    ]
    if loose:
        return sorted(loose)[0].resolve()

    return None


def _video_path_from_sanitized(transcript_path: Path) -> Path | None:
    """Return video_path from a sanitized transcript if the file still exists."""
    if not transcript_path.is_file():
        return None
    try:
        with transcript_path.open("r", encoding="utf-8") as f:
            sanitized = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    video_path = sanitized.get("video_path")
    if video_path and Path(video_path).is_file():
        return Path(video_path).resolve()

    # Stale absolute path — try locating by video_id in downloads/
    video_id = sanitized.get("video_id")
    if video_id:
        found = _find_download_by_video_id(str(video_id))
        if found:
            return found

    return None


def _resolve_video_for_curated(curated_path: Path) -> Path:
    """Resolve the source video path from curated JSON / sanitized transcript / downloads."""
    with curated_path.open("r", encoding="utf-8") as f:
        curated = json.load(f)

    video_id = curated.get("video_id")
    source_transcript = curated.get("source_transcript")
    tried: list[str] = []

    if source_transcript:
        transcript_path = Path(source_transcript)
        tried.append(str(transcript_path))
        resolved = _video_path_from_sanitized(transcript_path)
        if resolved:
            return resolved

    if video_id:
        fallback_transcript = TRANSCRIPTS_DIR / f"sanitized_{video_id}.json"
        tried.append(str(fallback_transcript))
        resolved = _video_path_from_sanitized(fallback_transcript)
        if resolved:
            return resolved

        found = _find_download_by_video_id(str(video_id))
        if found:
            return found
        tried.append(f"downloads/*[{video_id}]*")

    available = []
    if DOWNLOADS_DIR.is_dir():
        available = sorted(p.name for p in DOWNLOADS_DIR.iterdir() if p.is_file())

    available_msg = (
        "\n  - ".join([""] + available) if available else " (downloads/ is empty)"
    )
    raise FileNotFoundError(
        f"Could not resolve source video for curated file {curated_path.name} "
        f"(video_id={video_id!r}).\n"
        f"The original download was likely moved or deleted.\n"
        f"Checked:{chr(10).join('  - ' + t for t in tried) if tried else ' (nothing)'}\n"
        f"Available downloads:{available_msg}\n"
        f"Re-run the engine/pipeline for this URL, or pass paths explicitly:\n"
        f'  python services/video_cutter.py "<video.mp4>" "{curated_path}"'
    )


def _pick_latest_curated(transcripts_dir: Path = TRANSCRIPTS_DIR) -> Path:
    candidates = sorted(
        transcripts_dir.glob("curated_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No curated_*.json in {transcripts_dir}. Run: python -m services.engine <url>"
        )
    return candidates[0]


def _pick_latest_curated_with_video(
    transcripts_dir: Path = TRANSCRIPTS_DIR,
) -> tuple[Path, Path]:
    """
    Pick the newest curated JSON whose source video still exists on disk.

    Skips stale curated files whose downloads were deleted.
    """
    candidates = sorted(
        transcripts_dir.glob("curated_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No curated_*.json in {transcripts_dir}. Run: python -m services.engine <url>"
        )

    errors: list[str] = []
    for curated_path in candidates:
        try:
            video_path = _resolve_video_for_curated(curated_path)
            if curated_path != candidates[0]:
                logger.warning(
                    "Newest curated file %s has no local video; "
                    "falling back to %s",
                    candidates[0].name,
                    curated_path.name,
                )
            return curated_path, video_path
        except FileNotFoundError as exc:
            errors.append(f"{curated_path.name}: {exc}")
            continue

    raise FileNotFoundError(
        "No curated_*.json has a matching video in downloads/.\n"
        + "\n---\n".join(errors)
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Require explicit paths — never auto-pick old downloads/curated files
    if len(sys.argv) < 3:
        print(
            "Usage: python -m services.video_cutter <video_path> <curated_json_path>\n"
            "Both arguments are required so an old video is never selected by accident.\n"
            "Prefer: python -m services.engine <youtube_url>"
        )
        sys.exit(1)

    video_arg = sys.argv[1]
    curated_arg = sys.argv[2]
    print(f"Using curated: {curated_arg}")
    print(f"Using video:   {video_arg}")

    paths = process_all_curated_clips(video_arg, curated_arg)
    print(f"Generated {len(paths)} clip(s):")
    for path in paths:
        print(f"  {path}")
