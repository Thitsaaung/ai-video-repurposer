"""Deterministic post-processing for LLM-curated clip candidates."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curator import Clip

logger = logging.getLogger(__name__)

MIN_CLIP_SECONDS = 15.0
MAX_CLIP_SECONDS = 60.0
OVERLAP_THRESHOLD = 0.5  # discard when shared time exceeds 50% of the shorter clip


def _clip_duration(clip: Clip) -> float:
    """Authoritative duration from timestamps (ignore stale duration fields)."""
    return float(clip.end_time) - float(clip.start_time)


def _overlap_seconds(a: Clip, b: Clip) -> float:
    start = max(a.start_time, b.start_time)
    end = min(a.end_time, b.end_time)
    return max(0.0, end - start)


def _significant_overlap(a: Clip, b: Clip, threshold: float = OVERLAP_THRESHOLD) -> bool:
    """
    True when the shared interval is more than ``threshold`` of the shorter clip.

    Example: a 20s and 40s clip sharing 12s → 12/20 = 0.6 → significant.
    """
    overlap = _overlap_seconds(a, b)
    if overlap <= 0:
        return False

    shorter = min(_clip_duration(a), _clip_duration(b))
    if shorter <= 0:
        return True

    return (overlap / shorter) > threshold


def validate_and_filter_clips(clips: list[Clip], max_clips: int = 10) -> list[Clip]:
    """
    Sanitize AI clip output before persistence.

    1. Boundary check: ``start_time >= 0`` and ``start_time < end_time``
    2. Duration limits: keep only clips in ``[15, 60]`` seconds
    3. Overlap elimination: if two clips share >50% of the shorter span,
       keep the higher ``virality_score``
    4. Top-N: sort by ``virality_score`` descending, keep ``max_clips``
    """
    if max_clips < 1:
        raise ValueError("max_clips must be >= 1")

    # --- 1 & 2: boundary + duration filters ---
    print(
        f"DEBUG[validator]: received {len(clips)} clip(s) "
        f"(duration window {MIN_CLIP_SECONDS:.0f}–{MAX_CLIP_SECONDS:.0f}s)"
    )
    eligible: list[Clip] = []
    for clip in clips:
        start = float(clip.start_time)
        end = float(clip.end_time)
        duration = end - start

        if start < 0 or start >= end:
            reason = f"invalid_timestamps start={start} end={end}"
            print(
                "DEBUG[validator]: "
                f"clip_id={clip.clip_id} start={start:.3f} end={end:.3f} "
                f"duration={duration:.3f}s result=REJECT reason={reason}"
            )
            logger.info(
                "Discarding clip_id=%s: invalid bounds start=%s end=%s",
                clip.clip_id,
                start,
                end,
            )
            continue

        if duration < MIN_CLIP_SECONDS or duration > MAX_CLIP_SECONDS:
            reason = (
                f"duration_limits {duration:.3f}s outside "
                f"{MIN_CLIP_SECONDS:.0f}–{MAX_CLIP_SECONDS:.0f}s"
            )
            print(
                "DEBUG[validator]: "
                f"clip_id={clip.clip_id} start={start:.3f} end={end:.3f} "
                f"duration={duration:.3f}s result=REJECT reason={reason}"
            )
            logger.info(
                "Discarding clip_id=%s: duration %.3fs outside %.0f–%.0fs",
                clip.clip_id,
                duration,
                MIN_CLIP_SECONDS,
                MAX_CLIP_SECONDS,
            )
            continue

        print(
            "DEBUG[validator]: "
            f"clip_id={clip.clip_id} start={start:.3f} end={end:.3f} "
            f"duration={duration:.3f}s result=PASS stage=bounds+duration"
        )
        # Keep duration field in sync with timestamps
        eligible.append(
            clip.model_copy(update={"duration": round(duration, 3)})
        )

    # Prefer higher virality first so greedy keep favors better clips
    eligible.sort(
        key=lambda c: (c.virality_score, _clip_duration(c)),
        reverse=True,
    )

    # --- 3: overlap elimination (greedy, score-descending) ---
    kept: list[Clip] = []
    for candidate in eligible:
        conflict = next(
            (existing for existing in kept if _significant_overlap(candidate, existing)),
            None,
        )
        if conflict is not None:
            overlap = _overlap_seconds(candidate, conflict)
            shorter = min(_clip_duration(candidate), _clip_duration(conflict))
            ratio = (overlap / shorter) if shorter > 0 else 1.0
            reason = (
                f"overlap_filtering shares {overlap:.3f}s "
                f"({ratio:.0%} of shorter) with kept clip_id={conflict.clip_id} "
                f"(score={conflict.virality_score})"
            )
            print(
                "DEBUG[validator]: "
                f"clip_id={candidate.clip_id} start={candidate.start_time:.3f} "
                f"end={candidate.end_time:.3f} duration={_clip_duration(candidate):.3f}s "
                f"result=REJECT reason={reason}"
            )
            logger.info(
                "Discarding clip_id=%s (score=%s): overlaps >%.0f%% with clip_id=%s (score=%s)",
                candidate.clip_id,
                candidate.virality_score,
                OVERLAP_THRESHOLD * 100,
                conflict.clip_id,
                conflict.virality_score,
            )
            continue
        print(
            "DEBUG[validator]: "
            f"clip_id={candidate.clip_id} start={candidate.start_time:.3f} "
            f"end={candidate.end_time:.3f} duration={_clip_duration(candidate):.3f}s "
            f"result=PASS stage=overlap"
        )
        kept.append(candidate)

    # --- 4: top N (already score-sorted) ---
    top = kept[:max_clips]
    for dropped in kept[max_clips:]:
        print(
            "DEBUG[validator]: "
            f"clip_id={dropped.clip_id} start={dropped.start_time:.3f} "
            f"end={dropped.end_time:.3f} duration={_clip_duration(dropped):.3f}s "
            f"result=REJECT reason=top_n_cutoff max_clips={max_clips}"
        )

    # Stable, human-friendly ids after filtering
    renumbered = [
        clip.model_copy(update={"clip_id": index})
        for index, clip in enumerate(top, start=1)
    ]

    print(
        "DEBUG[validator]: summary "
        f"in={len(clips)} eligible={len(eligible)} "
        f"after_overlap={len(kept)} final={len(renumbered)}"
    )
    for clip in renumbered:
        print(
            "DEBUG[validator/final]: "
            f"clip_id={clip.clip_id} start={clip.start_time:.3f} "
            f"end={clip.end_time:.3f} duration={clip.duration:.3f}s "
            f"result=KEEP score={clip.virality_score}"
        )

    logger.info(
        "validate_and_filter_clips: %s in → %s eligible → %s after overlap → %s final",
        len(clips),
        len(eligible),
        len(kept),
        len(renumbered),
    )
    return renumbered
