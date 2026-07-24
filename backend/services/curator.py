"""LLM clip curator: pick the most engaging short segments from a sanitized transcript."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from services.clip_validator import validate_and_filter_clips

# backend/ is the application root (Railway deploy root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = PROJECT_ROOT / "transcripts"

# Prefer backend/.env; fall back to monorepo root .env for local development.
load_dotenv(PROJECT_ROOT.parent / ".env")
load_dotenv(PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)

MIN_CLIP_SECONDS = 15.0
MAX_CLIP_SECONDS = 60.0
BOUNDARY_TOLERANCE = 0.05  # seconds — Whisper floats can be slightly noisy


class Clip(BaseModel):
    clip_id: int
    title: str = Field(..., description="Catchy title for TikTok/Reels")
    hook: str = Field(..., description="Why this clip will perform well")
    start_time: float
    end_time: float
    virality_score: int = Field(..., ge=1, le=100)
    duration: float

    @field_validator("title", "hook")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned

    @model_validator(mode="after")
    def _sync_duration(self) -> Clip:
        computed = round(self.end_time - self.start_time, 3)
        if computed <= 0:
            raise ValueError("end_time must be greater than start_time")
        # Prefer the authoritative span from timestamps
        self.duration = computed
        return self


class CurationResponse(BaseModel):
    clips: list[Clip]
    overall_summary: str

    @field_validator("overall_summary")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("overall_summary must be a non-empty string")
        return cleaned

    @field_validator("clips")
    @classmethod
    def _non_empty_clips(cls, value: list[Clip]) -> list[Clip]:
        if not value:
            raise ValueError("clips must contain at least one clip")
        return value


SYSTEM_PROMPT = """You are an expert short-form video curator for TikTok, Instagram Reels, and YouTube Shorts.

You will receive a compact plain-text transcript. Each line is:
[start_time - end_time] spoken text

CRITICAL OUTPUT REQUIREMENT:
You MUST generate EXACTLY 10 distinct, high-quality clips. Do not return fewer than 10 clips under any circumstances.
Spread them across different parts of the video (beginning, middle, and end) so they do not pile up in one region.

Selection criteria — prioritize:
- Strong hooks in the first 1-3 seconds of the clip
- Emotional moments (surprise, tension, inspiration, vulnerability)
- High-value insights or actionable takeaways
- Humorous or highly quotable statements

Hard constraints:
1. Return EXACTLY 10 clips in the "clips" array — never 1, never 2, never 9. Always 10.
2. Each clip MUST be between 15 and 60 seconds long (duration = end_time - start_time).
3. start_time and end_time MUST be exact timestamp boundaries from the transcript lines (use only values that appear as a segment start or end). Do NOT invent intermediate timestamps.
4. Prefer contiguous spans that cover complete spoken phrases (start at a segment start, end at a later segment end).
5. Clips should be largely non-overlapping (minimize shared time) so all 10 can survive validation.
6. Assign a virality_score from 1-100 based on hook strength, emotional punch, and shareability.
7. Give each clip a catchy title and a short hook explaining why it will perform well on TikTok/Reels.
8. Return STRICT JSON only — no markdown fences, no commentary — conforming exactly to this schema:
{
  "clips": [
    {
      "clip_id": 1,
      "title": "...",
      "hook": "...",
      "start_time": 0.0,
      "end_time": 22.96,
      "virality_score": 85,
      "duration": 22.96
    }
  ],
  "overall_summary": "..."
}

Only if the entire source video is shorter than ~150 seconds (making 10 non-overlapping 15s+ clips physically impossible) may you return fewer than 10 — and you must state that limitation in overall_summary. For any video around 5+ minutes, EXACTLY 10 clips is mandatory.
"""


def _nearest_boundary(value: float, boundaries: list[float]) -> float:
    return min(boundaries, key=lambda b: abs(b - value))


def _snap_clip_to_boundaries(clip: Clip, boundaries: list[float]) -> Clip:
    """Force start/end onto exact transcript boundaries and recompute duration."""
    start = _nearest_boundary(clip.start_time, boundaries)
    end = _nearest_boundary(clip.end_time, boundaries)

    if end <= start:
        later = [b for b in boundaries if b > start]
        if not later:
            raise ValueError(f"Cannot form a valid clip starting at {start}")
        in_range = [
            b for b in later if MIN_CLIP_SECONDS <= (b - start) <= MAX_CLIP_SECONDS
        ]
        end = in_range[0] if in_range else later[-1]

    return clip.model_copy(
        update={
            "start_time": start,
            "end_time": end,
            "duration": round(end - start, 3),
        }
    )


def _merged_segment_count(
    start: float,
    end: float,
    segments: list[dict[str, Any]],
) -> int:
    """Count transcript segments fully contained in ``[start, end]``."""
    count = 0
    for seg in segments:
        if seg.get("start") is None or seg.get("end") is None:
            continue
        seg_start = float(seg["start"])
        seg_end = float(seg["end"])
        if (
            seg_start >= start - BOUNDARY_TOLERANCE
            and seg_end <= end + BOUNDARY_TOLERANCE
        ):
            count += 1
    return count


def _extend_clip_to_min_duration(
    clip: Clip,
    segments: list[dict[str, Any]],
) -> tuple[Clip, dict[str, Any]]:
    """
    Deterministically grow a too-short clip using whole transcript segments only.

    Preference order:
    1. Extend ``end_time`` forward to later segment ends (never mid-segment).
    2. If forward would exceed ``MAX_CLIP_SECONDS`` or hits EOF without reaching
       ``MIN_CLIP_SECONDS``, extend ``start_time`` backward to earlier segment starts.

    Preserves ``clip_id``, ``title``, ``hook``, and ``virality_score``.
    """
    segment_starts = sorted(
        {
            float(seg["start"])
            for seg in segments
            if seg.get("start") is not None
        }
    )
    segment_ends = sorted(
        {
            float(seg["end"])
            for seg in segments
            if seg.get("end") is not None
        }
    )
    if not segment_starts or not segment_ends:
        raise ValueError("No transcript segment boundaries available for extension")

    original_start = float(clip.start_time)
    original_end = float(clip.end_time)
    original_duration = round(original_end - original_start, 3)

    def _info(
        result_clip: Clip,
        *,
        extended: bool,
    ) -> dict[str, Any]:
        return {
            "extended": extended,
            "original_start": original_start,
            "original_end": original_end,
            "original_duration": original_duration,
            "extended_start": float(result_clip.start_time),
            "extended_end": float(result_clip.end_time),
            "extended_duration": float(result_clip.duration),
            "merged_segment_count": _merged_segment_count(
                float(result_clip.start_time),
                float(result_clip.end_time),
                segments,
            ),
        }

    if MIN_CLIP_SECONDS <= original_duration <= MAX_CLIP_SECONDS:
        return clip, _info(clip, extended=False)

    if original_duration > MAX_CLIP_SECONDS:
        raise ValueError(
            f"clip duration {original_duration}s outside "
            f"{MIN_CLIP_SECONDS}-{MAX_CLIP_SECONDS}s (too long to extend)"
        )

    new_start = original_start
    new_end = original_end

    # --- Phase 1: extend forward along segment ends ---
    for end_candidate in segment_ends:
        if end_candidate <= new_end + BOUNDARY_TOLERANCE:
            continue
        duration = end_candidate - new_start
        if duration > MAX_CLIP_SECONDS:
            # Next whole segment would exceed max — stop forward, try backward.
            break
        new_end = end_candidate
        if duration >= MIN_CLIP_SECONDS:
            extended_clip = clip.model_copy(
                update={
                    "start_time": new_start,
                    "end_time": new_end,
                    "duration": round(new_end - new_start, 3),
                }
            )
            return extended_clip, _info(extended_clip, extended=True)

    # --- Phase 2: extend backward along segment starts ---
    for start_candidate in reversed(segment_starts):
        if start_candidate >= new_start - BOUNDARY_TOLERANCE:
            continue
        duration = new_end - start_candidate
        if duration > MAX_CLIP_SECONDS:
            # Going further back only lengthens the clip.
            break
        new_start = start_candidate
        if duration >= MIN_CLIP_SECONDS:
            extended_clip = clip.model_copy(
                update={
                    "start_time": new_start,
                    "end_time": new_end,
                    "duration": round(new_end - new_start, 3),
                }
            )
            return extended_clip, _info(extended_clip, extended=True)

    final_duration = round(new_end - new_start, 3)
    raise ValueError(
        f"Cannot extend clip to {MIN_CLIP_SECONDS}-{MAX_CLIP_SECONDS}s "
        f"(reached {new_start:.3f}->{new_end:.3f}, {final_duration}s)"
    )


def _assert_clip_on_boundaries(clip: Clip, boundaries: list[float]) -> None:
    if not any(abs(clip.start_time - b) <= BOUNDARY_TOLERANCE for b in boundaries):
        raise ValueError(f"start_time {clip.start_time} is not a transcript boundary")
    if not any(abs(clip.end_time - b) <= BOUNDARY_TOLERANCE for b in boundaries):
        raise ValueError(f"end_time {clip.end_time} is not a transcript boundary")


def _validate_clip_against_transcript(
    clip: Clip,
    boundaries: list[float],
    video_duration: float | None,
    segments: list[dict[str, Any]] | None = None,
) -> tuple[Clip, dict[str, Any]]:
    """
    Snap to boundaries, optionally extend short clips, then enforce duration.

    Returns ``(validated_clip, extension_info)``.
    """
    snapped = _snap_clip_to_boundaries(clip, boundaries)
    _assert_clip_on_boundaries(snapped, boundaries)

    source_too_short = video_duration is not None and video_duration < MIN_CLIP_SECONDS
    extension_info: dict[str, Any] = {
        "extended": False,
        "original_start": float(snapped.start_time),
        "original_end": float(snapped.end_time),
        "original_duration": float(snapped.duration),
        "extended_start": float(snapped.start_time),
        "extended_end": float(snapped.end_time),
        "extended_duration": float(snapped.duration),
        "merged_segment_count": _merged_segment_count(
            float(snapped.start_time),
            float(snapped.end_time),
            segments or [],
        ),
    }

    if (
        not source_too_short
        and snapped.duration < MIN_CLIP_SECONDS
        and segments is not None
    ):
        snapped, extension_info = _extend_clip_to_min_duration(snapped, segments)
        _assert_clip_on_boundaries(snapped, boundaries)

    if not source_too_short and not (
        MIN_CLIP_SECONDS <= snapped.duration <= MAX_CLIP_SECONDS
    ):
        raise ValueError(
            f"clip duration {snapped.duration}s outside "
            f"{MIN_CLIP_SECONDS}-{MAX_CLIP_SECONDS}s"
        )

    return snapped, extension_info


def compress_transcript(sanitized_json_path: str) -> str:
    """
    Convert a sanitized transcript JSON into a compact plain-text token budget.

    Format per line: ``[start - end] text``
    Empty / whitespace-only segments are dropped.
    """
    path = Path(sanitized_json_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Sanitized transcript not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            transcript = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid sanitized JSON %s: %s", path, exc)
        raise

    segments = transcript.get("segments") or []
    lines: list[str] = []

    video_id = transcript.get("video_id")
    duration = transcript.get("duration")
    if video_id is not None or duration is not None:
        header_bits = []
        if video_id is not None:
            header_bits.append(f"video_id={video_id}")
        if duration is not None:
            header_bits.append(f"duration={float(duration):.3f}s")
        lines.append(" | ".join(header_bits))

    for seg in segments:
        text = " ".join(str(seg.get("text") or "").split())
        if not text:
            continue
        if seg.get("start") is None or seg.get("end") is None:
            continue
        start = float(seg["start"])
        end = float(seg["end"])
        lines.append(f"[{start:.3f} - {end:.3f}] {text}")

    if len(lines) <= (1 if video_id is not None or duration is not None else 0):
        raise ValueError(f"No usable transcript segments in {path}")

    compact = "\n".join(lines)
    logger.info(
        "Compressed transcript %s → %s chars / %s lines",
        path.name,
        len(compact),
        len(lines),
    )
    return compact


def _build_user_prompt(compact_transcript: str) -> str:
    return (
        "Curate short-form clips from this compact transcript.\n"
        "You MUST return EXACTLY 10 distinct clips in the JSON clips array.\n"
        "Use ONLY the start/end timestamps that appear in the lines below "
        "for start_time and end_time.\n"
        "Spread clips across the full timeline and keep them mostly non-overlapping.\n\n"
        f"{compact_transcript}"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse JSON from a model reply, tolerating accidental markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI, OpenAIError

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=api_key)
    try:
        completion = client.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=CurationResponse,
        )
        message = completion.choices[0].message
        if message.parsed is not None:
            return message.parsed.model_dump_json()
        return message.content or ""
    except OpenAIError as exc:
        logger.error("OpenAI curation call failed: %s", exc)
        raise


def _call_anthropic(system: str, user: str) -> str:
    from anthropic import Anthropic, APIError

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in .env")

    client = Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(parts).strip()
    except APIError as exc:
        logger.error("Anthropic curation call failed: %s", exc)
        raise


def _choose_provider() -> Literal["anthropic", "openai"]:
    """Prefer Claude 3.5 Sonnet when configured; otherwise use gpt-4o-mini."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise EnvironmentError(
        "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
    )


def _invoke_llm(system: str, user: str) -> CurationResponse:
    provider = _choose_provider()
    model_label = (
        "claude-3-5-sonnet-20241022" if provider == "anthropic" else "gpt-4o-mini"
    )
    logger.info("Curating clips with provider=%s model=%s", provider, model_label)

    raw_text = (
        _call_anthropic(system, user)
        if provider == "anthropic"
        else _call_openai(system, user)
    )

    try:
        data = _extract_json_object(raw_text)
        return CurationResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Failed to parse LLM curation response: %s", exc)
        raise


def curate_clips(sanitized_transcript_path: str) -> dict[str, Any]:
    """
    Load a sanitized transcript, ask an LLM to pick viral short clips, and save JSON.

    Returns a dict matching ``CurationResponse`` plus ``video_id`` and ``curated_path``.
    """
    path = Path(sanitized_transcript_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Sanitized transcript not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            transcript = json.load(f)

        video_id = str(
            transcript.get("video_id")
            or path.stem.replace("sanitized_", "")
            or "unknown"
        )
        segments = transcript.get("segments") or []
        if not segments:
            raise ValueError(f"Transcript has no segments: {path}")

        boundaries = sorted(
            {
                float(seg["start"])
                for seg in segments
                if seg.get("start") is not None
            }
            | {
                float(seg["end"])
                for seg in segments
                if seg.get("end") is not None
            }
        )
        video_duration = transcript.get("duration")
        if video_duration is not None:
            video_duration = float(video_duration)

        compact = compress_transcript(str(path))
        curation = _invoke_llm(SYSTEM_PROMPT, _build_user_prompt(compact))

        raw_clips = list(curation.clips)
        print(f"DEBUG: LLM generated {len(raw_clips)} clips before validation.")
        for clip in raw_clips:
            raw_duration = round(float(clip.end_time) - float(clip.start_time), 3)
            print(
                "DEBUG[curator/raw]: "
                f"clip_id={clip.clip_id} "
                f"start={clip.start_time:.3f} end={clip.end_time:.3f} "
                f"duration={raw_duration:.3f}s "
                f"score={clip.virality_score} "
                f"title={clip.title!r}"
            )

        # Snap (+ deterministic whole-segment extend if short), then duration gate
        boundary_snapped: list[Clip] = []
        extended_count = 0
        rejected_count = 0
        for clip in raw_clips:
            raw_duration = round(float(clip.end_time) - float(clip.start_time), 3)
            try:
                snapped, ext_info = _validate_clip_against_transcript(
                    clip,
                    boundaries,
                    video_duration,
                    segments=segments,
                )
                boundary_snapped.append(snapped)
                if ext_info.get("extended"):
                    extended_count += 1
                    print(
                        "DEBUG[curator/extend]: "
                        f"clip_id={clip.clip_id} "
                        f"original_start={ext_info['original_start']:.3f} "
                        f"original_end={ext_info['original_end']:.3f} "
                        f"original_duration={ext_info['original_duration']:.3f} "
                        f"extended_start={ext_info['extended_start']:.3f} "
                        f"extended_end={ext_info['extended_end']:.3f} "
                        f"extended_duration={ext_info['extended_duration']:.3f} "
                        f"merged_segment_count={ext_info['merged_segment_count']} "
                        f"score={clip.virality_score}"
                    )
                print(
                    "DEBUG[curator/snap]: "
                    f"clip_id={clip.clip_id} "
                    f"raw=({clip.start_time:.3f}->{clip.end_time:.3f}, {raw_duration:.3f}s) "
                    f"final=({snapped.start_time:.3f}->{snapped.end_time:.3f}, "
                    f"{snapped.duration:.3f}s) "
                    f"extended={bool(ext_info.get('extended'))} "
                    f"result=PASS"
                )
            except ValueError as exc:
                rejected_count += 1
                try:
                    snapped_preview = _snap_clip_to_boundaries(clip, boundaries)
                    snap_info = (
                        f"snapped=({snapped_preview.start_time:.3f}->"
                        f"{snapped_preview.end_time:.3f}, "
                        f"{snapped_preview.duration:.3f}s)"
                    )
                except Exception:
                    snap_info = "snapped=(unavailable)"
                print(
                    "DEBUG[curator/snap]: "
                    f"clip_id={clip.clip_id} "
                    f"raw=({clip.start_time:.3f}->{clip.end_time:.3f}, {raw_duration:.3f}s) "
                    f"{snap_info} "
                    f"result=REJECT reason={exc}"
                )
                logger.warning("Dropping invalid clip %s: %s", clip.clip_id, exc)

        print(
            f"DEBUG[curator]: {len(boundary_snapped)}/{len(raw_clips)} clips "
            "survived boundary/duration pre-filter; handing to clip_validator."
        )
        print(
            "DEBUG[curator/stats]: "
            f"llm_clips={len(raw_clips)} "
            f"extended={extended_count} "
            f"rejected={rejected_count} "
            f"sent_to_validator={len(boundary_snapped)}"
        )

        # Deterministic sanitize: bounds, 15–60s, overlap, top-N
        final_clips = validate_and_filter_clips(boundary_snapped, max_clips=10)
        print(f"DEBUG: {len(final_clips)} clips remained after validation.")
        print(
            "DEBUG[curator/stats]: "
            f"final_after_validator={len(final_clips)}"
        )

        if not final_clips:
            raise ValueError(
                "No clips remained after validation "
                "(bounds, 15–60s duration, and overlap filters)"
            )

        final = CurationResponse(
            clips=final_clips,
            overall_summary=curation.overall_summary,
        )

        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = TRANSCRIPTS_DIR / f"curated_{video_id}.json"
        payload = final.model_dump()
        payload["video_id"] = video_id
        payload["source_transcript"] = str(path)
        payload["debug_stats"] = {
            "llm_clips": len(raw_clips),
            "extended": extended_count,
            "rejected": rejected_count,
            "sent_to_validator": len(boundary_snapped),
            "final_after_validator": len(final_clips),
        }

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        payload["curated_path"] = str(out_path.resolve())
        logger.info(
            "Saved %s curated clips → %s",
            len(final_clips),
            payload["curated_path"],
        )
        return payload

    except Exception as exc:
        logger.error("Clip curation failed for %s: %s", path, exc)
        raise


def _pick_latest_sanitized(transcripts_dir: Path = TRANSCRIPTS_DIR) -> Path:
    candidates = sorted(
        transcripts_dir.glob("sanitized_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No sanitized_*.json files in {transcripts_dir}. "
            "Run: python -m services.pipeline <url> first."
        )
    return candidates[0]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    sample = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else _pick_latest_sanitized()
    )

    print(f"Curating clips from: {sample}")
    result = curate_clips(str(sample))
    print(f"video_id: {result.get('video_id')}")
    print(f"overall_summary: {result.get('overall_summary')}")
    print(f"clips ({len(result['clips'])}):")
    for clip in result["clips"]:
        print(
            f"  [{clip['clip_id']}] {clip['title']} "
            f"({clip['start_time']:.2f}s → {clip['end_time']:.2f}s, "
            f"score={clip['virality_score']})"
        )
        print(f"      hook: {clip['hook']}")
    print(f"Saved: {result.get('curated_path')}")
