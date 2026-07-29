# Subtitle Layout Engine — Implementation Report

**Date:** 2026-07-30  
**Related:** [`subtitle_layout_design.md`](./subtitle_layout_design.md), [`subtitle_layout_report.md`](./subtitle_layout_report.md)

---

## Files changed

| File | Change |
|------|--------|
| `backend/services/subtitle_layout.py` | **New** — layout engine (tokenize, protect nouns, pack lines, allocate time) |
| `backend/services/video_cutter.py` | `generate_srt_for_clip()` calls `layout_segment()` before writing SRT |
| `backend/tests/test_subtitle_layout.py` | **New** — 10 regression tests |
| `backend/tests/__init__.py` | **New** — package marker |
| `docs/subtitle_layout_implementation.md` | **New** — this report |

**Not changed:** FFmpeg filters, `_SUBTITLE_FORCE_STYLE`, colours, margins, frontend, curator, Whisper.

---

## Algorithm implemented

Pipeline per Whisper segment overlapping the clip:

1. **Normalize / tokenize** — whitespace collapse; keep trailing punctuation on tokens.  
2. **Protect spans** — adjacent capitalized runs and brand+number patterns (`iPhone 17 Pro`, `Premier League`).  
3. **Refine line breaks** — grow lines under `MAX_CHARS_PER_LINE=32` / `MAX_WORDS_PER_LINE=6`; prefer breaks after `.?!`, then `,;:`, then before conjunctions; never cut inside a protected span.  
4. **Force sentence cue splits** — lines ending in `.?!` start a new cue group.  
5. **Chunk to ≤3 lines** — prefer 2; avoid 3+1 splits (use 2+2).  
6. **Anti-orphan** — redistribute or merge single-word final lines when possible.  
7. **Allocate time** — proportional word weights inside the parent `[start, end]` (clip-clipped absolute window).  
8. **Min duration merge** — merge adjacent cues under `0.7s` when combined lines ≤ 3.

Constants (MVP):

```text
MAX_LINES=3, PREFERRED_LINES=2
MAX_CHARS_PER_LINE=32, MAX_WORDS_PER_LINE=6
MIN_CUE_DURATION=0.7
```

---

## Before / after examples

### Short

**Before (one SRT line):** `Show Reader.`  
**After:**

```text
Show Reader.
```

### Long sentence

**Before:** single cue, full string → libass soft-wrap to 5–7 lines  

**After (example run):**

```text
The next Safari tip we're going
to talk about is called Reader.
```

(≤3 lines; prefer 2)

### Very long Whisper segment

**Before:** one cue ≈21 words → tall soft-wrap stack  

**After:**

```text
[cue 1]
this away so you can focus
on the content you
want to read.

[cue 2]
Now a quick note here, Reader
is not
```

### Question

**After:**

```text
[cue 1] Why does this matter?
[cue 2] Because your audience
        watches muted.
```

### Numbers / proper nouns

**After:** `iPhone 17 Pro` and `Premier League` kept on one line (not split mid-name).

---

## Tests

```powershell
cd backend
$env:PYTHONPATH = "."
..\venv\Scripts\python.exe -m unittest tests.test_subtitle_layout -v
```

Coverage:

1. Short sentence  
2. Long sentence  
3. Very long Whisper segment  
4. Comma split  
5. Question sentence  
6. Proper noun  
7. Numbers  
8. Mixed punctuation  
9. Maximum line count  
10. Deterministic output  

All passing at commit time.

---

## Limitations

- English-first conjunction / capitalization heuristics.  
- `MAX_CHARS_PER_LINE` is a heuristic, not pixel-perfect for every FontSize/OS font.  
- Extremely large FontSize can still cause rare libass soft-wrap on a single long protected span.  
- Clip-windowing still attaches full overlapping segment text (pre-existing behavior).  
- Min-duration merges can recombine short sentence cues on very short segments.  
- Exact golden line breaks may differ slightly from design doc examples while still honoring max-3 / prefer-2 / noun protection.

---

## Future improvements

- Tie `MAX_CHARS_PER_LINE` to the active subtitle preset (Strategy B).  
- Optional word-level timestamps when Whisper word granularity is enabled.  
- Richer proper-noun / title dictionary.  
- i18n phrase breakers.  
- ASS `WrapStyle` safety net.  
- Bake-off re-render of `comparison/` clips for visual QA after layout ships.

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Layout before SRT (not libass-only) | Done |
| Prefer 2 / max 3 lines | Enforced in engine + tests |
| Whisper timing preserved inside segment window | Proportional allocation |
| No FFmpeg / force_style changes | Confirmed |
| Deterministic | Tested |
| Unit tests | 10/10 pass |
