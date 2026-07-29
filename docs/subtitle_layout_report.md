# Subtitle Layout Investigation Report

> **T-Clipper** — Investigation only. No code, FFmpeg, or `force_style` changes in this work.  
> **Date:** 2026-07-30  
> **Scope:** Why burned-in captions become 5–7 short visual lines despite unused horizontal space.  
> **Evidence clip:** comparison pack / `hXET-58xrqM` clip 1 (same window as preset bake-off).

---

## 1. Current subtitle pipeline

```
YouTube video
    │
    ▼
Whisper API (verbose_json, timestamp_granularities=["segment"])
    │  → segments[{ id, start, end, text }]
    ▼
pipeline.sanitize_segments()
    │  → keep id/start/end/text only (no layout logic)
    ▼
transcripts/sanitized_<id>.json
    │
    ▼
generate_srt_for_clip()   ← ONE Whisper segment → ONE SRT cue
    │  → timestamps relative to clip start
    │  → cue body = full segment text on a SINGLE SRT text line
    ▼
temp.srt
    │
    ▼
FFmpeg: crop=ih*9/16:ih,subtitles=temp.srt:force_style='…'
    │  → libass converts SRT → ASS and burns into frames
    │  → soft line wraps when rendered width exceeds available width
    ▼
output MP4 (9:16)
```

**Important:** Layout for short-form captions is **not** designed in Python today. Python emits long single-line SRT cues. Visual line breaks appear at **burn-in time** inside **libass**.

---

## 2. Where line breaks are created

| Stage | Creates visual line breaks? | What it does |
|-------|-----------------------------|--------------|
| Whisper | No (for display) | Emits speech **segments** (~phrase chunks by timing) |
| `sanitize_segments` | No | Strips fields only |
| `generate_srt_for_clip` | **No soft wraps** | Writes each segment as **one** SRT text line (no `\n` inside cue text) |
| SRT file | Structural blank lines only | Separate **cues**, not wraps inside a cue |
| `force_style` (FontSize, MarginL/R) | Indirect | Changes how wide a line can be → affects wrap count |
| **libass / FFmpeg `subtitles` filter** | **Yes — primary** | Soft-wraps long cue text to fit frame width |

So the 5–7 lines on screen are almost always **soft wraps of one long cue**, not five separate SRT cues stacked.

---

## 3. Maximum words per cue

**Application limit: none.**

Effective maximum = whatever Whisper puts in one `segment.text`.

Empirically on the comparison clip (`cut_start=488.520`, `cut_end=546.920`):

| Metric | Observed |
|--------|----------|
| Cues in clip | 12 (12 Whisper segments overlapping the window) |
| Words per cue | **13–21** |
| Chars per cue | **91–100** |

Example cue active at sample frame `t=25s` (only **one** cue active):

```text
21.880 → 27.480
this away so you can focus on the content you want to read. Now a quick note here, Reader is not
```

- Words: **21**  
- Characters: **96**  
- Overlapping cues at t=25: **1**

That single cue’s on-screen text matches the multi-line screenshot stack.

---

## 4. Maximum characters per line

**Application limit: none.**

There is no `max_chars_per_line`, `max_words_per_line`, or wrap helper in the repo.

Effective characters per **visual** line ≈

```text
f(video_width after 9:16 crop, FontSize, Bold, MarginL, MarginR, font metrics)
```

computed inside **libass** at render time. Changing FontSize/margins changes wrap count without any SRT change (confirmed by preset A–E bake-off: same SRT, different stacks).

Rough intuition for this pipeline’s ~608×1080 comparison exports: at FontSize≈24–30, a line often holds only a few words → a 20-word cue becomes ~5–8 visual lines.

---

## 5. What performs wrapping?

| Mechanism | Used today? |
|-----------|-------------|
| Character budget in Python | **No** |
| Word budget in Python | **No** |
| Punctuation-aware phrase breaks in Python | **No** |
| Whisper timing (segment boundaries) | **Yes** — defines **cue** start/end and cue text blob; does **not** insert `\n` |
| ASS/libass soft wrap | **Yes** — creates the visible short lines |

**Verdict:** Wrapping is **ASS/libass**-driven, constrained by FontSize + side margins + frame width. Cue boundaries follow **Whisper segment timing**.

---

## 6. Why the screenshot shows many short lines

Using the comparison sample frame (`t ≈ 25s`):

1. **Only one SRT cue is active** (not 5–7 overlapping cues).  
2. That cue is a **full Whisper segment** (~21 words / ~96 chars) written as **one unbroken SRT line**.  
3. At burn-in, **libass** wraps that long string to the usable width (`frame_width − MarginL − MarginR`) at the current **FontSize**.  
4. With short-form FontSize (≈18–30), usable width fits only a few words per line → the same sentence becomes **5–7 short visual lines**.  
5. With `Alignment=2` (bottom-center), the wrapped block grows **upward**, so a tall stack covers the talking head even though unused horizontal space might *look* available in a still — available width is already consumed by large bold glyphs + outline.

**Not the cause:** missing horizontal space in the abstract; Python inserting `\n`; multiple simultaneous cues at that timestamp.

**Is the cause:** long Whisper segments mapped 1:1 into SRT + large burned-in type + libass soft wrap.

```
Whisper segment (~20 words, one timing window)
        ↓  generate_srt_for_clip (no chunking)
One SRT cue, one text line
        ↓  libass @ FontSize 24–30, Margins
5–7 short on-screen lines (soft wrap)
```

---

## 7. Codebase places that affect subtitle layout

| Location | Role in layout |
|----------|----------------|
| `backend/services/transcriber.py` | Whisper `timestamp_granularities=["segment"]` — segment length/timing |
| `backend/services/pipeline.py` → `sanitize_segments()` | Passes segment text through unchanged |
| `backend/transcripts/sanitized_*.json` | Stored segment source for SRT |
| `backend/services/video_cutter.py` → `generate_srt_for_clip()` | **Cue construction:** 1 segment → 1 cue; single-line text; **no wrap/chunk policy** |
| `backend/services/video_cutter.py` → `_SUBTITLE_FORCE_STYLE` | FontSize / MarginL / MarginR / Alignment — **indirect** wrap width (out of scope to change in this task, but listed for completeness) |
| `backend/services/video_cutter.py` → `cut_clip()` | Invokes FFmpeg `subtitles=` burn-in |
| `backend/services/video_cutter.py` → `process_all_curated_clips()` | Orchestrates SRT gen + cut per clip |
| FFmpeg `subtitles` filter + **libass** | Soft wrapping engine (not in-repo source) |

**Not layout owners:** `curator.py` (clip windows only), frontend (plays burned MP4), validator (duration/overlap only).

Comments in `video_cutter.py` mention preferring “~2-line wraps,” but **no code enforces** max lines/words/chars.

---

## 8. Recommended implementation strategies

*(Design options only — do not implement until Founder/engineering review.)*

### Strategy A — Limit subtitle cues to ≤ N lines (e.g. 3)

**Idea:** After deciding wrap width (fixed char/word budget approximating FontSize), split each long Whisper segment into multiple **sequential** SRT cues (or multi-line cue bodies with `\n`) so at most ~2–3 lines show at once. Advance timing within the parent segment (linear split or word-timed if available).

| Pros | Cons |
|------|------|
| Directly fixes “wall of text” UX | Needs a durable line budget tied to FontSize or it drifts when style changes |
| Easy product rule (“max 3 lines”) | Naive time-slicing can desync slightly from speech |
| Stays in `generate_srt_for_clip` — no FFmpeg redesign | Must handle leftover words and punctuation cleanly |

---

### Strategy B — Dynamic character / width estimation

**Idea:** Estimate chars-per-line from output width (9:16), FontSize, Bold, Outline, MarginL/R (heuristic or measured), then wrap/chunk in Python **before** writing SRT so libass rarely soft-wraps further.

| Pros | Cons |
|------|------|
| Aligns layout with actual burn-in style | Heuristics can be wrong across fonts/OS (Windows vs Railway) |
| One place to tune readability | Couples layout code to style constants |
| Better than fixed “42 chars” magic alone | Still need a line-count cap or cues stay tall |

---

### Strategy C — Phrase-aware wrapping (punctuation + conjunctions)

**Idea:** Split long segments on `.?!`, commas, and light conjunctions (`and`, `but`, `so`, `because`, …) into short caption phrases; optionally merge micro-fragments. Prefer linguistic breaks over mid-phrase wraps.

| Pros | Cons |
|------|------|
| Reads more like creator captions / TikTok pacing | English-centric rules; other languages need work |
| Fewer awkward mid-clause wraps | Punctuation-poor Whisper text is common |
| Complements A or B (phrase split + line cap) | More logic and edge cases than a pure word budget |

---

## Summary for decision-makers

| Question | Answer |
|----------|--------|
| Is stacking a styling bug? | **No** — style works; layout policy is missing |
| Is stacking many overlapping cues? | **Usually no** at the sample frame (1 active cue) |
| Who wraps? | **libass**, after Python emits long single-line cues |
| Max words/chars per cue/line in code? | **None** |
| Best lever without touching colours/FFmpeg graph? | Change **`generate_srt_for_clip`** (chunk / wrap / phrase-split) |

**Suggested direction (non-binding):** combine **C + A** (phrase-aware splits, hard max ~2–3 on-screen lines), optionally informed by **B** so budgets track FontSize. Review before any implementation.

---

*End of investigation. No production code was modified for this report.*
