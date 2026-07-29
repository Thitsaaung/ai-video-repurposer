# Current State

> **T-Clipper Operating System (TOS)** — Living project status.  
> Update this file after every meaningful development session.  
> Keep entries factual. Prefer short bullets over narrative.

---

## Current Version

`0.1.0` (MVP / pre-auth SaaS)

---

## Current Phase

**Closed-beta / production hardening**

Core pipeline + FastAPI + Next.js UI exist. Auth, durable DB, and full SaaS packaging are not complete.

---

## Current Priority

1. Keep end-to-end clip generation reliable in production (Railway)
2. Stabilize YouTube download under bot / cookie constraints
3. Ship and harden frontend ↔ backend production pairing (CORS, HTTPS, env)
4. Improve AI clip quality via **prompt-first** changes (not architecture rewrites)

---

## Completed Features

- [x] YouTube download via yt-dlp (≤1080p, MP4 merge)
- [x] YouTube cookies support (`YOUTUBE_COOKIES_FILE` / `YOUTUBE_COOKIES_BASE64`)
- [x] Whisper transcription + sanitized transcript JSON
- [x] LLM clip curation (OpenAI default; Anthropic optional)
- [x] Deterministic short-clip extension (whole transcript segments)
- [x] Clip validation (15–60s, bounds, overlap, top-N)
- [x] FFmpeg cut: trim → 9:16 crop → burned-in captions → MP4
- [x] CLI / offline engine (`python -m services.engine`)
- [x] FastAPI job API (submit, poll, media serving)
- [x] Next.js frontend (submit URL, job status, clip preview/download)
- [x] Subtitle Layout Engine (≤3 lines, phrase-aware SRT cues)
- [x] Automatic storage cleanup / retention (downloads, temps, clips, expired jobs)
- [x] Supabase configuration foundation (Phase 0 — env load/validate/startup fail-fast)
- [x] JWT verification + protected API routes (Phase 1 — Bearer auth; no ownership/teams yet)

---

## Working Components

| Component | Path / surface | Notes |
|-----------|----------------|-------|
| Offline engine | `backend/services/engine.py` | E2E orchestration |
| Downloader | `backend/services/video_downloader.py` | yt-dlp |
| Transcriber | `backend/services/transcriber.py` | Whisper API |
| Curator | `backend/services/curator.py` | LLM + extend |
| Validator | `backend/services/clip_validator.py` | Deterministic |
| Cutter | `backend/services/video_cutter.py` | FFmpeg + captions |
| HTTP API | `backend/app/` | FastAPI |
| Job store | In-memory (process-local) | Not durable across restarts; expired terminal jobs purged by cleanup |
| Storage cleanup | `app/services/storage_cleanup.py` | Startup + interval; configurable retention env vars |
| Supabase config | `app/core/supabase_config.py` | Phase 0 foundation (DEC-020) |
| Auth (JWT) | `app/core/auth.py`, `app/deps/auth.py` | Phase 1: verify Supabase JWT; protect jobs/media |
| Frontend | `frontend/` | Next.js 15 App Router |

---

## Known Bugs

| ID | Issue | Severity | Notes |
|----|-------|----------|-------|
| BUG-001 | YouTube bot / “sign in” failures on cloud IPs | High | Mitigated with cookies; cookies expire and must be refreshed |
| BUG-002 | Very long audio can exceed Whisper ~25 MB limit | Medium | Compression helps; chunking not implemented |
| BUG-003 | Unicode console print issues on some Windows code pages | Low | Processing may still succeed |
| BUG-004 | Jobs lost on backend restart | Medium | In-memory job store |

*(Add new rows as bugs are confirmed. Remove or mark resolved when fixed.)*

---

## Known Technical Debt

- In-memory job store (no Redis/DB-backed queue yet)
- Auth JWT gate shipped (Phase 1); no user profiles / job ownership / teams yet
- Frontend login UI + attaching Bearer tokens not shipped yet (API returns 401 when auth enforced)
- No durable clip library or object storage abstraction (local retention cleanup mitigates disk fill)
- Whisper chunking for long videos not implemented
- Optional Node/JS runtime still relevant for some yt-dlp YouTube challenges
- Repo / product naming mix (`ai-video-repurposer` vs `T-Clipper`) in places
- Legacy docs may still say “AI Video Repurposer” without TOS cross-links
- Cookie files are gitignored (`*cookies*.txt`); env-only loading unchanged — see `docs/cookies_secret_management.md`

---

## Current Blockers

| Blocker | Impact | Owner / next step |
|---------|--------|-------------------|
| YouTube anti-bot on Railway without fresh cookies | Downloads fail in prod | Keep cookies current; re-export when failures return |
| Frontend production env / CORS pairing | Browser calls fail if misconfigured | Align `NEXT_PUBLIC_API_BASE` + Railway `CORS_ORIGINS` |

*(Clear blockers when resolved. Empty list is OK.)*

---

## In Progress

- Railway backend production reliability
- Vercel frontend deployment pairing
- Cookie / download resilience for cloud environments
- Subtitle preset bake-off review (Founder chooses A–E default)
- Auth Phase 1 JWT gate complete → next: frontend login + attach tokens; then Phase 2 ownership

---

## Next Milestones

1. Apply chosen subtitle style preset after Founder decision
2. Stable Closed Beta: frontend (Vercel) + backend (Railway) reliably process speech-heavy videos
3. Auth Phase 2 (profiles + job ownership) per `docs/auth_implementation_plan.md`; frontend Supabase login UI
4. Durable jobs / worker path when concurrency or restarts demand it
5. Measurable AI quality loop (prompt evals on known source videos)

---

## Deployment Status

| Surface | Status | Notes |
|---------|--------|-------|
| Backend (Railway) | Deployed / operational | Root Directory = `backend/`; FFmpeg via Railpack apt |
| Frontend (Vercel) | Planned / in progress | Root Directory = `frontend/`; needs `NEXT_PUBLIC_API_BASE` |
| Local CLI pipeline | Working | Preferred for offline debugging |

---

## Frontend Status

- **Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS
- **Capabilities:** URL submit, job polling, clip list, preview/download UX
- **Gaps:** Auth UI, account/billing, production polish depending on deploy state
- **Config:** `NEXT_PUBLIC_API_BASE`, optional poll interval

---

## Backend Status

- **Stack:** FastAPI + modular `services/` pipeline
- **API:** Process video, job status, media/clips
- **Capabilities:** Background job processing via FastAPI `BackgroundTasks`; intelligent subtitle layout before SRT burn-in; automatic storage cleanup; Supabase JWT auth dependency on jobs/media (Phase 1)
- **Gaps:** Frontend login / token attach; job ownership (Phase 2); durable queue; multi-tenant orgs; long-video Whisper chunking; char budget not yet tied to FontSize preset

---

## Infrastructure Status

| Area | Status |
|------|--------|
| Secrets via env (OpenAI, cookies, CORS, Supabase) | In use (Supabase required when `APP_ENV=production`) |
| FFmpeg on Railway | Required (`RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg`) |
| Object storage / CDN for clips | Not yet (local retention cleanup enabled — DEC-019) |
| Observability / alerting | Minimal (logs) |
| CI gates | Not a current focus unless already present |

---

## Current Risks

1. **YouTube extractor / bot policy changes** break downloads without warning
2. **Cookie leakage** if Netscape cookies are committed or logged (mitigated: `*cookies*.txt` gitignored; rotate if ever leaked)
3. **API cost spikes** (Whisper + LLM) on long or frequent jobs
4. **Ephemeral jobs** confuse users after redeploys
5. **Disk fill** mitigated by retention cleanup; still no object storage / CDN
6. **Scope creep** into vision/gaming/architecture rewrites before MVP reliability
7. **Breaking API changes** that desync frontend and backend

---

## Last Updated

**2026-07-30** (auth Phase 1 — JWT verification + protected API)

---

## MVP Success Dashboard

Daily Jobs

Daily Active Users

Average Processing Time

Success Rate

Failed Jobs

Average Cost per Job

Average Clip Rating

Average Queue Time

---

## Current Sprint

Sprint Goal

Sprint Start

Sprint End

Sprint Tasks

Blocked Tasks

Completed Tasks

---

### Session update checklist

When finishing a session, update:

1. **Completed Features** / **In Progress** / **Next Milestones**
2. **Known Bugs** and **Technical Debt** (add, resolve, or re-rank)
3. **Current Blockers** and **Current Risks**
4. **Deployment / Frontend / Backend / Infrastructure Status** if anything changed
5. **Last Updated** date
6. Add a corresponding entry to `ai/DECISIONS.md` if an important decision was made

## Related Documents

- PROJECT.md
- DECISIONS.md
- RULES.md

--- 

## Business Readiness

Authentication

60%

Billing

0%

Subscriptions

0%

Email

0%

Analytics

20%

Support

0%

---

## Target Release

- Closed Beta
- Expected Users
- 50
- 100
- 500