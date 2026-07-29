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
| Job store | In-memory (process-local) | Not durable across restarts |
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
- No authentication / multi-tenancy
- No durable clip library or object storage abstraction
- Whisper chunking for long videos not implemented
- Optional Node/JS runtime still relevant for some yt-dlp YouTube challenges
- Repo / product naming mix (`ai-video-repurposer` vs `T-Clipper`) in places
- Legacy docs may still say “AI Video Repurposer” without TOS cross-links

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
- Documentation foundation (TOS: `docs/PROJECT.md`, `ai/*`)

---

## Next Milestones

1. Stable Closed Beta: frontend (Vercel) + backend (Railway) reliably process speech-heavy videos
2. Auth + persistent storage (Supabase or approved alternative)
3. Durable jobs / worker path when concurrency or restarts demand it
4. Measurable AI quality loop (prompt evals on known source videos)
5. Billing / plan gates (post-auth)

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
- **Capabilities:** Background job processing via FastAPI `BackgroundTasks`
- **Gaps:** Durable queue, auth, multi-tenant isolation, long-video Whisper chunking

---

## Infrastructure Status

| Area | Status |
|------|--------|
| Secrets via env (OpenAI, cookies, CORS) | In use |
| FFmpeg on Railway | Required (`RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg`) |
| Object storage / CDN for clips | Not yet |
| Observability / alerting | Minimal (logs) |
| CI gates | Not a current focus unless already present |

---

## Current Risks

1. **YouTube extractor / bot policy changes** break downloads without warning
2. **Cookie leakage** if Netscape cookies are committed or logged
3. **API cost spikes** (Whisper + LLM) on long or frequent jobs
4. **Ephemeral jobs** confuse users after redeploys
5. **Scope creep** into vision/gaming/architecture rewrites before MVP reliability
6. **Breaking API changes** that desync frontend and backend

---

## Last Updated

**2026-07-29**

---

### Session update checklist

When finishing a session, update:

1. **Completed Features** / **In Progress** / **Next Milestones**
2. **Known Bugs** and **Technical Debt** (add, resolve, or re-rank)
3. **Current Blockers** and **Current Risks**
4. **Deployment / Frontend / Backend / Infrastructure Status** if anything changed
5. **Last Updated** date
6. Add a corresponding entry to `ai/DECISIONS.md` if an important decision was made
