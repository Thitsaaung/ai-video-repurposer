# Quality Benchmark Framework

> **T-Clipper Operating System (TOS)** — How we measure clip quality, catch regressions, and compare before/after changes.  
> **Status:** Documentation only. Not an automated test suite yet.  
> **Date:** 2026-07-30  
> **Related:** `docs/PROJECT.md`, `docs/t_score_design.md`, `docs/subtitle_layout_design.md`, `ai/RULES.md`

---

## Purpose

T-Clipper ships burned-in vertical clips. Small changes to curation, layout, styling, or timing can silently hurt readability or ranking.

This framework defines:

- What videos we always re-test  
- What “good” means (quality + regression)  
- How we name artifacts  
- How we score and compare runs  

**Rules of use**

1. Run the relevant checklist after any change that touches clipping, captions, scoring, or render.  
2. Prefer the same source URLs / IDs across runs so before/after is fair.  
3. Store artifacts under a dated run folder (see naming).  
4. Do not claim “quality improved” without a filled scoring template.

---

## 1. Benchmark dataset categories

Each category needs **≥2 fixed fixtures** (stable YouTube IDs or archived local downloads). Prefer speech-heavy ICP content.

| ID | Category | Why it exists | Fixture criteria |
|----|----------|---------------|------------------|
| **POD** | Podcast / interview | Core ICP; long turns, natural speech | 10–40 min; clear host/guest; English first |
| **EDU** | Education / explainer | Tip density; numbered steps | Concrete “how-to” moments; minimal music bed |
| **COM** | Commentary / opinion | Hooks, stakes, punchlines | Strong cold-opens; opinionated speech |
| **SPO** | Sports commentary | Fast speech; names; excitement | Play-by-play or studio desk; not silent highlights |
| **NEW** | News / talk | Formal cadence; proper nouns | Anchors, interviews; clean audio |
| **MIX** | Edge / stress | Break the pipeline safely | Very long mono segments; heavy ads talk; soft opens; non-English *optional later* |

### Fixture registry (maintain in-repo later)

Suggested path (when populated): `benchmarks/fixtures/manifest.json`

Per fixture fields:

| Field | Description |
|-------|-------------|
| `fixture_id` | Stable id, e.g. `POD-001` |
| `category` | One of POD / EDU / COM / SPO / NEW / MIX |
| `youtube_id` | Canonical id |
| `title` | Human label |
| `notes` | Known hard parts (long Whisper lines, soft open, etc.) |
| `min_expected_clips` | Soft expectation after curation |
| `focus` | `layout` · `hook` · `duration` · `full` |

### Minimum Closed-Beta set

Before calling a release “quality-checked,” run at least:

- 1× POD  
- 1× EDU  
- 1× COM  
- 1× MIX (long-segment stress for subtitles)

---

## 2. Quality checklist

Use on a **fresh** export (not a stale MP4). Check on phone-width viewport when possible.

### A. Editorial / clip selection

| # | Check | Pass if |
|---|-------|---------|
| Q1 | Cold open | First 1–3s are a concrete spoken line (not intro/CTA) |
| Q2 | Completeness | Thought has setup + payoff inside the window |
| Q3 | Duration | Clip in 15–60s; prefer ~20–45s for speech tips |
| Q4 | Hook clarity | A stranger understands the topic from the first caption block |
| Q5 | No filler lead | Does not start on “um”, “so yeah”, subscribe asks |
| Q6 | Ranking sanity | Best clip feels like top of list (when T-Score™ exists) |

### B. Subtitles / layout

| # | Check | Pass if |
|---|-------|---------|
| Q7 | Max lines | On-screen stack rarely exceeds **3** lines for a single cue |
| Q8 | Prefer 2 | Most cues are **1–2** lines |
| Q9 | Phrase breaks | Breaks feel natural (not mid proper noun) |
| Q10 | Timing | Captions track speech; no obvious early/late drift |
| Q11 | Continuity | No visible flicker gaps between sequential cues |
| Q12 | Integrity | No missing / duplicated words vs speech (spot-check) |

### C. Packaging / burn-in

| # | Check | Pass if |
|---|-------|---------|
| Q13 | Aspect | True 9:16; subject reasonably framed |
| Q14 | Style | FontSize / outline readable on dark and light backgrounds |
| Q15 | Chrome clearance | Bottom captions clear typical Shorts/TikTok UI (given current MarginV) |
| Q16 | Face tradeoff | Captions do not permanently cover eyes for the whole clip |
| Q17 | Audio sync | A/V aligned; no obvious cut glitches at start/end |

### D. Product / ops

| # | Check | Pass if |
|---|-------|---------|
| Q18 | Determinism | Same URL + code → same cue text (layout) / stable clip count band |
| Q19 | Job UX | Status → complete; clips preview + download |
| Q20 | No secrets | Logs do not print cookies / API keys |

**Pass bar (single fixture):** all **Must** items Q1–Q4, Q7–Q8, Q13–Q15, Q18–Q19. Others are **Should**.

---

## 3. Regression checklist

Run when changing: curator prompts, validator, subtitle layout, `force_style`, padding, cutter, or scoring.

| # | Regression risk | How to detect | Block release if |
|---|-----------------|---------------|------------------|
| R1 | 6-line caption walls return | Compare mid-clip stills to prior run | Any fixture shows ≥6-line single-cue stacks as default |
| R2 | Layout drops/dupes words | Diff cue text vs Whisper segment tokens | Word integrity fails on golden samples |
| R3 | Timing gaps/overlaps | Inspect SRT: `end(prev)` vs `start(next)` within segment | Systematic gaps/overlaps inside a segment |
| R4 | FontSize / style drift | Diff `_SUBTITLE_FORCE_STYLE` + stills | Unintended style constant change |
| R5 | MarginV / chrome regression | Margin bake-off stills or new stills | Captions under UI or covering eyes constantly |
| R6 | Clip count collapse | Compare clip N vs prior | 0 clips or only filler |
| R7 | Soft-open creep | First-line audit | Majority of top clips start soft |
| R8 | Duration gate break | Check &lt;15s or &gt;60s outputs | Invalid durations ship |
| R9 | Overlap duplicates | Two near-identical windows | Validator overlap regression |
| R10 | Perf / cost blowup | Job time + API usage notes | &gt;2× latency or token cost without approval |
| R11 | API contract break | Frontend smoke | Preview/download/job schema broken |
| R12 | Windows/Railway path | Burn-in on both if possible | Captions missing only on one OS |

**Sign-off:** reviewer initials + date on the run’s `SCORECARD.md`.

---

## 4. Acceptance criteria

### Change-type gates

| Change type | Required fixtures | Required artifacts | Accept when |
|-------------|-------------------|--------------------|-------------|
| Subtitle layout | EDU + MIX | SRT + 2 stills/fixture + scorecard | Q7–Q12 + R1–R3 pass |
| Subtitle style only | EDU + COM | stills @ fixed `t` + scorecard | Q14–Q16 + R4–R5 pass |
| Curation / prompts | POD + EDU + COM | clip list + first-line quotes + scorecard | Q1–Q6 + R6–R9 pass |
| Scoring (T-Score™) | POD + EDU + COM | score dumps + rank order notes | Ranking matches human top-3 on ≥2/3 fixtures |
| Full pipeline / release | Min Closed-Beta set | full pack (below) | All Must quality checks + no Block regressions |

### Release acceptance (Closed Beta)

1. Min dataset set executed on the release commit.  
2. Scorecards filled (section 8).  
3. Before/After attached when the change is intentional UX/quality work.  
4. No **Block** items on regression checklist.  
5. Known limitations listed (honest), not hidden.

---

## 5. Before / After comparison format

Each quality experiment gets a run folder:

```text
benchmarks/runs/YYYYMMDD_<short_slug>/
  MANIFEST.md
  SCORECARD.md
  before/
  after/
  notes.md
```

### `MANIFEST.md` template

```markdown
# Run: YYYYMMDD_<slug>

- Commit: <sha>
- Author: <name>
- Change summary: <1–2 sentences>
- Fixtures: POD-001, EDU-001, ...
- Pipeline: engine | cutter-only | layout-only
```

### `notes.md` template

```markdown
## Hypothesis
## What changed
## What stayed constant (URL, window, style except X)
## Observed deltas
## Decision / follow-ups
```

### Side-by-side table (in SCORECARD or notes)

| Fixture | Metric | Before | After | Delta | Notes |
|---------|--------|--------|-------|-------|-------|
| EDU-001 | Max on-screen lines @ t=25s | 6 | 2 | −4 | Layout Phase 1 |
| EDU-001 | Top clip first line | "So yeah…" | "The Reader…" | better | Prompt |
| EDU-001 | T-Score™ (when live) | — | 78 | — | |

### Visual compare rules

- Same `fixture_id`, same source media, same clip window when testing layout/style.  
- Same frame timestamp `t` for stills (default **t=25s** into the export, or **t=3s** for hook checks).  
- Prefer muted scrub of MP4s, not stills alone.  
- Label which is before/after in filenames (section 6).

---

## 6. Screenshot naming

Pattern:

```text
{fixture_id}_{phase}_{clip_tag}_t{seconds}[_{label}].png
```

| Token | Meaning | Examples |
|-------|---------|----------|
| `fixture_id` | Registry id | `EDU-001` |
| `phase` | `before` · `after` · `baseline` | `after` |
| `clip_tag` | Clip identity | `c1`, `best`, `hook` |
| `t{seconds}` | Frame time into export | `t25`, `t03` |
| `label` | Optional experiment knob | `mv58`, `fs22`, `layout` |

Examples:

```text
EDU-001_before_c1_t25.png
EDU-001_after_c1_t25.png
EDU-001_after_c1_t25_fs22.png
POD-002_baseline_best_t03_hook.png
```

Store under the run’s `before/` or `after/` folder (phase also in filename for portability).

---

## 7. Clip naming

### Pipeline outputs (existing product)

Keep cutter convention:

```text
clip_{clip_id}_{sanitized_title}.mp4
```

Do not rename product outputs ad hoc in `output_clips/` for benchmarks.

### Benchmark copies

When copying into a run folder, use:

```text
{fixture_id}_{phase}_clip{clip_id}_{slug}.mp4
```

Examples:

```text
EDU-001_before_clip1_reader_feature.mp4
EDU-001_after_clip1_reader_feature.mp4
COM-001_after_clip3_cold_open.mp4
```

### SRT / JSON companions (optional)

```text
{fixture_id}_{phase}_clip{clip_id}.srt
{fixture_id}_{phase}_curated.json
```

### Experiment packs (comparison/)

For A/B style packs already in `comparison/`, prefer explicit knob names:

```text
margin58.mp4 / margin58.png
fontsize22.mp4 / fontsize22.png
preset_c.mp4
```

New experiments should follow `{knob}{value}.mp4` plus matching `.png` at the same `t`.

---

## 8. Scoring template

Copy into each run’s `SCORECARD.md`.

```markdown
# Scorecard — YYYYMMDD_<slug>

Commit: 
Reviewer: 
Date: 

## Summary
- Verdict: Pass / Pass-with-notes / Fail
- Blockers:
- Follow-ups:

## Fixture results

### Fixture: <POD-001>
Category: POD
Source: <youtube_id or file>

| Check | Must/Should | Result (Pass/Fail/N/A) | Notes |
|-------|-------------|------------------------|-------|
| Q1 Cold open | Must |  |  |
| Q2 Completeness | Must |  |  |
| Q3 Duration | Must |  |  |
| Q4 Hook clarity | Must |  |  |
| Q7 Max ≤3 lines | Must |  |  |
| Q8 Prefer 2 lines | Must |  |  |
| Q13 9:16 | Must |  |  |
| Q14 Readable style | Must |  |  |
| Q15 Chrome clearance | Must |  |  |
| Q18 Determinism | Must |  |  |
| Q19 Job UX | Must |  |  |
| Q5–Q6, Q9–Q12, Q16–Q17, Q20 | Should |  |  |

Clips reviewed: 
Best first line: 
Worst issue: 

### Fixture: <EDU-001>
… (repeat)

## Regression (R1–R12)

| ID | Result | Notes |
|----|--------|-------|
| R1 |  |  |
| R2 |  |  |
| … |  |  |

## Before/After (if applicable)

| Fixture | Metric | Before | After | Better? |
|---------|--------|--------|-------|---------|
|  |  |  |  |  |

## Artifacts
- Stills:
- MP4s:
- SRT/JSON:

## Sign-off
Reviewer: ____  Date: ____
```

### Optional numeric rubric (0–5 per fixture)

| Dimension | 0 | 3 | 5 |
|-----------|---|---|---|
| Hook | Soft/CTA | Adequate | Cold + concrete |
| Completeness | Cut-off | Mostly full | Clean arc |
| Captions | Unreadable / 6+ lines | OK | ≤3, natural breaks |
| Packaging | Broken | Usable | Chrome-safe + framed |
| Trust | Would never post | Maybe | Post first |

**Fixture total:** sum (max 25). Record in scorecard notes. This rubric complements T-Score™; it does not replace it when T-Score™ ships.

---

## Workflow (quick)

1. Create `benchmarks/runs/YYYYMMDD_<slug>/`.  
2. Select fixtures from section 1.  
3. Export **before** (if comparing) → name per sections 6–7.  
4. Apply change; export **after**.  
5. Fill quality + regression checklists.  
6. Complete scoring template; verdict Pass / Fail.  
7. Link run folder in PR description.

---

## Non-goals

- Not a substitute for unit tests (layout unit tests remain mandatory for layout changes).  
- Not full creator analytics (views/retention) — that is T-Score™ Stage S5.  
- Not vision/gaming QA until an ADR expands scope.

---

*This framework is the quality contract for T-Clipper clip output. Update it when categories, naming, or acceptance bars change.*
