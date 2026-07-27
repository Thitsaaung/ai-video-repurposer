"""Map internal pipeline errors to short, user-facing messages.

Raw diagnostics stay in server logs. Never put stack traces or vendor
internals (Whisper, cookies, MB sizes) into API ``error`` fields.
"""

from __future__ import annotations

GENERIC_FAILURE_MESSAGE = (
    "Video processing failed. Please try again or use a different YouTube URL."
)

INVALID_YOUTUBE_LINK_MESSAGE = "Please enter a valid YouTube video link."

_VIDEO_TOO_LONG_MESSAGE = (
    "This video exceeds the current processing limit.\n"
    "Please try a shorter video."
)

_VIDEO_UNAVAILABLE_MESSAGE = "This video isn't publicly available."

_ACCESS_RETRY_MESSAGE = (
    "We couldn't access this YouTube video right now. Please try again later."
)

_NETWORK_INTERRUPT_MESSAGE = (
    "Network connection was interrupted. Please try again."
)


def to_user_facing_error(raw: str | None) -> str:
    """
    Classify ``raw`` exception/engine text into a friendly client message.

    First matching rule wins. Unknown text falls back to the generic message.
    """
    text = (raw or "").strip()
    if not text:
        return GENERIC_FAILURE_MESSAGE

    lower = text.lower()

    # 1) Whisper / compressed-audio size limit (no MB / Whisper wording).
    if (
        "compressed audio is still" in lower
        or "mb for whisper" in lower
        or "limit 24 mb" in lower
    ):
        return _VIDEO_TOO_LONG_MESSAGE

    # 2) Bot / login wall (before "unavailable" — wording overlaps).
    if (
        "sign in to confirm" in lower
        or "not a bot" in lower
        or "login required" in lower
        or "please sign in" in lower
    ):
        return _ACCESS_RETRY_MESSAGE

    # 3) Private / removed / blocked.
    if (
        "private video" in lower
        or "video unavailable" in lower
        or "has been removed" in lower
        or "violating" in lower
        or "copyright claim" in lower
        or (
            "not available" in lower
            and "network" not in lower
            and "timed out" not in lower
        )
    ):
        return _VIDEO_UNAVAILABLE_MESSAGE

    # 4) Network timeouts.
    if (
        "timed out" in lower
        or "timeout" in lower
        or "read timed out" in lower
        or "the read operation timed out" in lower
    ):
        return _NETWORK_INTERRUPT_MESSAGE

    # 5) Invalid YouTube link (submit-time + rare job-time echoes).
    if (
        "could not find a youtube video id" in lower
        or "missing youtube video id" in lower
        or "only youtube urls" in lower
        or "url must start with http" in lower
        or "a youtube url is required" in lower
        or "please enter a valid youtube video link" in lower
    ):
        return INVALID_YOUTUBE_LINK_MESSAGE

    return GENERIC_FAILURE_MESSAGE
