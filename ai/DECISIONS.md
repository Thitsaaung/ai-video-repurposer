# Engineering Decisions

> **T-Clipper Operating System (TOS)** — Architecture Decision Record (ADR) log.  
> Every important engineering or product-engineering decision must be recorded here.  
> Each decision is independent. Do not silently reverse an accepted decision.

## How to add a decision

1. Assign the next `DEC-NNN` ID.
2. Fill **all** fields below.
3. Keep entries factual and tied to code, ops, or explicit product approval.
4. If replaced, set old status to `Superseded` and reference the new ID.

### Required fields

| Field | Meaning |
|-------|---------|
| **Decision ID** | Stable ID (`DEC-NNN`) |
| **Title** | Short name |
| **Date** | Adoption / documentation date (`YYYY-MM-DD`) |
| **Status** | `Accepted` · `Proposed` · `Superseded` · `Deprecated` |
| **Context** | Why this came up |
| **Decision** | What we chose |
| **Reason** | Why this option won |
| **Alternatives Considered** | What else was on the table |
| **Trade-offs** | What we accept |
| **Future Impact** | Constraints this places on later work |

---

## DEC-001 — Product name is T-Clipper

**Decision ID:** DEC-001  
**Title:** Product name is T-Clipper  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
The repository and early docs used “AI Video Repurposer.” The product needs a stable commercial identity for docs, deploy configs, and agent orientation.

**Decision**  
The product name is **T-Clipper**. Internal TOS documents use this name. Repo folder names may lag; product language should not.

**Reason**  
A clear brand reduces ambiguity for engineers, agents, and deployment docs (e.g. Vercel/Railway naming).

**Alternatives Considered**  
- Keep “AI Video Repurposer” permanently  
- Introduce a codename separate from the public name  

**Trade-offs**  
Legacy strings and paths may still say “AI Video Repurposer” until deliberately renamed.

**Future Impact**  
New user-facing and operating docs should prefer T-Clipper. Renames of packages/paths require an explicit migration decision.

---

## DEC-002 — Backend framework is FastAPI

**Decision ID:** DEC-002  
**Title:** Backend framework is FastAPI  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
The product needs an HTTP API for job submission, status polling, and media serving around a Python video pipeline.

**Decision**  
Use **FastAPI** for the backend HTTP layer under `backend/app/`.

**Reason**  
Native async support, strong typing with Pydantic, excellent fit for Python ML/media tooling, fast iteration for MVP APIs.

**Alternatives Considered**  
- Django / Django REST Framework  
- Flask  
- Node/Express backend calling Python workers  

**Trade-offs**  
Python ops/deps must be managed carefully on Railway; CPU-bound FFmpeg still needs subprocess discipline.

**Future Impact**  
API evolution stays on FastAPI unless a formal migration ADR supersedes this. Processing logic must not be trapped inside route handlers.

---

## DEC-003 — Frontend is Next.js (React + TypeScript)

**Decision ID:** DEC-003  
**Title:** Frontend is Next.js (React + TypeScript)  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
T-Clipper needs a SaaS UI for submitting jobs and reviewing clips. Early brainstorming sometimes mentioned generic React SPAs.

**Decision**  
Use **Next.js App Router** with **React**, **TypeScript**, and **Tailwind CSS** in `frontend/`.

**Reason**  
App Router fits SaaS surfaces, TypeScript reduces contract drift with the API, and the codebase is already implemented and documented for Vercel with Root Directory `frontend/`.

**Alternatives Considered**  
- React + Vite SPA only  
- Remix  
- Pure static HTML  

**Trade-offs**  
Next.js adds framework conventions vs a minimal Vite SPA; deploy must set Vercel Root Directory correctly.

**Future Impact**  
Do not rewrite the frontend to Vite/SPA without an explicit superseding decision. Prefer incremental UI improvements inside the existing Next.js app.

---

## DEC-004 — Backend hosting is Railway

**Decision ID:** DEC-004  
**Title:** Backend hosting is Railway  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
The pipeline requires FFmpeg, Python, and longer-running jobs unsuitable for typical serverless function timeouts alone.

**Decision**  
Host the backend on **Railway** with Root Directory `backend/`, Railpack builder, and FFmpeg installed via apt package config.

**Reason**  
Straightforward container-like deploys, env var management, and ability to install system packages (FFmpeg) needed for rendering.

**Alternatives Considered**  
- Render  
- Fly.io  
- AWS ECS / custom VPS  
- Serverless-only (Lambda, etc.)  

**Trade-offs**  
Cold starts / restarts wipe in-memory jobs; YouTube bot challenges are harsher on cloud IPs; cost scales with always-on compute.

**Future Impact**  
Ops docs and env conventions assume Railway. Moving hosts requires a dedicated ADR and migration plan.

---

## DEC-005 — OpenAI is the default AI provider

**Decision ID:** DEC-005  
**Title:** OpenAI is the default AI provider  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Clip curation and transcription need hosted AI APIs for MVP speed.

**Decision**  
Use **OpenAI** as the default provider for Whisper transcription and default LLM curation (e.g. `gpt-4o-mini`). Optional Anthropic may be used for curation when configured.

**Reason**  
Single primary vendor reduces integration surface; Whisper + chat models are already integrated and working.

**Alternatives Considered**  
- Local Whisper only  
- Anthropic-only stack  
- Multi-provider abstraction from day one  

**Trade-offs**  
Vendor cost and rate limits; dependency on OpenAI availability and pricing.

**Future Impact**  
Provider abstractions can be added later, but default paths should remain OpenAI unless superseded. Keep API keys in env only.

---

## DEC-006 — Whisper for transcription

**Decision ID:** DEC-006  
**Title:** Whisper for transcription  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Clip selection requires accurate speech timestamps.

**Decision**  
Transcribe with **OpenAI Whisper API**, using compressed mono audio and segment-level timestamps.

**Reason**  
Good accuracy/cost balance for MVP; segment timestamps enable boundary snap and deterministic extension.

**Alternatives Considered**  
- Local Whisper models  
- Deepgram / AssemblyAI  
- Subtitle track scraping only  

**Trade-offs**  
~25 MB upload limit without chunking; API cost; latency on long videos.

**Future Impact**  
Long-form chunking is expected technical work. Do not replace Whisper casually without quality comparison and an ADR.

---

## DEC-007 — Subtitles are burned into the video

**Decision ID:** DEC-007  
**Title:** Subtitles burned into the video  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Short-form platforms often play muted; captions are essential for retention.

**Decision**  
Burn captions into exported MP4s via FFmpeg (`subtitles` / libass), not soft-only sidecar delivery as the primary MVP output.

**Reason**  
Burned-in captions work everywhere without depending on platform caption upload UX.

**Alternatives Considered**  
- Soft subtitles (SRT/VTT only)  
- Platform-native caption upload APIs  
- No captions in MVP  

**Trade-offs**  
Harder to restyle after export; FFmpeg must include subtitle filter support; rendering is more CPU-heavy.

**Future Impact**  
Caption styling changes happen in the cutter pipeline. Soft-subtitle export may be additive later without removing burn-in as default.

---

## DEC-008 — Cursor Pro is the implementation IDE

**Decision ID:** DEC-008  
**Title:** Cursor Pro is the implementation IDE  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
The team uses AI-assisted implementation and needs a standard agent environment.

**Decision**  
Use **Cursor Pro** as the primary implementation IDE for T-Clipper engineering agents and developers.

**Reason**  
Repo-aware agents, rules/skills, and tight edit loops match the project’s AI-orchestrated workflow.

**Alternatives Considered**  
- VS Code only  
- JetBrains IDEs as primary  
- Cloud-only coding agents  

**Trade-offs**  
Agents must be constrained by TOS docs (`ai/RULES.md`) to avoid unsafe rewrites.

**Future Impact**  
Project rules, skills, and TOS docs are written assuming Cursor-based agents will read them before coding.

---

## DEC-009 — ChatGPT is the Software Architect partner

**Decision ID:** DEC-009  
**Title:** ChatGPT is the Software Architect partner  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
Architecture and product-system design benefit from a dedicated high-level partner separate from line-by-line implementation.

**Decision**  
Use **ChatGPT** as the Software Architect partner for system design, decision framing, and operating documentation guidance. Cursor agents implement within those constraints.

**Reason**  
Separating architecture judgment from implementation agents reduces tunnel vision and undocumented decisions.

**Alternatives Considered**  
- Architecture solely inside Cursor agents  
- Human-only architecture with no AI partner  

**Trade-offs**  
Architect guidance must still be verified against the real codebase; this file remains the source of truth for accepted decisions.

**Future Impact**  
Major design changes should be written into this ADR log before large implementation starts.

---

## DEC-010 — Production-first mindset

**Decision ID:** DEC-010  
**Title:** Production-first mindset  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
Early-stage products often accumulate prototypes that cannot be operated.

**Decision**  
Prefer changes that are **safe to deploy, observe, and reverse**. Treat Railway/Vercel reality as first-class constraints.

**Reason**  
A demo that cannot survive production constraints is not MVP progress.

**Alternatives Considered**  
- Local-only prototype culture  
- Rewrite-first “clean architecture” phases  

**Trade-offs**  
Some elegant abstractions are deferred; occasional temporary roughness is accepted if production risk is lower.

**Future Impact**  
Agents must weigh deploy, secrets, CORS, FFmpeg, and YouTube constraints before proposing rewrites.

---

## DEC-011 — Investigate before changing code

**Decision ID:** DEC-011  
**Title:** Investigate before changing code  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
AI agents often patch symptoms or rewrite modules when a config/env/root-cause fix would suffice.

**Decision**  
**Investigate first:** reproduce, read relevant code/logs/docs, identify root cause, then change the minimum necessary surface.

**Reason**  
Prevents regressions, preserves working pipeline behavior, and keeps diffs reviewable.

**Alternatives Considered**  
- Speculative rewrites  
- “Fix by redesign” as default  

**Trade-offs**  
Slightly slower start to coding; much lower incident rate.

**Future Impact**  
Debugging sessions must explain root cause. Drive-by refactors are out of scope unless requested.

---

## DEC-012 — Minimal safe changes only

**Decision ID:** DEC-012  
**Title:** Minimal safe changes only  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
Working download → transcribe → curate → cut pipelines are high-value assets.

**Decision**  
Default to the **smallest correct change**. No rewrites of working code. No unrelated cleanups in the same change.

**Reason**  
Blast radius control is mandatory for media pipelines and production deploys.

**Alternatives Considered**  
- Opportunistic large refactors  
- “While we’re here” dependency upgrades bundled into fixes  

**Trade-offs**  
Codebase may retain known debt longer; debt is tracked in `ai/CURRENT_STATE.md` instead of silent rewrites.

**Future Impact**  
PRs/agent sessions should be easy to review. Large changes require explicit scope approval and often their own ADR.

---

## DEC-013 — Preserve backend architecture split

**Decision ID:** DEC-013  
**Title:** Preserve backend architecture split  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
The backend already separates offline processing from HTTP.

**Decision**  
Keep:

- `backend/services/` — offline pipeline (download → transcribe → curate → cut)
- `backend/app/` — FastAPI HTTP layer (jobs, media)

Orchestration remains via `engine.process_video_to_clips` (or thin adapters around it).

**Reason**  
Low blast radius, CLI debugability, clear ownership.

**Alternatives Considered**  
- Merge pipeline into route handlers  
- Introduce a new processing framework/queue prematurely  

**Trade-offs**  
Some duplication in adapters; queue/worker extraction waits until needed.

**Future Impact**  
New processing behavior lands in `services/`, not routes. Architecture redesign needs founder/CTO-level approval and a new ADR.

---

## DEC-014 — Backend API treated as launch-stable

**Decision ID:** DEC-014  
**Title:** Backend API treated as launch-stable  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Frontend depends on job submit/poll and media routes.

**Decision**  
Treat the current FastAPI surface as stable for launch. Prefer additive, backward-compatible changes. Do not break request/response shapes without an explicit versioning plan.

**Reason**  
API churn breaks the UI and any external callers.

**Alternatives Considered**  
- Frequent breaking redesigns  
- Immediate public versioning (`/v2`) without need  

**Trade-offs**  
Some awkward fields may persist longer; versioning overhead is deferred until necessary.

**Future Impact**  
Agents must preserve contracts. Public payloads continue to avoid leaking absolute filesystem paths.

---

## DEC-015 — Prompt-first AI quality improvements

**Decision ID:** DEC-015  
**Title:** Prompt-first AI quality improvements  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Clip quality is the product. Architecture churn is not.

**Decision**  
Improve selection quality primarily by changing curator prompts and related localized logic—not by adding vision models, category routers, or new AI services by default.

**Reason**  
Highest impact-to-risk ratio; deterministic snap/extend/validate already provide safety nets.

**Alternatives Considered**  
- Vision-first pipeline  
- Multi-agent curation graphs  
- Hard rewrites of curator architecture  

**Trade-offs**  
Quality ceiling is bounded by transcript signal until a later vision decision.

**Future Impact**  
Gaming/visual-only excellence is postponed. See also DEC-016 and DEC-017.

---

## DEC-016 — Quality over quantity for clips

**Decision ID:** DEC-016  
**Title:** Quality over quantity for clips  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Forcing a fixed high clip count encouraged weak filler.

**Decision**  
Prefer fewer excellent clips over padded mediocre sets. Validator max remains a safety cap (e.g. 10); do not force exact counts in prompts/code.

**Reason**  
Editorial judgment beats arbitrary quotas for creator trust.

**Alternatives Considered**  
- Always return exactly N clips  
- Hard-code a lower max in validator without product need  

**Trade-offs**  
Thin videos may return fewer clips; UX must not treat that as failure by default.

**Future Impact**  
Product copy and tests should expect variable clip counts driven by content quality.

---

## DEC-017 — Transcript-first clip selection (no vision at launch)

**Decision ID:** DEC-017  
**Title:** Transcript-first clip selection (no vision at launch)  
**Date:** 2026-07-27  
**Status:** Accepted  

**Context**  
Gameplay and visual-only moments are poorly served by speech-only models.

**Decision**  
Launch pipeline chooses clip windows from Whisper transcripts via LLM. No visual scene understanding in the launch path. Gaming highlight excellence is explicitly postponed.

**Reason**  
Matches ICP (speech-heavy content); avoids cost/latency/architecture expansion before reliability.

**Alternatives Considered**  
- Vision models at launch  
- Hybrid audio-visual scoring immediately  

**Trade-offs**  
Visual-only moments will be missed; gaming quality remains limited.

**Future Impact**  
Vision/gaming work requires a separate accepted ADR—not a silent expansion.

---

## DEC-018 — Frontend hosting target is Vercel

**Decision ID:** DEC-018  
**Title:** Frontend hosting target is Vercel  
**Date:** 2026-07-29  
**Status:** Accepted  

**Context**  
Backend is on Railway; the Next.js app needs a complementary host.

**Decision**  
Deploy the frontend to **Vercel** with Root Directory `frontend/`, pairing via `NEXT_PUBLIC_API_BASE` and Railway `CORS_ORIGINS`.

**Reason**  
Native Next.js fit; documented deployment path already exists in `frontend/DEPLOY.md`.

**Alternatives Considered**  
- Host frontend on Railway too  
- Netlify  
- Cloudflare Pages  

**Trade-offs**  
Two platforms to configure; CORS and env drift are operational risks.

**Future Impact**  
Frontend deploy docs and agent instructions assume Vercel unless superseded.

---

*When in doubt: add a decision here before implementing a directional change.*
