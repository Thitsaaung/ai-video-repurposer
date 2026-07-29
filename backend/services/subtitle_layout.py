"""Subtitle Layout Engine — Phase 1.

Pack Whisper segments into ≤3-line SRT cues (prefer 2) before FFmpeg burn-in.

Design: docs/subtitle_layout_design.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_LINES = 3
PREFERRED_LINES = 2
# Conservative vs FontSize≈22 on 9:16 so libass rarely soft-wraps further.
MAX_CHARS_PER_LINE = 24
MAX_WORDS_PER_LINE = 5
CHAR_GRACE = 1.12

CONJUNCTIONS = frozenset(
    {
        "and",
        "but",
        "or",
        "so",
        "because",
        "when",
        "while",
        "if",
        "that",
        "which",
        "who",
        "as",
        "than",
        "into",
        "onto",
        "from",
        "with",
        "without",
        "for",
        "to",
    }
)

_ARTICLES = frozenset({"the", "a", "an"})

_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?(?:-[A-Za-z0-9]+)*[.,!?;:]*|[.,!?;:]"
)


@dataclass(frozen=True, slots=True)
class LayoutCue:
    """One timed caption unit with explicit visual lines."""

    start: float
    end: float
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def word_count(self) -> int:
        return sum(len(line.split()) for line in self.lines)


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    return _TOKEN_RE.findall(normalized)


def _core_word(token: str) -> str:
    return token.rstrip(".,!?;:")


def _is_capitalized_word(token: str) -> bool:
    core = _core_word(token)
    if not core:
        return False
    if core[0].islower() and any(ch.isupper() for ch in core[1:]):
        return True
    return core[0].isupper()


def _is_versionish(token: str) -> bool:
    core = _core_word(token)
    return bool(re.fullmatch(r"\d+[A-Za-z]?", core)) or bool(
        re.fullmatch(r"[A-Z]\d+", core)
    )


def mark_protected_spans(tokens: list[str]) -> list[tuple[int, int]]:
    """Half-open [start, end) spans that must stay on one line."""
    n = len(tokens)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not _is_capitalized_word(tokens[i]) and not _is_versionish(tokens[i]):
            i += 1
            continue
        if _core_word(tokens[i]).lower() in _ARTICLES and (
            i + 1 >= n or not _is_capitalized_word(tokens[i + 1])
        ):
            i += 1
            continue

        j = i + 1
        while j < n and (
            _is_capitalized_word(tokens[j]) or _is_versionish(tokens[j])
        ):
            # Never extend a protected name across a sentence boundary.
            if tokens[j - 1].endswith((".", "?", "!")):
                break
            j += 1

        if j - i >= 2:
            spans.append((i, j))
        elif j - i == 1 and _is_capitalized_word(tokens[i]):
            core = _core_word(tokens[i])
            if any(ch.isdigit() for ch in core) or (
                len(core) > 1 and any(ch.isupper() for ch in core[1:])
            ):
                spans.append((i, j))
        i = max(j, i + 1)

    if not spans:
        return []
    spans.sort()
    merged: list[tuple[int, int]] = [spans[0]]
    for a, b in spans[1:]:
        la, lb = merged[-1]
        if a <= lb:
            merged[-1] = (la, max(lb, b))
        else:
            merged.append((a, b))
    return merged


def _span_covering(index: int, spans: list[tuple[int, int]]) -> tuple[int, int] | None:
    for a, b in spans:
        if a <= index < b:
            return (a, b)
    return None


def _break_priority_before(tokens: list[str], index: int) -> int:
    """Lower = stronger break before tokens[index]."""
    if index <= 0 or index >= len(tokens):
        return 99
    prev = tokens[index - 1]
    cur = tokens[index]
    prev_core = _core_word(prev)
    cur_core = _core_word(cur)

    if prev.endswith((".", "?", "!")):
        return 1
    if prev.endswith((",", ";", ":")):
        return 2
    if cur_core.lower() in CONJUNCTIONS:
        return 3
    if (
        prev_core
        and cur_core
        and prev_core[0].islower()
        and cur_core[0].isupper()
        and cur_core.lower() not in _ARTICLES
    ):
        return 3
    return 4


def _line_text(tokens: list[str]) -> str:
    return " ".join(tokens)


def _fits(tokens: list[str], *, grace: float = 1.0) -> bool:
    if not tokens:
        return True
    if len(tokens) > MAX_WORDS_PER_LINE:
        return False
    return len(_line_text(tokens)) <= int(MAX_CHARS_PER_LINE * grace)


def _next_chunk_end(tokens: list[str], j: int, protected: list[tuple[int, int]]) -> int:
    span = _span_covering(j, protected)
    if span is not None and span[0] == j:
        return span[1]
    return j + 1


def _refine_line_breaks(
    tokens: list[str], protected: list[tuple[int, int]]
) -> list[list[str]]:
    """Greedy pack into lines using phrase-aware break priorities."""
    if not tokens:
        return []

    lines: list[list[str]] = []
    i = 0
    n = len(tokens)

    while i < n:
        j = i
        best_break = i + 1
        best_pri = 99

        while j < n:
            end = _next_chunk_end(tokens, j, protected)
            trial = tokens[i:end]
            if not _fits(trial) and end > i + 1:
                break
            if (
                not _fits(trial, grace=CHAR_GRACE)
                and _span_covering(j, protected) is not None
                and _span_covering(j, protected)[0] == j
            ):
                break

            j = end
            if not _fits(tokens[i:j]):
                break

            best_break = j
            if tokens[j - 1].endswith((".", "?", "!")):
                best_pri = 1
                break

            if j < n:
                pri = _break_priority_before(tokens, j)
                near_full = (
                    len(tokens[i:j]) >= 3
                    or len(_line_text(tokens[i:j])) >= MAX_CHARS_PER_LINE * 0.6
                )
                if pri < best_pri and near_full:
                    best_pri = pri
                    best_break = j
                if pri <= 2 and near_full:
                    best_break = j
                    if pri == 1:
                        break
                    # comma: take break when line already has content
                    if len(tokens[i:j]) >= 3:
                        break
                if pri == 3 and near_full and len(tokens[i:j]) >= 3:
                    best_break = j
                    # keep scanning a bit for stronger break unless very full
                    if len(_line_text(tokens[i:j])) >= MAX_CHARS_PER_LINE * 0.85:
                        break

        if best_break <= i:
            best_break = min(i + 1, n)

        # Avoid leaving a single orphan token for the next line when possible.
        remaining = n - best_break
        if remaining == 1 and best_break - i >= 3:
            for k in range(best_break - 1, i, -1):
                span = _span_covering(k, protected)
                if span is not None and span[0] != k:
                    continue
                if _fits(tokens[i:k]) and n - k >= 2:
                    best_break = k
                    break

        lines.append(tokens[i:best_break])
        i = best_break

    return lines


def fix_orphans(lines: list[str]) -> list[str]:
    """Avoid single-word final lines when a local redistribute is possible."""
    if len(lines) < 2:
        return lines

    result = list(lines)
    last_words = result[-1].split()
    if len(last_words) != 1:
        return result

    prev_words = result[-2].split()
    if len(prev_words) < 3:
        merged = result[-2] + " " + result[-1]
        if len(merged) <= int(MAX_CHARS_PER_LINE * CHAR_GRACE) and len(
            merged.split()
        ) <= MAX_WORDS_PER_LINE + 1:
            return result[:-2] + [merged]
        return result

    take = 2 if len(prev_words) >= 4 else 1
    take = min(take, len(prev_words) - 2)
    if take < 1:
        take = 1
    moved = prev_words[-take:]
    new_prev = prev_words[:-take]
    new_last = moved + last_words
    new_prev_text = " ".join(new_prev)
    new_last_text = " ".join(new_last)
    if len(new_prev_text) <= int(MAX_CHARS_PER_LINE * CHAR_GRACE) and len(
        new_last_text
    ) <= int(MAX_CHARS_PER_LINE * CHAR_GRACE):
        result[-2] = new_prev_text
        result[-1] = new_last_text
        return result

    merged = result[-2] + " " + result[-1]
    if len(merged) <= int(MAX_CHARS_PER_LINE * CHAR_GRACE):
        return result[:-2] + [merged]
    return result


def _lines_to_text_list(token_lines: list[list[str]]) -> list[str]:
    return [_line_text(t) for t in token_lines if t]


def _hard_split_long_line(line: str) -> list[str]:
    words = line.split()
    if _fits(words, grace=CHAR_GRACE) or len(words) <= 1:
        return [line]
    out: list[str] = []
    buf: list[str] = []
    for w in words:
        trial = buf + [w]
        if buf and not _fits(trial, grace=CHAR_GRACE):
            out.append(" ".join(buf))
            buf = [w]
        else:
            buf = trial
    if buf:
        out.append(" ".join(buf))
    return out


def _chunk_lines_into_cues(line_strs: list[str]) -> list[list[str]]:
    """Prefer 2-line cues; never exceed MAX_LINES; split on sentence ends."""
    if not line_strs:
        return []

    sentence_groups: list[list[str]] = []
    current: list[str] = []
    for line in line_strs:
        current.append(line)
        if line.rstrip().endswith((".", "?", "!")):
            sentence_groups.append(current)
            current = []
    if current:
        sentence_groups.append(current)

    cues: list[list[str]] = []
    for group in sentence_groups:
        cues.extend(_chunk_flat_lines(group))
    return cues


def _chunk_flat_lines(line_strs: list[str]) -> list[list[str]]:
    """Pack flat lines into cues: prefer 2, allow 3, never more."""
    if not line_strs:
        return []

    cues: list[list[str]] = []
    i = 0
    while i < len(line_strs):
        remaining = len(line_strs) - i
        if remaining <= PREFERRED_LINES:
            cues.append(line_strs[i:])
            break
        if remaining == MAX_LINES:
            cues.append(line_strs[i:])
            break
        # Prefer closing at 2 whenever more than 3 lines remain (or 4 → 2+2).
        if remaining >= 4:
            cues.append(line_strs[i : i + PREFERRED_LINES])
            i += PREFERRED_LINES
            continue
        # remaining == 3 → one 3-line cue
        cues.append(line_strs[i : i + MAX_LINES])
        i += MAX_LINES
    return cues


def _allocate_time(cue_line_groups: list[list[str]], t0: float, t1: float) -> list[LayoutCue]:
    """
    Proportional word-count timing inside [t0, t1].

    Guarantees continuous abutting cues in millisecond space:
    end(prev) == start(next), no gaps, no overlaps.
    """
    if not cue_line_groups:
        return []
    if t1 < t0:
        t1 = t0

    start_ms = int(round(t0 * 1000.0))
    end_ms = int(round(t1 * 1000.0))
    if end_ms < start_ms:
        end_ms = start_ms
    total_ms = end_ms - start_ms

    weights = [max(1, sum(len(line.split()) for line in g)) for g in cue_line_groups]
    weight_sum = sum(weights)

    if len(cue_line_groups) == 1 or total_ms == 0:
        return [
            LayoutCue(
                start=start_ms / 1000.0,
                end=end_ms / 1000.0,
                lines=tuple(cue_line_groups[0]),
            )
        ]

    # Distribute integer milliseconds; force contiguous boundaries.
    boundaries = [start_ms]
    acc = 0
    for idx, w in enumerate(weights[:-1]):
        acc += w
        # Floor division keeps monotonic; last cue absorbs remainder.
        cut = start_ms + (total_ms * acc) // weight_sum
        if cut <= boundaries[-1]:
            cut = boundaries[-1]  # zero-length avoided below
        boundaries.append(cut)
    boundaries.append(end_ms)

    # Ensure strictly increasing ends where possible (avoid zero-length mid cues).
    for i in range(1, len(boundaries) - 1):
        if boundaries[i] <= boundaries[i - 1]:
            boundaries[i] = boundaries[i - 1] + 1
    # Re-clamp if we overshot
    for i in range(len(boundaries) - 2, 0, -1):
        if boundaries[i] >= boundaries[i + 1]:
            boundaries[i] = max(boundaries[i - 1], boundaries[i + 1] - 1)
    boundaries[0] = start_ms
    boundaries[-1] = end_ms

    cues: list[LayoutCue] = []
    for idx, group in enumerate(cue_line_groups):
        a = boundaries[idx]
        b = boundaries[idx + 1]
        if b < a:
            b = a
        cues.append(
            LayoutCue(start=a / 1000.0, end=b / 1000.0, lines=tuple(group))
        )
    return cues


def _split_mid_sentence_lines(line_strs: list[str]) -> list[str]:
    """If a line still contains '. ' / '? ' / '! ' mid-string, split there."""
    out: list[str] = []
    for line in line_strs:
        buf = line
        while True:
            cut = None
            for sep in (". ", "? ", "! "):
                idx = buf.find(sep)
                if idx >= 0:
                    cut = idx + 1  # keep punctuation on left
                    break
            if cut is None:
                if buf.strip():
                    out.append(buf.strip())
                break
            left = buf[:cut].strip()
            right = buf[cut:].strip()
            if left:
                out.append(left)
            buf = right
    return out


def layout_segment(start: float, end: float, text: str) -> list[LayoutCue]:
    """
    Layout one Whisper segment into one or more caption cues.

    Times stay inside [start, end]. Sequential cues abut with no gaps/overlaps.
    """
    tokens = tokenize(text)
    if not tokens:
        return []

    t0 = float(start)
    t1 = float(end)
    if t1 < t0:
        t1 = t0

    protected = mark_protected_spans(tokens)
    token_lines = _refine_line_breaks(tokens, protected)
    line_strs: list[str] = []
    for line in fix_orphans(_lines_to_text_list(token_lines)):
        line_strs.extend(_hard_split_long_line(line))
    line_strs = fix_orphans(line_strs)
    line_strs = _split_mid_sentence_lines(line_strs)

    groups = _chunk_lines_into_cues(line_strs)
    groups = [fix_orphans(g)[:MAX_LINES] for g in groups if g]

    # Safety: never exceed max lines
    fixed: list[list[str]] = []
    for g in groups:
        if len(g) <= MAX_LINES:
            fixed.append(g)
        else:
            for i in range(0, len(g), MAX_LINES):
                fixed.append(g[i : i + MAX_LINES])

    cues = _allocate_time(fixed, t0, t1)

    out: list[LayoutCue] = []
    for cue in cues:
        lines = tuple(fix_orphans(list(cue.lines))[:MAX_LINES])
        if not lines:
            continue
        out.append(LayoutCue(start=cue.start, end=cue.end, lines=lines))

    # If any empty cues were dropped, re-allocate so timing stays continuous.
    if len(out) != len(cues):
        out = _allocate_time([list(c.lines) for c in out], t0, t1)

    return out


def layout_segment_texts(start: float, end: float, text: str) -> list[str]:
    """Convenience: return cue body strings (lines joined by newline)."""
    return [c.text for c in layout_segment(start, end, text)]


def words_from_cues(cues: list[LayoutCue]) -> list[str]:
    """Flatten cue words for integrity checks (punctuation kept on tokens)."""
    words: list[str] = []
    for cue in cues:
        for line in cue.lines:
            words.extend(line.split())
    return words
