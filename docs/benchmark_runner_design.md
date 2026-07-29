# Benchmark Runner — Design

> **T-Clipper Operating System (TOS)** — Design for an automated quality benchmark runner.  
> **Status:** Design only. No implementation in this document.  
> **Date:** 2026-07-30  
> **Depends on:** [`benchmark_framework.md`](./benchmark_framework.md)  
> **Related:** `docs/PROJECT.md`, `ai/RULES.md`, `docs/t_score_design.md`, `docs/subtitle_layout_design.md`

---

## Purpose

The **Benchmark Runner** turns the Quality Benchmark Framework into a repeatable CLI (and later CI) workflow:

1. Select fixtures from a registry  
2. Run a defined pipeline profile (layout-only → full engine)  
3. Collect named artifacts (MP4, SRT, stills, JSON)  
4. Compare against a **baseline** golden run  
5. Emit a machine-readable + human **PASS/FAIL** report  

It does **not** replace unit tests. It catches product-level regressions that unit tests miss (caption walls, soft opens, duration gates, render breakage).

---

## Design principles

1. **Deterministic fixtures** — prefer local archived media over live YouTube in CI.  
2. **Profile-based cost control** — `layout` / `cutter` / `full` so every PR need not re-Whisper.  
3. **Baseline diffs** — regressions are vs a committed or stored baseline, not vs “vibes.”  
4. **Secrets stay out** — never log cookies/keys; CI uses dedicated env.  
5. **Human-in-the-loop for editorial** — auto-fail measurable checks; soft-open/ranking can warn until T-Score™ / classifiers exist.  
6. **Minimal blast radius** — runner lives under `benchmarks/`; does not refactor production pipeline modules.

---

## 1. Folder structure

```text
benchmarks/
├── fixtures/
│   ├── manifest.json              # registry of fixture_id → media + expectations
│   ├── media/                     # optional git-lfs / local cache of source MP4s
│   │   ├── EDU-001/
│   │   │   └── source.mp4         # or pointer file if using external cache
│   │   └── POD-001/
│   │       └── source.mp4
│   ├── transcripts/               # optional frozen sanitized_*.json for layout/cutter profiles
│   │   └── EDU-001/
│   │       ├── sanitized.json
│   │       └── curated.json       # frozen windows for cutter/layout-only
│   └── expectations/
│       └── EDU-001/
│           ├── layout_cues.golden.json
│           └── meta.json          # min clips, duration bands, focus flags
│
├── baselines/
│   └── <baseline_id>/             # e.g. v0.9.1 or 20260730_main
│       ├── MANIFEST.json
│       ├── EDU-001/
│       │   ├── clips/
│       │   ├── srt/
│       │   ├── stills/
│       │   └── metrics.json
│       └── SUMMARY.json
│
├── runs/
│   └── YYYYMMDD_HHMMSS_<slug>/
│       ├── config.json            # what was run
│       ├── EDU-001/
│       │   ├── clips/
│       │   ├── srt/
│       │   ├── stills/
│       │   ├── curated.json       # if produced
│       │   └── metrics.json
│       ├── compare/               # vs baseline diffs
│       │   └── EDU-001.diff.json
│       ├── REPORT.md
│       ├── REPORT.json
│       └── SCORECARD.md           # optional human overlay
│
├── runner/                        # future package (design only)
│   ├── README.md
│   ├── cli.py                     # entry: python -m benchmarks.runner …
│   ├── profiles.py
│   ├── compare.py
│   ├── metrics.py
│   └── report.py
│
└── README.md                      # how to run locally
```

### Naming alignment

Artifact filenames inside a run follow [`benchmark_framework.md`](./benchmark_framework.md) §§6–7:

- Stills: `{fixture_id}_{phase}_{clip_tag}_t{seconds}.png`  
- Clips: `{fixture_id}_{phase}_clip{id}_{slug}.mp4`  
- For automated runs, `phase` is typically `after` (current) vs baseline folder as `before`.

---

## 2. Input videos

### 2.1 Fixture sources (priority order)

| Priority | Source | When |
|----------|--------|------|
| 1 | `fixtures/media/<id>/source.mp4` | Local / CI (preferred) |
| 2 | Frozen `youtube_id` via yt-dlp | Local only; flaky for CI |
| 3 | Pre-placed path override in config | Debugging |

### 2.2 `manifest.json` (conceptual schema)

```json
{
  "version": 1,
  "fixtures": [
    {
      "fixture_id": "EDU-001",
      "category": "EDU",
      "title": "Safari tips — Reader",
      "youtube_id": "hXET-58xrqM",
      "media_path": "fixtures/media/EDU-001/source.mp4",
      "transcript_path": "fixtures/transcripts/EDU-001/sanitized.json",
      "curated_path": "fixtures/transcripts/EDU-001/curated.json",
      "focus": ["layout", "full"],
      "min_expected_clips": 2,
      "max_expected_clips": 10,
      "still_timestamps_sec": [3, 25],
      "profiles_allowed": ["layout", "cutter", "full"],
      "notes": "Long Whisper segments; layout stress"
    }
  ]
}
```

### 2.3 Profiles (cost vs coverage)

| Profile | Inputs used | Pipeline stages | Typical use |
|---------|-------------|-----------------|-------------|
| **`layout`** | frozen sanitized + curated windows | layout → SRT only (optional dry metrics) | PR: subtitle layout |
| **`cutter`** | frozen video + curated | layout → SRT → FFmpeg cut | PR: style / MarginV / FontSize |
| **`full`** | video or URL | download (optional) → Whisper → curate → validate → cut | Nightly / release |
| **`smoke`** | 1 short fixture | `cutter` or tiny `full` | CI gate cheap path |

Frozen transcripts/curated JSON make **`layout`** and **`cutter`** reproducible without OpenAI spend.

### 2.4 Secrets / cookies

- Live download profile may need `YOUTUBE_COOKIES_*` locally.  
- CI **default** = offline media + frozen transcripts.  
- Runner must refuse to print cookie contents.

---

## 3. Expected outputs

Per fixture, per run:

| Artifact | Required by profile | Description |
|----------|---------------------|-------------|
| `metrics.json` | all | Machine metrics (see §5) |
| `srt/*.srt` | layout, cutter, full | Burn-in source cues |
| `clips/*.mp4` | cutter, full | Vertical exports |
| `stills/*.png` | cutter, full | Frames at configured `t` |
| `curated.json` | full (optional copy) | Clip windows for audit |
| `layout_cues.json` | layout | Structured cue lines + times |

### 3.1 `metrics.json` (per fixture)

```json
{
  "fixture_id": "EDU-001",
  "profile": "cutter",
  "commit": "abc123",
  "clip_count": 3,
  "clips": [
    {
      "clip_id": 1,
      "duration_sec": 34.2,
      "path": "clips/EDU-001_after_clip1_reader.mp4",
      "first_caption_line": "The next Safari tip",
      "srt_cue_count": 24,
      "max_lines_per_cue": 3,
      "pct_cues_leq_2_lines": 0.82,
      "timing_continuous_within_segments": true,
      "word_integrity_ok": true,
      "aspect_ratio": "9:16"
    }
  ],
  "aggregates": {
    "max_lines_per_cue_global": 3,
    "soft_open_heuristic_hits": 0,
    "duration_violations": 0
  },
  "status": "pass",
  "failures": []
}
```

### 3.2 Baseline outputs

Same shape under `benchmarks/baselines/<baseline_id>/`.  
`SUMMARY.json` lists fixture statuses and overall gate result for that baseline pin.

---

## 4. Automatic comparison workflow

```text
                    ┌─────────────────┐
                    │ Load manifest   │
                    │ + run config    │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ For each fixture│
                    │ run profile     │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ Write artifacts │
                    │ + metrics.json  │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ Load baseline   │
                    │ metrics/arts    │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ Diff engine     │
                    │ (compare.py)    │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ Aggregate PASS/ │
                    │ FAIL + REPORT   │
                    └─────────────────┘
```

### 4.1 Run config (CLI conceptual)

```text
benchmark-run \
  --profile cutter \
  --fixtures EDU-001,POD-001 \
  --baseline v0.9.1 \
  --slug layout_phase1 \
  --still-timestamps 3,25
```

### 4.2 Comparison modes

| Mode | Behavior |
|------|----------|
| **`vs-baseline`** | Diff current run metrics vs `baselines/<id>` (default) |
| **`vs-run`** | Diff two run folders (A/B experiment) |
| **`absolute-only`** | No baseline; apply absolute PASS rules only (first golden) |

### 4.3 What is compared automatically

| Signal | Compare method |
|--------|----------------|
| `max_lines_per_cue` | Absolute threshold + delta vs baseline |
| `pct_cues_leq_2_lines` | Floor threshold; warn if drop &gt; N points vs baseline |
| `word_integrity_ok` | Must stay true |
| `timing_continuous_within_segments` | Must stay true |
| `clip_count` | Band vs expectations; warn if |Δ| large vs baseline |
| `duration_violations` | Must be 0 |
| `first_caption_line` | String diff → **warn** (editorial; not hard fail by default) |
| Still PNGs | Optional perceptual hash / size sanity — **warn** unless `--strict-visual` |
| Style constants fingerprint | Hash of `_SUBTITLE_FORCE_STYLE` recorded in metrics |

### 4.4 Promoting a baseline

```text
benchmark-promote --run YYYYMMDD_... --baseline-id v0.9.2
```

Copies run artifacts into `baselines/` after human PASS sign-off (framework scorecard).

---

## 5. Regression detection

Maps to framework **R1–R12**, automated where possible.

| ID | Detection (automated) | Severity |
|----|----------------------|----------|
| **R1** Caption walls | `max_lines_per_cue > 3` | **FAIL** |
| **R2** Word drop/dup | layout token integrity vs source segment text | **FAIL** |
| **R3** Timing gaps/overlaps | within-segment `end != next.start` (ms) | **FAIL** |
| **R4** Style drift | fingerprint ≠ expected unless `--allow-style-change` | **FAIL** / allow |
| **R5** Chrome / margin | still bottom-band heuristic optional; else manual | **WARN** → later FAIL |
| **R6** Clip count collapse | `clip_count == 0` or below `min_expected_clips` | **FAIL** |
| **R7** Soft-open creep | heuristic on first line lexicon (`um`, `subscribe`, …) | **WARN** (FAIL in `--strict`) |
| **R8** Duration gate | any clip &lt;15s or &gt;60s | **FAIL** |
| **R9** Overlap dups | curated windows IoU &gt; threshold | **FAIL** |
| **R10** Perf/cost | runtime &gt; 2× baseline median | **WARN** |
| **R11** API smoke | optional job HTTP probe | **FAIL** if enabled |
| **R12** Platform | separate matrix jobs (Win/Linux) | per-job FAIL |

### Baseline delta rules (examples)

| Metric | FAIL if |
|--------|---------|
| `max_lines_per_cue` | current &gt; 3 **or** current &gt; baseline + 0 |
| `pct_cues_leq_2_lines` | current &lt; 0.50 **or** drop ≥ 0.25 vs baseline |
| `clip_count` | 0 **or** outside `[min, max]` expectations |
| `word_integrity_ok` | false |

Editorial quality (Q1–Q6) remains **WARN** until classifiers / T-Score™ Stage S2.

---

## 6. Report generation

### 6.1 Outputs

| File | Audience |
|------|----------|
| `REPORT.json` | CI machines |
| `REPORT.md` | Humans / PR comments |
| `compare/*.diff.json` | Per-fixture detail |
| `SCORECARD.md` | Optional manual overlay (framework template) |

### 6.2 `REPORT.md` skeleton

```markdown
# Benchmark Report — <slug>

- Commit: …
- Profile: cutter
- Baseline: v0.9.1
- Result: **FAIL**
- Failed fixtures: EDU-001
- Warnings: POD-001 soft-open heuristic

## Summary table

| Fixture | Status | max_lines | clips | Notes |
|---------|--------|-----------|-------|-------|
| EDU-001 | FAIL   | 5         | 3     | R1 caption wall |
| POD-001 | PASS   | 3         | 5     |  |

## Failures
- EDU-001 R1: max_lines_per_cue=5 > 3

## Artifacts
- runs/…/EDU-001/stills/…
```

### 6.3 `REPORT.json` skeleton

```json
{
  "result": "fail",
  "profile": "cutter",
  "baseline_id": "v0.9.1",
  "commit": "abc123",
  "fixtures": [
    {
      "fixture_id": "EDU-001",
      "status": "fail",
      "failures": [{ "code": "R1", "message": "max_lines_per_cue=5" }],
      "warnings": []
    }
  ],
  "counts": { "pass": 1, "fail": 1, "warn_only": 0 }
}
```

### 6.4 Exit codes

| Code | Meaning |
|------|---------|
| `0` | All fixtures PASS (warnings allowed unless `--strict`) |
| `1` | One or more FAIL |
| `2` | Runner misconfiguration / missing fixtures |
| `3` | Baseline missing when required |

---

## 7. PASS / FAIL rules

### 7.1 Fixture-level

A fixture is **PASS** iff:

1. Pipeline profile completed without uncaught exception.  
2. All **absolute** hard checks pass (R1–R3, R6, R8–R9 as applicable to profile).  
3. No **style fingerprint** mismatch unless explicitly allowed.  
4. Baseline deltas (when enabled) do not violate delta FAIL table.  
5. Required artifacts exist (SRT/clips/stills per profile).

A fixture is **WARN** if only soft checks fail (R7, R10, first-line diffs, visual hash).

A fixture is **FAIL** if any hard check fails.

### 7.2 Run-level

| Result | Rule |
|--------|------|
| **PASS** | Every selected fixture PASS; warnings OK |
| **PASS WITH WARNINGS** | All PASS hard; ≥1 WARN (CI green unless `--strict`) |
| **FAIL** | Any fixture FAIL |

### 7.3 Profile applicability

| Profile | Hard checks enforced |
|---------|----------------------|
| `layout` | R1–R3, word integrity, cue structure |
| `cutter` | layout hard + R4, R8 on outputs, artifact presence |
| `full` | cutter hard + R6, R9, optional R7/R10 |
| `smoke` | subset: one fixture, R1/R8 + render success |

### 7.4 Override flags (design)

- `--strict` — treat WARN as FAIL  
- `--allow-style-change` — skip R4  
- `--update-golden` — rewrite layout golden JSON (local only; never default in CI)  
- `--fixtures` — subset selection  

---

## 8. Future CI integration

### 8.1 Recommended stages

| Workflow | Trigger | Profile | Baseline |
|----------|---------|---------|----------|
| **PR smoke** | pull_request | `smoke` or `layout` on touched paths | pinned `baselines/ci_smoke` |
| **PR cutter** | changes to `video_cutter` / `subtitle_layout` / style | `cutter` + EDU+MIX | pinned |
| **Nightly full** | schedule | `full` min Closed-Beta set | moving `nightly_prev` |
| **Release** | tag / manual | `full` min set + scorecard note | promote new baseline |

### 8.2 Path filters (example)

- `backend/services/subtitle_layout.py` → layout profile  
- `backend/services/video_cutter.py` → cutter profile  
- `backend/services/curator.py` → nightly full (or labeled PR)  

### 8.3 CI constraints

- Use **cached offline media** (Git LFS or downloaded cache action).  
- No live YouTube in default PR CI.  
- Cache Whisper only in nightly with budget caps.  
- Upload run folder as CI artifact on FAIL.  
- Post `REPORT.md` excerpt as PR comment.

### 8.4 GitHub Actions sketch (non-normative)

```yaml
# design only — not an implemented workflow
jobs:
  benchmark-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python / FFmpeg
      - name: Restore media cache
      - name: Run benchmark smoke
        run: python -m benchmarks.runner --profile smoke --baseline ci_smoke
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: benchmark-run
          path: benchmarks/runs/
```

### 8.5 Railway / production

Benchmark runner is **engineering QA**, not a Railway service. Do not run full benchmarks on production dynos.

---

## Implementation phases (future)

| Phase | Deliverable |
|-------|-------------|
| **P0** | Folder scaffolding + manifest + manual script that writes metrics.json |
| **P1** | `layout` profile + golden cue compare + REPORT.md |
| **P2** | `cutter` profile + stills + style fingerprint |
| **P3** | Baseline promote CLI + PR smoke CI |
| **P4** | `full` nightly + soft-open/T-Score™ hooks |

---

## Non-goals

- Replacing unit tests for `subtitle_layout`  
- Automated aesthetic judgment of “good hooks” at P0–P2  
- Vision/gaming benchmarks without ADR  
- Mutating production `output_clips/` as the source of truth (runs are isolated)

---

## Open decisions

1. Commit baselines + small media to git-lfs vs external cache bucket.  
2. Whether PR CI is `layout`-only until media cache is ready.  
3. Who may `benchmark-promote` baselines (maintainers only).  
4. When R7 soft-open becomes hard FAIL.

---

*This design is the automation layer on top of `benchmark_framework.md`. Implement only after Founder approval of profiles and CI cost.*
