# Subtitle Layout Engine — Design

> **T-Clipper** — Design only. No implementation in this document.  
> **Related:** [`subtitle_layout_report.md`](./subtitle_layout_report.md)  
> **Date:** 2026-07-30  
> **Goal:** Control on-screen caption layout in Python so libass soft-wrap no longer produces 5–7-line stacks.

---

## Design principles

1. **Max 3 visual lines** per displayed caption block; **prefer 2**.
2. **Preserve Whisper timing** — do not invent speech times outside a segment’s `[start, end]`.
3. **Split at natural phrase boundaries** — punctuation and light conjunctions before mid-phrase cuts.
4. **Never split proper nouns** — keep multi-word names / titled products on one line when possible.
5. **No orphans** — avoid a last line of a single short word; avoid one-word lines unless the whole cue is one word.
6. **Reading flow** — captions should feel like paced short-form subtitles, not a wrapped paragraph.

**Non-goals (this design):** changing `force_style`, colours, FFmpeg graph, Whisper model, or curation.

---

## 1. Algorithm overview

The engine sits between sanitized Whisper segments and SRT emission:

```
Whisper segment { start, end, text }
        │
        ▼
Normalize text (whitespace, light cleanup)
        │
        ▼
Tokenize → words + attachable punctuation
        │
        ▼
Detect protected spans (proper nouns / titles)
        │
        ▼
Propose phrase cuts (punctuation → conjunctions → length)
        │
        ▼
Pack phrases into caption units (prefer 2 lines, max 3)
        │
        ▼
Allocate time within [segment.start, segment.end]
        │
        ▼
Emit SRT cues (each cue body has explicit \n line breaks)
```

**Key idea:** Stop relying on libass to invent wraps. Emit **short cues** whose text already contains at most 3 lines, sized so further soft-wrap is rare.

**Two output modes (same rules; implementation may pick one):**

| Mode | Behavior |
|------|----------|
| **A — Sequential cues** | Long segment → multiple SRT cues in time order; each cue ≤ 3 lines; times partition the parent segment |
| **B — Multi-line single cue** | One cue keeps full `[start, end]`; body uses `\n` for ≤ 3 lines only if the whole segment fits the line budget |

**Default for T-Clipper MVP:** **Mode A** when a segment needs more than 3 lines of content; **Mode B** when the whole segment packs into ≤ 3 lines. This preserves timing granularity for longer speech while keeping short segments simple.

---

## 2. Step-by-step pipeline

### Step 0 — Inputs / constants

| Name | Intent | Suggested MVP default |
|------|--------|------------------------|
| `MAX_LINES` | Hard cap on visual lines per cue | `3` |
| `PREFERRED_LINES` | Target pack height | `2` |
| `MAX_CHARS_PER_LINE` | Soft width budget (approx FontSize≈24, 9:16) | `28–32` |
| `MAX_WORDS_PER_LINE` | Soft word budget | `5–6` |
| `MIN_WORDS_PER_LINE` | Avoid skinny lines when merging | `2` (when total words ≥ 2) |
| `CONJUNCTIONS` | Prefer split before these | `and, but, or, so, because, when, while, if, that, which, who` |
| `PROTECTED` | Do not break inside | Capitalized multi-word runs, known titles |

`MAX_CHARS_PER_LINE` is a **layout heuristic**, not a promise of pixel-perfect fit. It should later track the active subtitle preset (see report Strategy B) without blocking v1.

### Step 1 — Normalize

- Collapse whitespace.
- Keep terminal punctuation on the preceding word (`Reader.` stays one token with `.`).
- Do not lower-case (needed for proper-noun detection).

### Step 2 — Tokenize

Produce an ordered list of tokens:

```text
"called Reader." → ["called", "Reader."]
```

Internal commas/semicolons may be separate soft-break markers after the preceding word.

### Step 3 — Mark protected spans

A **protected span** is a contiguous token range that must stay on one line if it fits `MAX_CHARS_PER_LINE`; if it does not fit, break only at span edges (never mid-span).

Heuristics (MVP, English-first):

1. Adjacent Capitalized tokens: `Safari`, `Reader`, `New York`, `Premier League`.
2. Patterns like `iPhone 17`, `Galaxy Z`, `ChatGPT` (letter+digit / known brand shapes).
3. Quoted titles if present.
4. Do **not** treat sentence-initial “The/A/An” alone as a proper noun; attach only when followed by a capitalized head (`The Reader` as product name is protected if both are capitalized product-style — prefer protecting `Reader` and allowing `The` to sit with previous line if needed).

### Step 4 — Build phrase candidates

Scan tokens left → right and insert **candidate break points** with priority:

| Priority | Break after… | Example |
|----------|--------------|---------|
| 1 (best) | `.` `?` `!` | `…focus?` ‖ `This is…` |
| 2 | `,` `;` `:` | `…mine,` ‖ `just being…` |
| 3 | Before conjunction | `…tip` ‖ `we're going…` / `…about` ‖ `is called…` |
| 4 (fallback) | Soft length boundary | When a growing line would exceed char/word budget, break at last safe token boundary outside a protected span |

Never place a break:

- Inside a protected span
- After the first word of a 2-word protected name
- Such that the remainder would be a single orphan word if a nearby better break exists

### Step 5 — Pack into lines (prefer 2, max 3)

For each caption unit being built:

1. Fill **line 1** until near `MAX_CHARS_PER_LINE` / `MAX_WORDS_PER_LINE`, ending on the highest-priority break available.
2. Fill **line 2** the same way.
3. If content remains and still fits a third line under budgets → use **line 3**.
4. If content would need a **4th** line → **close the cue** after line 2 or 3 (whichever ends on a stronger phrase break) and start a **new sequential cue** (Mode A) with remaining tokens.
5. **Prefer 2 lines:** if total content fits in 2 lines under budgets, do not spread thinly across 3.
6. **Anti-orphan pass:** if the last line has 1 word and the previous line has ≥ 3 words, pull 1–2 words down from the previous line (unless that breaks a protected span or exceeds line budget by a small grace, e.g. +10% chars).

### Step 6 — Allocate timing (preserve Whisper window)

Parent segment: `[T0, T1]`, duration `D = T1 - T0`.

For Mode A with cues `C1…Ck` containing `w1…wk` words (or character weights):

```text
weight_i = max(1, word_count_i)   # or char_count_i
t_i = T0 + D * (sum(weight_0..i-1) / sum(weights))
cue i occupies [t_i, t_{i+1}] with t_{k+1} = T1
```

Rules:

- Monotonic, non-overlapping (except optional 0–50ms intentional continuity; MVP: abutting is fine).
- **Do not** extend outside `[T0, T1]`.
- Minimum cue duration floor (e.g. 0.7s) — if too many splits, merge adjacent units back until floors are met or accept slightly denser lines (never violate `MAX_LINES`).

Mode B: single cue keeps exact `[T0, T1]`.

### Step 7 — Emit SRT

Each cue:

```srt
N
HH:MM:SS,mmm --> HH:MM:SS,mmm
line one
line two
line three

```

Explicit `\n` between lines. No fourth line. Relative timestamps remain clip-relative as today.

### Step 8 — Libass safety

Even with explicit breaks, oversized protected spans or huge FontSize may still soft-wrap. Mitigation for later implementation (not style redesign now): keep `MAX_CHARS_PER_LINE` conservative relative to the active preset; optionally set ASS `WrapStyle` when implementation lands. Out of scope for this design’s product rules.

---

## 3. Pseudo-code

```text
function layout_segment(segment):
    tokens = tokenize(normalize(segment.text))
    if tokens is empty:
        return []

    protected = mark_protected_spans(tokens)
    phrases = split_into_phrases(tokens, protected)
        # uses punctuation → conjunction → length fallback
        # never cuts inside protected

    cues = []
    current_lines = []      # list of strings, length 0..3
    current_tokens = []     # tokens assigned to current cue

    for phrase in phrases:
        trial = pack(current_lines, phrase, MAX_LINES, PREFERRED_LINES,
                     MAX_CHARS_PER_LINE, MAX_WORDS_PER_LINE, protected)
        if trial.ok:
            current_lines = trial.lines
            current_tokens.append(phrase)
        else:
            # close current cue if it has content
            if current_lines:
                current_lines = fix_orphans(current_lines, protected)
                cues.append(CaptionUnit(lines=current_lines, tokens=current_tokens))
            current_lines, current_tokens = pack_new(phrase, ...)
            # if phrase alone needs > MAX_LINES, hard-split phrase by length
            # at protected-safe boundaries into multiple units

    if current_lines:
        current_lines = fix_orphans(current_lines, protected)
        cues.append(CaptionUnit(lines=current_lines, tokens=current_tokens))

    return allocate_time(cues, segment.start, segment.end)


function pack(lines, phrase, ...):
    # Prefer filling 2 lines; allow 3rd only if needed and within budgets
    # Reject if would require 4th line
    ...


function fix_orphans(lines, protected):
    if len(lines) >= 2 and word_count(lines[-1]) == 1:
        attempt move 1-2 words from lines[-2] → lines[-1]
        unless protected span would split or budgets explode
    if len(lines) >= 2 and word_count(lines[-1]) == 1 and cannot fix:
        merge last two lines if merged line within 1.15 * MAX_CHARS_PER_LINE
        else leave (rare)
    return lines


function allocate_time(units, t0, t1):
    weights = [max(1, word_count(u)) for u in units]
    # proportional slices of [t0, t1]; enforce min duration by merging if needed
    return list of {start, end, text_with_newlines}


function generate_srt_for_clip(...):  # future integration point
    for segment overlapping clip window:
        for cue in layout_segment(segment):
            emit SRT cue with clip-relative times
```

---

## 4. Edge cases

| Case | Policy |
|------|--------|
| Segment shorter than `MAX_CHARS_PER_LINE` | One line (or 2 if a strong mid break exists and prefer readability); do not force 2 lines |
| Exactly fits 2 lines | Use 2; do not pad to 3 |
| Needs 4+ lines of content | Sequential cues (Mode A); each ≤ 3 lines |
| Protected span longer than one line | Keep on its own line; if still too long, break at span **edges** only (never mid-token name); allow temporary soft excess ≤ grace |
| All-caps shouting | Treat as normal words unless known title list matches |
| No punctuation / no conjunctions | Length-based breaks at word boundaries; still enforce max lines via sequential cues |
| Single-word segment | One line, one cue; full `[start, end]` |
| Leading leftover from clip pad (`this away so…`) | Layout still applies; do not “fix” incomplete grammar from windowing |
| Numbers / versions (`iPhone 17 Pro`) | Protect as one span |
| Apostrophes (`we're`, `doesn't`) | Single token; never split |
| Em-dash / ellipsis | Soft break after if present |
| Very short segment duration + many forced cues | Merge units until min duration satisfied; prefer fewer cues over violating min read time |
| Non-English | MVP English heuristics; fallback = length-only wrap + max lines; i18n later |
| Empty / whitespace segment | Skip |
| Cue would end with orphan (“a”, “the”, “to”) | Pull next word onto that line or push orphan to next line with following words |

---

## 5. Examples

Convention:

```text
Input:  <single Whisper segment text>
Output: <lines as they should appear in one cue>
        --- next cue (if Mode A split) ---
```

Times omitted in examples; implementation allocates proportionally inside the parent segment.

---

### Example 1 — Required sample (prefer 3 balanced lines)

**Input**

```text
The next Safari tip we're going to talk about is called Reader.
```

**Output**

```text
The next Safari tip
we're going to talk about
is called Reader.
```

Notes: Break before `we're` and before `is`; keep `Reader.` intact; 3 lines OK; no orphan.

---

### Example 2 — Prefer 2 lines when content is shorter

**Input**

```text
Have you ever been on a website full of ads?
```

**Output**

```text
Have you ever been
on a website full of ads?
```

---

### Example 3 — Sentence boundary → sequential cues

**Input**

```text
Impossible to focus? This is personally a pet peeve of mine.
```

**Output (cue 1)**

```text
Impossible to focus?
```

**Output (cue 2)**

```text
This is personally
a pet peeve of mine.
```

Notes: Hard split after `?`; second sentence packs to 2 lines.

---

### Example 4 — Avoid single-word last line

**Input**

```text
The Reader quickly strips all of this away.
```

**Bad**

```text
The Reader quickly strips all of
this away.
```
*(acceptable)*  
vs  

```text
The Reader quickly strips all of this
away.
```
*(reject — orphan `away.`)*

**Output**

```text
The Reader quickly strips
all of this away.
```

---

### Example 5 — Do not split proper noun / product name

**Input**

```text
Today we're reviewing the iPhone 17 Pro camera.
```

**Bad**

```text
Today we're reviewing the iPhone
17 Pro camera.
```

**Output**

```text
Today we're reviewing
the iPhone 17 Pro camera.
```

---

### Example 6 — Conjunction break

**Input**

```text
You can customize this to show exactly what you want.
```

**Output**

```text
You can customize this
to show exactly what you want.
```

---

### Example 7 — Long segment → two cues, max 3 lines each

**Input**

```text
this away so you can focus on the content you want to read. Now a quick note here, Reader is not
```

**Output (cue 1)**

```text
this away so you can focus
on the content you want to read.
```

**Output (cue 2)**

```text
Now a quick note here,
Reader is not
```

Notes: Split on `.`; keep `Reader` with following words; no 5–7-line stack.

---

### Example 8 — Comma phrase

**Input**

```text
Just being flooded with all that stuff, making it hard to read.
```

**Output**

```text
Just being flooded
with all that stuff,
making it hard to read.
```

---

### Example 9 — Short segment stays one line

**Input**

```text
Show Reader.
```

**Output**

```text
Show Reader.
```

---

### Example 10 — Multi-word place / competition name

**Input**

```text
Every stadium's best goal from the Premier League this season.
```

**Output**

```text
Every stadium's best goal
from the Premier League
this season.
```

Notes: `Premier League` protected on one line.

---

### Example 11 — Apostrophe token + no orphan

**Input**

```text
It doesn't usually work on the home page of a website.
```

**Output**

```text
It doesn't usually work
on the home page
of a website.
```

---

### Example 12 — Prefer 2 over stretched 3

**Input**

```text
Pin these websites for easy access later.
```

**Bad (over-split)**

```text
Pin these
websites for
easy access later.
```

**Output**

```text
Pin these websites
for easy access later.
```

---

### Example 13 — Question + continuation inside one segment

**Input**

```text
Why does this matter? Because your audience watches muted.
```

**Output (cue 1)**

```text
Why does this matter?
```

**Output (cue 2)**

```text
Because your audience
watches muted.
```

---

## Integration sketch (future implementation — not now)

| Change | Location |
|--------|----------|
| New pure functions | e.g. `backend/services/subtitle_layout.py` (name TBD) |
| Call site | `generate_srt_for_clip()` maps each overlapping segment through `layout_segment` before writing SRT |
| Untouched | Whisper, curator, `force_style`, FFmpeg filter graph |
| Tests | Golden strings for Examples 1–13; timing monotonicity; never > 3 lines per cue |

---

## Success criteria

A layout is correct when:

1. Every emitted cue has **≤ 3** lines.  
2. Most conversational cues use **2** lines when content allows.  
3. All cue times lie within the parent Whisper `[start, end]`.  
4. Protected spans are not broken mid-name.  
5. No intentional single-word final line when a local redistribute fixes it.  
6. Re-rendering the comparison clip no longer shows 5–7-line walls for the former long segments.

---

## Open decisions (Founder / eng before coding)

1. Exact `MAX_CHARS_PER_LINE` for the chosen subtitle preset.  
2. Min cue duration when Mode A splits aggressively.  
3. Whether product titles like `The Reader` are always protected as two-token spans.  
4. Non-English v1 behavior (length-only vs skip layout).

---

*End of design. No code was written or modified.*
