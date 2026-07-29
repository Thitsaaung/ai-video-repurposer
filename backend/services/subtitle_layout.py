"""Subtitle Layout Engine — pack Whisper segments into ≤3-line SRT cues.

Design: docs/subtitle_layout_design.md
Pure functions only; no FFmpeg / force_style changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_LINES = 3
PREFERRED_LINES = 2
MAX_CHARS_PER_LINE = 32
MAX_WORDS_PER_LINE = 6
MIN_CUE_DURATION = 0.7
CHAR_GRACE = 1.15  # orphan merge / protected overflow

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

# Leading articles alone are not proper nouns.
_ARTICLES = frozenset({"the", "a", "an"})

# Token: word characters including apostrophe/hyphen, optional trailing punctuation.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?(?:-[A-Za-z0-9]+)*[.,!?;:]*|[.,!?;:]")


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
    """Split into words with attached trailing punctuation."""
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
    # iPhone / ChatGPT style
    if core[0].islower() and any(ch.isupper() for ch in core[1:]):
        return True
    return core[0].isupper()


def _is_versionish(token: str) -> bool:
    core = _core_word(token)
    return bool(re.fullmatch(r"\d+[A-Za-z]?", core)) or bool(
        re.fullmatch(r"[A-Z]\d+", core)
    )


def mark_protected_spans(tokens: list[str]) -> list[tuple[int, int]]:
    """
    Return half-open [start, end) token index spans that must stay on one line.

    Covers adjacent capitalized runs and brand+number patterns (e.g. iPhone 17 Pro).
    """
    n = len(tokens)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not _is_capitalized_word(tokens[i]) and not _is_versionish(tokens[i]):
            i += 1
            continue

        # Skip lone article
        if _core_word(tokens[i]).lower() in _ARTICLES and (
            i + 1 >= n or not _is_capitalized_word(tokens[i + 1])
        ):
            i += 1
            continue

        j = i + 1
        while j < n and (
            _is_capitalized_word(tokens[j])
            or _is_versionish(tokens[j])
            or (
                # allow mid connectors inside titles rarely — keep tight
                False
            )
        ):
            j += 1

        # Protect multi-token names, or single camelCase/brand token with digit neighbor
        if j - i >= 2:
            spans.append((i, j))
        elif j - i == 1 and _is_capitalized_word(tokens[i]):
            # Single capitalized token: protect only brand-like (has internal capital or alnum mix)
            core = _core_word(tokens[i])
            if any(ch.isdigit() for ch in core) or (
                len(core) > 1 and any(ch.isupper() for ch in core[1:])
            ):
                spans.append((i, j))
        i = max(j, i + 1)

    # Merge overlapping
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
    """
    Priority for breaking BEFORE tokens[index] (0=best/strongest ... higher=weaker).
    index is in 1..len(tokens).
    """
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
    # Soft clause: capitalized continuation after lowercase (new phrase)
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


def _refine_line_breaks(
    tokens: list[str], protected: list[tuple[int, int]]
) -> list[list[str]]:
    """
    Greedy pack with look-ahead: fill a line, then choose the best break near the budget.
    """
    if not tokens:
        return []

    lines: list[list[str]] = []
    i = 0
    n = len(tokens)

    while i < n:
        # Grow window from i
        j = i
        best_break = i + 1  # at least one token
        while j < n:
            span = _span_covering(j, protected)
            if span is not None and span[0] == j:
                end = span[1]
            else:
                end = j + 1
            trial = tokens[i:end]
            if not _fits(trial) and end > i + 1:
                break
            if not _fits(trial, grace=CHAR_GRACE) and span is not None and span[0] == j:
                # protected won't fit with prior — break before it
                break
            j = end
            # Record candidate break at j if within budget
            if _fits(tokens[i:j]):
                best_break = j
                # If the line we just closed ends a sentence, stop growing.
                if tokens[j - 1].endswith((".", "?", "!")):
                    best_break = j
                    break
                # Prefer stronger break points when near capacity
                if j < n:
                    pri = _break_priority_before(tokens, j)
                    if pri <= 3 and (
                        len(tokens[i:j]) >= 3
                        or len(_line_text(tokens[i:j])) >= MAX_CHARS_PER_LINE * 0.55
                    ):
                        best_break = j
                        if pri == 1:
                            break
            else:
                break

        if best_break <= i:
            best_break = min(i + 1, n)

        # Avoid orphan: if remaining after break is 1 token and we can shorten break
        remaining = n - best_break
        if remaining == 1 and best_break - i >= 3:
            # try pull last word onto next line by breaking earlier at a soft point
            for k in range(best_break - 1, i, -1):
                if _span_covering(k, protected) and _span_covering(k, protected)[0] != k:
                    continue
                if _break_priority_before(tokens, k) <= 4 and _fits(tokens[i:k]):
                    if n - k >= 2:
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
        # Try merge last two if within grace
        merged = result[-2] + " " + result[-1]
        if len(merged) <= int(MAX_CHARS_PER_LINE * CHAR_GRACE) and len(
            merged.split()
        ) <= MAX_WORDS_PER_LINE + 1:
            return result[:-2] + [merged]
        return result

    # Pull 1–2 words from previous line onto last
    take = 2 if len(prev_words) >= 4 else 1
    take = min(take, len(prev_words) - 2)  # leave at least 2 on previous when possible
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

    # Merge fallback
    merged = result[-2] + " " + result[-1]
    if len(merged) <= int(MAX_CHARS_PER_LINE * CHAR_GRACE):
        return result[:-2] + [merged]
    return result


def _lines_to_text_list(token_lines: list[list[str]]) -> list[str]:
    return [_line_text(t) for t in token_lines if t]


def _chunk_lines_into_cues(line_strs: list[str]) -> list[list[str]]:
    """Split a flat line list into cue groups of at most MAX_LINES (prefer closing at 2 when possible)."""
    if not line_strs:
        return []

    # First split on hard sentence boundaries (lines ending with .?!).
    sentence_groups: list[list[str]] = []
    current: list[str] = []
    for line in line_strs:
        current.append(line)
        stripped = line.rstrip()
        if stripped.endswith((".", "?", "!")):
            sentence_groups.append(current)
            current = []
    if current:
        sentence_groups.append(current)

    cues: list[list[str]] = []
    for group in sentence_groups:
        cues.extend(_chunk_flat_lines(group))
    return cues


def _chunk_flat_lines(line_strs: list[str]) -> list[list[str]]:
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
        if remaining == MAX_LINES + 1:
            # 4 lines → 2+2 better than 3+1
            cues.append(line_strs[i : i + 2])
            i += 2
            continue
        take = MAX_LINES
        if remaining > MAX_LINES and remaining - 3 == 1:
            take = 2
        cues.append(line_strs[i : i + take])
        i += take
    return cues


def _merge_short_duration_cues(
    cues: list[LayoutCue], t0: float, t1: float
) -> list[LayoutCue]:
    """Merge adjacent cues when duration floor cannot be met; never exceed MAX_LINES."""
    if not cues:
        return []
    if t1 <= t0:
        return [
            LayoutCue(start=t0, end=t0, lines=cues[0].lines)
        ]

    result = list(cues)
    changed = True
    while changed and len(result) > 1:
        changed = False
        durations = [c.end - c.start for c in result]
        for idx, dur in enumerate(durations):
            if dur + 1e-9 >= MIN_CUE_DURATION:
                continue
            # Merge with neighbor that yields ≤ MAX_LINES
            candidates: list[tuple[int, int]] = []
            if idx > 0:
                candidates.append((idx - 1, idx))
            if idx + 1 < len(result):
                candidates.append((idx, idx + 1))
            merged_ok = False
            for a, b in candidates:
                combined = list(result[a].lines) + list(result[b].lines)
                if len(combined) > MAX_LINES:
                    continue
                new_cue = LayoutCue(
                    start=result[a].start,
                    end=result[b].end,
                    lines=tuple(fix_orphans(combined)),
                )
                result = result[:a] + [new_cue] + result[b + 1 :]
                changed = True
                merged_ok = True
                break
            if merged_ok:
                break
            # Cannot merge without exceeding lines — keep short cue
        if not changed:
            break

    # Re-allocate times after merges for consistency
    return _allocate_time([list(c.lines) for c in result], t0, t1)


def _allocate_time(cue_line_groups: list[list[str]], t0: float, t1: float) -> list[LayoutCue]:
    if not cue_line_groups:
        return []
    if t1 < t0:
        t1 = t0
    if len(cue_line_groups) == 1:
        return [LayoutCue(start=t0, end=t1, lines=tuple(cue_line_groups[0]))]

    weights = [max(1, sum(len(line.split()) for line in g)) for g in cue_line_groups]
    total = float(sum(weights))
    cues: list[LayoutCue] = []
    cursor = t0
    acc = 0.0
    for idx, group in enumerate(cue_line_groups):
        acc += weights[idx]
        if idx == len(cue_line_groups) - 1:
            end = t1
        else:
            end = t0 + (t1 - t0) * (acc / total)
        # monotonic / numeric stability
        if end < cursor:
            end = cursor
        cues.append(LayoutCue(start=cursor, end=end, lines=tuple(group)))
        cursor = end
    # Ensure last end is exactly t1
    if cues:
        last = cues[-1]
        cues[-1] = LayoutCue(start=last.start, end=t1, lines=last.lines)
    return cues


def layout_segment(start: float, end: float, text: str) -> list[LayoutCue]:
    """
    Layout one Whisper segment into one or more caption cues.

    Times are absolute (same domain as the segment). Caller shifts to clip-relative.
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
    line_strs = fix_orphans(_lines_to_text_list(token_lines))
    # Ensure no line exceeds max by re-splitting pathological lines
    sanitized: list[str] = []
    for line in line_strs:
        words = line.split()
        if _fits(words, grace=CHAR_GRACE) or len(words) <= 1:
            sanitized.append(line)
            continue
        # Hard split long line
        buf: list[str] = []
        for w in words:
            trial = buf + [w]
            if buf and not _fits(trial, grace=CHAR_GRACE):
                sanitized.append(" ".join(buf))
                buf = [w]
            else:
                buf = trial
        if buf:
            sanitized.append(" ".join(buf))

    sanitized = fix_orphans(sanitized)
    groups = _chunk_lines_into_cues(sanitized)
    groups = [fix_orphans(g) for g in groups]
    # Hard assert max lines
    fixed_groups: list[list[str]] = []
    for g in groups:
        if len(g) <= MAX_LINES:
            fixed_groups.append(g)
        else:
            for i in range(0, len(g), MAX_LINES):
                fixed_groups.append(g[i : i + MAX_LINES])

    cues = _allocate_time(fixed_groups, t0, t1)
    cues = _merge_short_duration_cues(cues, t0, t1)

    # Final invariants
    out: list[LayoutCue] = []
    for cue in cues:
        lines = tuple(fix_orphans(list(cue.lines))[:MAX_LINES])
        if not lines:
            continue
        out.append(LayoutCue(start=cue.start, end=cue.end, lines=lines))
    return out


def layout_segment_texts(start: float, end: float, text: str) -> list[str]:
    """Convenience: return cue body strings (lines joined by newline)."""
    return [c.text for c in layout_segment(start, end, text)]
