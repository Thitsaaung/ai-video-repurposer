# AI Curation — How Clip Selection Works

This document explains the **current** AI clip-selection path in AI Video Repurposer.

This document describes the CURRENT implemented AI behavior.

Future ideas belong in ROADMAP.md until they are approved.

It is based on the implemented pipeline under `backend/services/`. It does not describe planned vision models, category routers, or other unbuilt features.

Related decisions: [`DECISIONS.md`](./DECISIONS.md) (`DEC-003`, `DEC-004`, `DEC-005`, `DEC-007`).

---

## Pipeline overview

End-to-end orchestration: `backend/services/engine.py` → `process_video_to_clips(url)`.

```
YouTube URL
    │
    ▼
[1] yt-dlp download          → backend/downloads/
    │
    ▼
[2] Whisper transcription    → sanitized transcript JSON
    │
    ▼
[3] LLM curator              → candidate clip windows
    │                           (+ boundary snap + short-clip extend)
    ▼
[4] Clip validator           → filtered / ranked clips
    │                           → backend/transcripts/curated_<id>.json
    ▼
[5] FFmpeg rendering         → backend/output_clips/*.mp4
                                (trim, optional editorial pad, 9:16 crop, captions)
```

HTTP jobs (`POST /api/process-video`) call the same engine via `backend/app/services/video_processor.py`. The AI path itself lives entirely in `services/`.

---

## Whisper

**Module:** `backend/services/transcriber.py` (invoked through `pipeline.py`)

**Role:** Turn speech into timestamped text the curator can reason over.

**Behavior (current):**

1. Extract compressed audio with FFmpeg (mono, 16 kHz, 64 kbps MP3) to stay under Whisper’s size limit.
2. Call OpenAI Whisper (`whisper-1`) with `verbose_json` to obtain segments (`id`, `start`, `end`, `text`).
3. Reject audio that is still too large after compression (~24 MB gate; chunking is not implemented).
4. Pipeline sanitizes segments and writes `backend/transcripts/sanitized_<video_id>.json`.

Whisper is the only speech model in the path. Clip times later snap to these segment boundaries.

---

## Curator

**Module:** `backend/services/curator.py`

**Role:** Ask an LLM to pick engaging short-form windows from a **compact transcript**, then apply deterministic timestamp repair.

### Inputs

- Sanitized transcript JSON
- Compressed to plain lines: `[start - end] spoken text` (`compress_transcript`) to reduce token / TPM pressure

### LLM providers

| Preference | Model |
|------------|--------|
| If `ANTHROPIC_API_KEY` is set | Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) |
| Else if `OPENAI_API_KEY` is set | OpenAI `gpt-4o-mini` (structured parse into `CurationResponse`) |

Temperature is `0.3`. Schema fields per clip: `clip_id`, `title`, `hook`, `start_time`, `end_time`, `virality_score` (1–100), `duration`, plus `overall_summary`.

### Post-LLM (deterministic, no LLM)

1. **Snap** `start_time` / `end_time` to nearest transcript segment boundaries.
2. **Extend** clips shorter than 15s using whole segments only:
   - Prefer extend **forward** to later segment ends
   - If needed, extend **backward** to earlier segment starts
   - Never invent mid-segment timestamps; preserve title/hook/score
3. Hand survivors to the validator.

### Output

`backend/transcripts/curated_<video_id>.json` including clips, `overall_summary`, `video_id`, `source_transcript`, and `debug_stats` (counts for LLM / extended / rejected / final).

---

## Validator

**Module:** `backend/services/clip_validator.py`

**Role:** Deterministic cleanup before persistence. No network calls.

**Rules:**

1. Valid bounds: `start_time >= 0` and `start_time < end_time`
2. Duration must be **15–60 seconds**
3. If two clips share **>50%** of the shorter span, keep the higher `virality_score`
4. Sort by score descending; keep top **`max_clips=10`**; renumber `clip_id` from 1

The validator does **not** judge editorial quality. That is the curator’s job. The validator enforces mechanical constraints and ranking.

---

## FFmpeg

**Module:** `backend/services/video_cutter.py`

**Role:** Render final Shorts/Reels files from curated windows (not AI selection).

**Per clip (current):**

1. Resolve sanitized transcript for caption text (`source_transcript` on curated JSON).
2. Optionally apply **editorial padding** at cut time only (`CLIP_PAD_START_SECONDS` / `CLIP_PAD_END_SECONDS` from settings; defaults 3s / 1s). Curated JSON timestamps on disk are not rewritten.
3. Build relative SRT cues for the (padded) window.
4. FFmpeg: seek/trim → center-crop **9:16** (`crop=ih*9/16:ih`) → burn subtitles → `libx264` / `aac` MP4 under `backend/output_clips/`.

Engine always passes **exact** `video_path` and `curated_json_path` from the same run (no “pick latest file” in the engine path).

---

## Current prompt philosophy

Source of truth: `SYSTEM_PROMPT` and `_build_user_prompt()` in `backend/services/curator.py`.

**Core ideas:**

- **Quality drives count.** Prefer excellent standalone clips. Typically 5–8; up to 10 only when clearly warranted. Never pad with weak fillers.
- **Cold open.** First 1–3 seconds must work with zero prior context.
- **Complete micro-story.** Prefer 20–45s complete thoughts over bare 15s snips (still within 15–60s).
- **Start on the punchy line**, not setup filler.
- **Hard reject list:** intros/outros, CTAs, transitions, music/silence/repeated filler, mid-sentence starts, incomplete thoughts, context-dependent moments.
- **Light content cues** (judgment only — not category routing): podcast/interview, sports commentary, educational.
- **`virality_score` discrimination:** most solid clips 40–75; strong 76–84; exceptional 85–100. Do not inflate.
- **`hook`:** brief paraphrase of the actual opening spoken line — not marketing ad copy.

`max_clips=10` in the validator remains unchanged; under-generation is prompt-led (see `DEC-004`).

---

## Current limitations

These are real limitations of the **current** system:

| Limitation | Effect |
|------------|--------|
| Transcript-only selection | Visual-only moments (silent gameplay, B-roll punchlines) are missed |
| Whisper quality | Noisy, non-English, or music-heavy audio yields weak or garbled segments; curator may still invent meaning from bad text |
| LLM short windows | Models often propose short spans; deterministic extension pads with neighboring speech, which can dilute the moment |
| Center 9:16 crop | No face/subject tracking; framing can miss the speaker |
| Score is model-assigned | `virality_score` is useful for relative ranking after filters; it is not a verified viral predictor and is not shown as a product “fake viral score” feature |
| Overlap filter | Dense or extended windows can drop otherwise good clips |
| Whisper size limit | Very long videos can exceed the compressed audio budget; chunking is not implemented |
| In-memory jobs | HTTP job state is process-local (API concern, not curation quality) |

---

## Why transcript-first

1. **Launch verticals are speech-heavy** — podcasts, interviews, sports commentary, education.
2. **Already production-proven** — Whisper + LLM curation + deterministic repair is deployed and working.
3. **Cost and complexity** — vision models would add latency, spend, and new failure modes without changing the need for transcript timing for captions.
4. **Decoupled pipeline** — selection stays in `curator.py`; render stays in `video_cutter.py`.

See `DEC-007`.

---

## Why gaming is currently limited

Gameplay highlights are often **visual**: kills, movement, UI, silent reactions. Commentary may lag, be sparse, or not describe the exact highlight.

Because selection uses speech timestamps only:

- Strong shout-cast moments can still work
- Pure visual plays without clear speech usually will not

Gaming is **not** a launch priority. Do not “fix gaming” with architecture changes (vision, routers) without a separate product decision (`DEC-005`).

---

## Sprint #4 prompt engineering strategy

**Focus:** Improve clip selection quality inside the existing curator. Not infrastructure. Not API redesign.

**Approved approach:**

1. Rewrite curator prompts so the model prefers cold opens, complete moments, and filler rejection.
2. Let quality drive clip count (typically 5–8; up to 10).
3. Keep `max_clips=10` in the validator — no hard code cap of 8.
4. Preserve snap / extend / validate / cut behavior.

**Explicitly avoided in this strategy:**

- Fake viral score product surfaces
- Vision models
- Category routing architecture
- Major pipeline refactors

**Success signals (qualitative):**

- Lower reliance on extension (more LLM windows already ≥ ~20s)
- Fewer intro/outro/CTA clips
- Clip counts that shrink on thin content instead of always filling to 9–10 mediocre clips
- Opening line of each clip works without prior context

---

## Future improvements

The following are **possible** next steps discussed as product/engineering direction. They are **not** implemented unless noted elsewhere in code:

- Further prompt iteration from A/B re-curation of existing `sanitized_*.json` files
- Tune overlap threshold or extension behavior only if evidence shows prompt changes are insufficient
- Whisper chunking for very long audio
- Subject-aware vertical reframing (face/speaker crop)
- Customizable caption styling
- Automated tests for validator / extension / path hand-off
- Durable job queue (ops), separate from curation quality
- Vision or gaming-specific understanding — only after an explicit product decision

Do not treat this list as a commitment or as current capabilities.
