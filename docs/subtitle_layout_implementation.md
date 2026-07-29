# Subtitle Layout Engine — Implementation Report

**Date:** 2026-07-30 (Phase 1 refined)  
**Related:** [`subtitle_layout_design.md`](./subtitle_layout_design.md), [`subtitle_layout_report.md`](./subtitle_layout_report.md)  
**Diagnostics:** [`subtitle_layout_phase1_diagnostics.txt`](./subtitle_layout_phase1_diagnostics.txt)

---

## Files changed

| File | Change |
|------|--------|
| `backend/services/subtitle_layout.py` | Phase 1 layout engine (tighter line budgets, continuous ms timing, sentence-safe proper nouns) |
| `backend/services/video_cutter.py` | `generate_srt_for_clip()` calls `layout_segment()` before writing SRT |
| `backend/tests/test_subtitle_layout.py` | Regression tests including Safari multi-cue + continuity |
| `docs/subtitle_layout_phase1_diagnostics.txt` | short / medium / long / extremely_long dumps |
| `docs/subtitle_layout_implementation.md` | This report |

**Not changed:** FFmpeg filters, `_SUBTITLE_FORCE_STYLE`, colours, margins, frontend, API routes.

---

## Algorithm used

Per Whisper segment overlapping the clip window:

1. Normalize + tokenize (punctuation stays on tokens).  
2. Mark protected spans (multi-word capitals / brand+number); **do not** extend spans across `.?!`.  
3. Phrase-aware line packing (`MAX_CHARS_PER_LINE=24`, `MAX_WORDS_PER_LINE=5`) with break priority: sentence → comma → conjunction → length.  
4. Anti-orphan redistribute; hard-split oversized lines; split any residual mid-line `. ` / `? ` / `! `.  
5. Chunk into cues: **prefer 2 lines**, allow 3, never more; sentence ends start new cue groups.  
6. Allocate time by **word-count weights** inside the segment `[start, end]` using **integer milliseconds** so `end(prev) == start(next)` (no gaps/overlaps).  

---

## Before / after (acceptance sample)

**Input**

```text
The next Safari tip we're going to talk about is called Reader. Have you ever been...
```

**Before:** one long SRT line → libass soft-wrap to ~6 visual lines.

**After (diagnostics):** multiple cues, each ≤3 lines, e.g.

```text
cue 1: The next Safari tip / we're going to talk / about is called Reader.
cue 2: Have you ever been on / a website that is so
...
```

---

## Edge cases handled

- Short one-line cues  
- Sentence-boundary cue splits (`?` / `.`)  
- Proper nouns / `iPhone 17 Pro` kept together  
- Sentence-initial capitals not glued onto prior names (`Reader.` ‖ `Have`)  
- Orphan single-word last lines  
- Continuous abutting cues in ms space  
- Word integrity (no drop/dup vs tokenize)

---

## Limitations

- English-first heuristics.  
- Char budget is heuristic (FontSize/OS font can still rarely soft-wrap).  
- Very short segment durations can produce brief cues (no min-duration merge in Phase 1 refined path).  
- Cross-segment Whisper gaps/overlaps are preserved (continuity is enforced **within** each segment’s laid-out cues).

---

## Tests

```powershell
cd backend
$env:PYTHONPATH = "."
..\venv\Scripts\python.exe -m unittest tests.test_subtitle_layout -v
```

12 tests passing.
