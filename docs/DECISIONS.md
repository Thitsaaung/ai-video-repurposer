## DEC-000 — Product Mission

Decision

Build an AI Video Repurposer that saves creators time by automatically producing high-quality vertical clips from long-form videos.

Context

This decision defines the purpose of the entire project.

Reasoning

Every future engineering decision should support this mission.

Consequences

Avoid features that do not directly improve creator productivity or clip quality.

# Engineering & Product Decisions

This file records important decisions that shape the AI Video Repurposer product.

Format for each entry:

| Field | Meaning |
|-------|---------|
| **ID** | Stable identifier (`DEC-NNN`) |
| **Date** | When the decision was adopted or documented |
| **Status** | `Accepted` · `Superseded` · `Proposed` |
| **Decision** | What we chose |
| **Context** | Why the decision came up |
| **Reasoning** | Why this option won |
| **Consequences** | What we accept as a result |

Do not invent features here. Decisions must reflect the current product and codebase.

---

## DEC-001 — Preserve backend architecture

| | |
|---|---|
| **ID** | DEC-001 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

Do not redesign the backend architecture. Keep the existing split:

- `backend/services/` — offline processing pipeline (download → transcribe → curate → cut)
- `backend/app/` — FastAPI HTTP layer (jobs, media)
- Pipeline orchestration via `engine.process_video_to_clips`

**Context**

The processing engine and FastAPI job API are stable and deployed. New work (especially AI quality) must not trigger structural rewrites.

**Reasoning**

Architecture changes have high blast radius and low customer value when the pipeline already works end-to-end. Improvements should land inside existing modules.

**Consequences**

- No new processing frameworks, queues, or service splits without explicit founder/CTO approval
- Feature work prefers prompt, config, or localized logic changes over new layers
- Refactors that “clean up” working systems are out of scope unless they fix a proven defect

---

## DEC-002 — Backend API frozen before launch

| | |
|---|---|
| **ID** | DEC-002 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

Treat the current FastAPI surface as stable for launch:

- `POST /api/process-video`
- `GET /api/jobs/{job_id}`
- Clip media under `/media/clips`
- Download route for clip files

Do not break request/response shapes or job polling contracts without an explicit versioning plan.

**Context**

The Next.js frontend polls jobs and previews/downloads clips against this API. Backend deployment on Railway is already in use.

**Reasoning**

API churn breaks the frontend and any external callers. Launch readiness depends on a predictable contract more than on elegant redesigns.

**Consequences**

- Additive, backward-compatible changes only (unless a breaking change is explicitly approved)
- Job payload public shape continues to hide absolute filesystem paths
- Background processing remains FastAPI `BackgroundTasks` + in-memory job store until a durable worker decision is made separately

---

## DEC-003 — Prompt-first AI quality improvements

| | |
|---|---|
| **ID** | DEC-003 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

Improve clip selection quality primarily by changing curator prompts (`SYSTEM_PROMPT` and user prompt in `backend/services/curator.py`), not by adding vision models, category routers, or new AI services.

**Context**

Sprint #4 focus is AI quality. Clip selection is transcript-based LLM curation followed by deterministic snap/extend/validate.

**Reasoning**

Prompt changes have the highest impact-to-risk ratio. Boundary snap, duration extension, and validation already work; selection quality is mostly brief quality.

**Consequences**

- Sprint #4 implementation stays inside prompt text unless a later decision expands scope
- Deterministic post-LLM steps remain the safety net for timestamps and duration
- See `docs/04_AI_CURATION.md` for the current prompt philosophy

---

## DEC-004 — Quality over quantity for clip count

| | |
|---|---|
| **ID** | DEC-004 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

Clip count is driven by quality, not by an artificial hard cap below the validator maximum.

- The curator prompt asks for excellent clips only (typically 5–8; up to 10 when warranted)
- Fewer strong clips beat a padded set of mediocre ones
- `validate_and_filter_clips(..., max_clips=10)` stays at 10; do not introduce a hard limit of 8 in code

**Context**

Earlier prompts required exactly 10 clips, which encouraged filler and weak moments. Product strategy prefers excellent clips for creators.

**Reasoning**

Forcing a fixed count fights editorial judgment. Keeping `max_clips=10` preserves the existing validator contract while letting the model under-generate when quality is low.

**Consequences**

- Users may see fewer than 10 clips on thin or low-signal videos — this is intended
- Validator still caps at 10 if the model over-produces
- Ranking still uses `virality_score` after overlap filtering

---

## DEC-005 — Gaming postponed for launch

| | |
|---|---|
| **ID** | DEC-005 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

Gaming highlight support is **not** a launch priority. Do not add vision models or architecture changes to chase gameplay moments.

**Context**

Current AI is transcript-first. Gameplay highlights are often visual (kills, plays, UI) with sparse or non-explanatory speech.

**Reasoning**

Launch customers are podcast, interview, sports commentary, and educational creators — domains where speech carries the moment. Solving gaming well needs visual understanding the product does not have yet.

**Consequences**

- Expected gaming quality remains limited
- Product messaging and testing prioritize speech-heavy content
- Future gaming work requires a separate product decision (not a silent architecture expansion)

---

## DEC-006 — Keep video processing decoupled from the web server

| | |
|---|---|
| **ID** | DEC-006 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

The offline pipeline in `backend/services/` must remain callable without FastAPI (CLI / `engine`). The HTTP layer in `backend/app/` orchestrates jobs and calls into the engine; it does not embed FFmpeg/Whisper logic.

**Context**

Project rules (`.cursorrules`) require modularity: processing scripts decoupled from web server logic. This is already how the repo is structured.

**Reasoning**

Decoupling allows local debugging (`python -m services.curator`, etc.), clearer ownership, and safer evolution of the API layer.

**Consequences**

- New processing behavior lands in `services/`, not in route handlers
- `video_processor` / job store remain thin adapters around `process_video_to_clips`
- CLI and HTTP paths share the same engine

---

## DEC-007 — Transcript-first clip selection (no vision for launch)

| | |
|---|---|
| **ID** | DEC-007 |
| **Date** | 2026-07-27 |
| **Status** | Accepted |

**Decision**

Clip windows are chosen from Whisper transcripts via an LLM. There is no visual scene understanding in the launch pipeline.

**Context**

The implemented stack is yt-dlp → Whisper → LLM curator → validator → FFmpeg. Vision would add cost, latency, and architectural surface area.

**Reasoning**

Transcript-first matches launch verticals and reuses an already-working path. Vision is deferred until product evidence demands it.

**Consequences**

- Quality depends on speech content and transcription accuracy
- Visual-only moments will be missed
- Fake “viral score” product features and vision routing are explicitly out of scope for current quality work

---

## How to add a decision

1. Assign the next `DEC-NNN` ID.
2. Fill all fields (ID, Date, Status, Decision, Context, Reasoning, Consequences).
3. Keep entries factual and tied to code or explicit product approval.
4. If a decision is replaced, mark the old one `Superseded` and link the new ID.
