# T-Clipper Production Health Check

> Engineering audit only — no code changes in this session.  
> Scope: `backend/` + `frontend/` (plus related ops/security signals).  
> Date: **2026-07-30**  
> Product stage: Closed-beta / production hardening (`0.1.0`)

---

## Executive summary

The core pipeline and API contracts are coherent for closed beta: FastAPI ↔ Next.js job submit/poll/media works, services stay mostly decoupled, and path/media hardening exists on download routes. Production readiness is blocked less by “messy code” and more by **unauthenticated open compute**, **ephemeral jobs**, **unbounded disk**, **credential hygiene**, and **thin automated test coverage**. Several temporary `DEBUG` print paths still run on every curation/validation job.

Severity guide used below:

| Level | Meaning |
|-------|---------|
| **Critical** | Can cause outage, secret leakage, abuse, or data/privacy breach in production now |
| **High** | Likely user-facing failure, cost spike, or serious reliability gap under real beta load |
| **Medium** | Meaningful debt / inconsistency that will bite as usage or team size grows |
| **Low** | Cleanup, naming, organization — improve when touching nearby code |

For every finding: **description**, **affected files**, **business impact**, **suggested priority**.

---

## Critical

### C1 — Unauthenticated public job API (open Whisper + LLM + FFmpeg spend)

- **description:** `POST /api/process-video` accepts any YouTube URL with no auth, API key, quota, or rate limit. Anyone who can reach the Railway origin can enqueue expensive downloads, Whisper transcription, LLM curation, and FFmpeg renders. Jobs are serialized by a process lock, but requests can still pile up and hold the queue for hours while burning API spend.
- **affected files:** `backend/app/routes/videos.py`, `backend/app/services/video_processor.py`, `backend/app/main.py`
- **business impact:** Unbounded OpenAI (and optional Anthropic) cost; denial-of-service via queue saturation; closed-beta abuse risk as soon as the API URL is known.
- **suggested priority:** P0 before widening beta traffic or publishing the API URL broadly. At minimum: shared beta token / IP allowlist / tight rate limit + max concurrent queued jobs.

### C2 — All generated clips publicly listable/guessable without auth

- **description:** Clips are served via `StaticFiles` at `/media/clips` and via `/media/download/{filename}`. Filenames are deterministic (`clip_{id}_{title}.mp4`) and not tied to job ownership. There is no auth, signed URL, or per-job ACL. Knowing or guessing a filename grants access to another user’s output.
- **affected files:** `backend/app/main.py`, `backend/app/routes/media.py`, `backend/services/video_cutter.py`, `frontend/app/lib/api.ts`
- **business impact:** Privacy/leak risk for creator content; competitive/content theft; incompatible with multi-user SaaS without redesign.
- **suggested priority:** P0 for any multi-user or public beta with real creator content. Prefer opaque names + auth/signed URLs; remove world-readable StaticFiles listing assumptions.

### C3 — YouTube cookie credentials present locally and not gitignored

- **description:** `backend/cookies.txt` exists on disk (~2 KB) and is **untracked** (`??`) but **not listed in `.gitignore`**. Cookie env/materialization is correctly treated as secret in code, but local Netscape cookie files can be committed by accident. Repo rules already forbid committing cookies; ignore rules do not enforce that.
- **affected files:** `backend/cookies.txt` (local), `.gitignore`, `backend/app/core/config.py` (`YOUTUBE_COOKIES_*`)
- **business impact:** Accidental commit/push of YouTube session cookies compromises the account used for downloads and can take production downloads offline or expose account access.
- **suggested priority:** P0 immediately — add `cookies.txt`, `*cookies*.txt`, and similar patterns to `.gitignore`; rotate cookies if ever committed; keep only env-based secrets in Railway.

### C4 — Unbounded local media retention (disk fill / Railway volume exhaustion)

- **description:** Every successful job leaves full source videos under `downloads/`, transcripts under `transcripts/`, and rendered MP4s under `output_clips/` with **no TTL, cleanup, or quota**. Local workspace snapshot already shows ~**7.0 GB** downloads, ~**1.2 GB** clips, ~**85** transcript files — evidence the pipeline accumulates aggressively.
- **affected files:** `backend/services/video_downloader.py`, `backend/services/pipeline.py`, `backend/services/transcriber.py`, `backend/services/curator.py`, `backend/services/video_cutter.py`, `backend/app/core/config.py` (`output_clips_dir`)
- **business impact:** Production disk full → all jobs fail; Railway redeploys/ephemeral FS may hide this until volume is attached, then fill again; rising storage cost; slower ops.
- **suggested priority:** P0 for sustained production. Add post-job cleanup policy (delete source after cut; expire clips; object storage) before scaling daily jobs.

---

## High

### H1 — In-memory job store; jobs vanish on restart (BUG-004)

- **description:** Job state lives in a process-local dict (`_jobs`). Railway redeploy/restart clears all jobs. Frontend restores `job_id` from `localStorage` and then 404s.
- **affected files:** `backend/app/services/job_store.py`, `frontend/app/lib/jobPersistence.ts`, `frontend/app/hooks/useVideoJob.ts`
- **business impact:** Users lose progress mid-job after deploys; support load; trust damage during closed beta.
- **suggested priority:** P1 for closed-beta reliability messaging; P0 once concurrent users / deploys are frequent. Durable store or clear UX that jobs are ephemeral.

### H2 — No job timeout / stuck `processing` forever

- **description:** Background pipeline has no watchdog. If the worker dies mid-run, hangs in yt-dlp/FFmpeg, or the process is killed after status=`processing`, the job never transitions to `failed`. Frontend polls until three network failures, then stops — but a live backend can report `processing` indefinitely.
- **affected files:** `backend/app/services/video_processor.py`, `backend/app/services/job_store.py`, `frontend/app/hooks/useVideoJob.ts`
- **business impact:** Infinite spinner UX; confused users; occupied pipeline lock blocking the next job.
- **suggested priority:** P1 — job max runtime + heartbeat/stage timestamps + auto-fail stale jobs.

### H3 — Global pipeline lock makes multi-user latency a product cliff

- **description:** `_pipeline_lock` intentionally serializes all engine runs (shared `temp.srt` / `temp_audio.mp3`). Concurrent submitters queue behind one long video (download + Whisper + LLM + N FFmpeg cuts).
- **affected files:** `backend/app/services/video_processor.py`, `backend/services/transcriber.py`, `backend/services/video_cutter.py`
- **business impact:** Acceptable for tiny beta; with ~50 users, queue wait explodes and looks like “the product is broken.”
- **suggested priority:** P1 before scaling concurrency — per-job temp paths first (unlock parallelism), then real queue/worker.

### H4 — Clip filename collisions overwrite prior users’ outputs

- **description:** Outputs are named `clip_{clip_id}_{sanitized_title}.mp4` in a shared `output_clips/` directory. Clip IDs reset to 1..N per job. Two jobs with similar titles can overwrite each other’s files; StaticFiles then serves the latest bytes under the same URL.
- **affected files:** `backend/services/video_cutter.py`, `backend/app/core/paths.py`, `frontend/app/lib/api.ts`
- **business impact:** Wrong clip preview/download; silent data loss; cross-job contamination.
- **suggested priority:** P1 — include `job_id` / `video_id` / UUID in filenames or isolate per-job directories.

### H5 — Production DEBUG `print` noise on every curation/validation path

- **description:** Hot-path `print("DEBUG[curator]...")` and `print("DEBUG[validator]...")` run during normal jobs (not only CLI `__main__`). Duplicates structured `logger` output, pollutes Railway logs, and violates project “remove temporary diagnostics” rule.
- **affected files:** `backend/services/curator.py`, `backend/services/clip_validator.py`
- **business impact:** Harder incident diagnosis; log volume/cost; risk of shipping more temporary diagnostics as “normal.”
- **suggested priority:** P1 — replace with `logger.debug` gated by log level (keep CLI prints only under `__main__`).

### H6 — Missing automated tests for nearly the entire product surface

- **description:** Only `backend/tests/test_subtitle_layout.py` exists. No tests for job store, API routes, URL validation, curator snap/extend, clip validator, cutter padding, user-error mapping, or any frontend module. Frontend `package.json` has `lint` but no test runner.
- **affected files:** `backend/tests/` (subtitle only), `frontend/package.json`, core modules under `backend/services/` and `backend/app/`, `frontend/app/`
- **business impact:** Regressions in duration gates, media path safety, or job contracts ship unnoticed; slow/fearful changes to the money path.
- **suggested priority:** P1 — start with API contract + validator + user_errors + media path traversal tests; then hook/API client smoke tests.

### H7 — No Whisper chunking for long videos (BUG-002)

- **description:** Compressed mono MP3 still fails hard above ~24 MB. User sees a friendly “processing limit” message, but long podcasts (ICP content) cannot complete.
- **affected files:** `backend/services/transcriber.py`, `backend/app/core/user_errors.py`
- **business impact:** Core ICP videos fail; conversion loss vs competitors; support tickets.
- **suggested priority:** P1 for closed-beta content mix that includes long episodes.

### H8 — YouTube bot/cookie fragility in cloud (BUG-001)

- **description:** Production downloads depend on fresh cookies / yt-dlp extractor health. Cookie expiry or YouTube policy change fails the entire funnel. Mitigations exist but operational process is manual.
- **affected files:** `backend/services/video_downloader.py`, `backend/app/core/config.py`, `backend/app/core/user_errors.py`
- **business impact:** Sudden 100% download failure in production until cookies refreshed.
- **suggested priority:** P1 ops runbook + monitoring on download error signatures; treat cookie rotation as production dependency.

### H9 — No CI gates

- **description:** No `.github/workflows` (or equivalent) found. Lint/tests are not enforced on PR merge.
- **affected files:** repo root (missing CI), `frontend/package.json`, `backend/tests/`
- **business impact:** Broken main branch risk; inconsistent deploy quality.
- **suggested priority:** P1 before larger team/PR volume — minimal CI: pytest + `next build` / eslint.

### H10 — API cost & abuse surface without observability

- **description:** Infrastructure status already notes minimal observability. No per-job cost meters, success-rate alerts, or download-failure dashboards in code. Combined with open API (C1), spend spikes are detected late.
- **affected files:** `backend/app/services/video_processor.py`, `backend/services/engine.py`, `backend/app/core/logging_config.py`
- **business impact:** Silent margin burn; slow incident response.
- **suggested priority:** P1 — structured job metrics (duration, stage, failure class, clip count) + basic alerts.

---

## Medium

### M1 — Temporary shared files couple concurrency and cleanup

- **description:** Global `backend/temp_audio.mp3` and `backend/temp.srt` require the pipeline lock. Cleanup is best-effort; concurrent designs remain unsafe without per-job temps.
- **affected files:** `backend/services/transcriber.py`, `backend/services/video_cutter.py`, `backend/app/services/video_processor.py`
- **business impact:** Blocks horizontal scaling; residual temps after crashes.
- **suggested priority:** P2 when unlocking concurrency (pairs with H3).

### M2 — Large “god” modules that should eventually split

- **description:** Oversized modules mix prompting, LLM I/O, snap/extend, persistence (`curator.py` ~630 lines); FFmpeg cut + SRT + CLI resolvers (`video_cutter.py` ~580); layout algorithms (`subtitle_layout.py` ~445); dense UI state machine (`JobStatus.tsx` ~340; `useVideoJob.ts` ~220).
- **affected files:** `backend/services/curator.py`, `backend/services/video_cutter.py`, `backend/services/subtitle_layout.py`, `frontend/app/components/JobStatus.tsx`, `frontend/app/hooks/useVideoJob.ts`
- **business impact:** Higher change risk; slower reviews; accidental behavior coupling.
- **suggested priority:** P2 — split only when next feature touches them (per DEC-012).

### M3 — Duplicate duration constants and YouTube URL parsing

- **description:** `MIN_CLIP_SECONDS` / `MAX_CLIP_SECONDS` duplicated in `curator.py` and `clip_validator.py`. YouTube host/id parsing duplicated across `app/core/validation.py`, `services/pipeline.py`, and frontend `app/lib/youtube.ts` (frontend helper used for thumbnails only; form does not pre-validate like backend).
- **affected files:** `backend/services/curator.py`, `backend/services/clip_validator.py`, `backend/app/core/validation.py`, `backend/services/pipeline.py`, `frontend/app/lib/youtube.ts`, `frontend/app/components/VideoForm.tsx`
- **business impact:** Drift can accept invalid clips or reject valid URLs inconsistently.
- **suggested priority:** P2 — single shared constants module; align FE validation messages with backend.

### M4 — Dead / CLI-only resolver helpers in cutter

- **description:** `_find_download_by_video_id`, `_video_path_from_sanitized`, `_resolve_video_for_curated`, `_pick_latest_curated`, `_pick_latest_curated_with_video` are unused by the production engine path; `__main__` now requires explicit paths. They remain as latent “auto-pick latest” logic that previously caused wrong-video bugs.
- **affected files:** `backend/services/video_cutter.py`
- **business impact:** Confusion for future agents; risk someone rewires auto-detect into production.
- **suggested priority:** P2 — delete or clearly quarantine as CLI-only with tests.

### M5 — Logging inconsistency (stdlib logger vs DEBUG prints vs CLI prints)

- **description:** FastAPI layer uses structured `logging`. Pipeline services mostly use `logger`, but curator/validator still use `print(DEBUG...)`. CLI `__main__` blocks use `print` (acceptable). `configure_logging` is basicConfig-only — no JSON/request-id correlation.
- **affected files:** `backend/app/core/logging_config.py`, `backend/services/curator.py`, `backend/services/clip_validator.py`, other `services/*`
- **business impact:** Uneven production diagnostics; hard to grep job_id across stages.
- **suggested priority:** P2 — standardize on logger + job_id context.

### M6 — Error-handling consistency is good at API edge, uneven inside services

- **description:** API maps failures to user-facing strings via `to_user_facing_error` (good). Engine swallows exceptions into `{status: error}` then processor maps them. Partial clip cut failures are logged and skipped; job can still “succeed” with a subset — correct product-wise but not surfaced clearly to the client beyond clip count.
- **affected files:** `backend/services/engine.py`, `backend/app/services/video_processor.py`, `backend/app/core/user_errors.py`, `backend/services/video_cutter.py`
- **business impact:** Users may not understand partial generation; some internal errors collapse to generic message (by design) hiding actionable classes.
- **suggested priority:** P2 — expose safe failure classes (`too_long`, `unavailable`, `access`, `partial_clips`) without leaking internals.

### M7 — Frontend poll race under slow networks

- **description:** `setInterval` fires `pollOnce` every 5s without awaiting prior completion or using `AbortController`. Overlapping polls can apply out-of-order job snapshots if latency > interval.
- **affected files:** `frontend/app/hooks/useVideoJob.ts`
- **business impact:** Occasional UI flicker or stale status under slow API.
- **suggested priority:** P2 — single-flight poll or abort previous request.

### M8 — Services depend on `app.core.config` (architecture coupling)

- **description:** Offline pipeline imports FastAPI settings (`resolve_youtube_cookiefile`, `get_settings` for pad seconds). Works when cwd/PYTHONPATH is `backend/`, but blurs DEC-013 “services ≠ HTTP” boundary.
- **affected files:** `backend/services/video_downloader.py`, `backend/services/video_cutter.py`, `backend/app/core/config.py`
- **business impact:** Harder to run/test services in isolation; config changes can surprise CLI users.
- **suggested priority:** P2 — thin shared `config` module outside `app/` when next touching cookies/padding.

### M9 — Dual dotenv loading patterns

- **description:** `pydantic-settings` loads `.env` in API config; `curator.py` / `transcriber.py` also call `load_dotenv` independently. Env precedence can surprise operators.
- **affected files:** `backend/app/core/config.py`, `backend/services/curator.py`, `backend/services/transcriber.py`
- **business impact:** “Works locally / fails on Railway” class bugs when keys differ across files.
- **suggested priority:** P2 — one settings entry point for process env.

### M10 — LLM provider preference contradicts “OpenAI default” ADR when both keys set

- **description:** `_choose_provider` prefers Anthropic if `ANTHROPIC_API_KEY` is set, else OpenAI. DEC-005 says OpenAI is the default provider.
- **affected files:** `backend/services/curator.py`, `ai/DECISIONS.md` (DEC-005)
- **business impact:** Unexpected model/cost/quality changes in environments that happen to have both keys.
- **suggested priority:** P2 — explicit `LLM_PROVIDER` env or flip preference to match ADR.

### M11 — Diagnostic / experiment artifacts in workspace

- **description:** `backend/diag_phase0/` PNGs and `comparison/` preset videos are local experiment outputs (mostly untracked). Not served by API, but clutter deploys if Root Directory packaging is loose.
- **affected files:** `backend/diag_phase0/*`, `comparison/*`
- **business impact:** Noise; accidental large commits; agent confusion about “source of truth” presets.
- **suggested priority:** P2 — gitignore diagnostic dirs; keep comparison scripts opt-in.

### M12 — Naming inconsistency: T-Clipper vs AI Video Repurposer vs `avr:`

- **description:** Product is T-Clipper (DEC-001). API `app_name` still “AI Video Repurposer API”; frontend storage key `avr:activeJobId`; comments say “video-repurposer.”
- **affected files:** `backend/app/core/config.py`, `backend/app/main.py`, `frontend/app/lib/jobPersistence.ts`, `frontend/types/job.ts`
- **business impact:** Brand/docs drift; low user impact today.
- **suggested priority:** P3 unless doing a branding pass (avoid breaking localStorage key without migration).

### M13 — Deprecated FastAPI startup hook / BackgroundTasks longevity

- **description:** `@app.on_event("startup")` is legacy vs lifespan handlers. Long CPU/FFmpeg work runs in FastAPI `BackgroundTasks` inside the web process — fine for MVP, fragile for multi-instance/zero-downtime.
- **affected files:** `backend/app/main.py`, `backend/app/routes/videos.py`
- **business impact:** Deploy drains can cut jobs; harder to scale workers independently.
- **suggested priority:** P2 when introducing durable queue (already on roadmap).

### M14 — Frontend has no production auth/billing surface (expected debt)

- **description:** Documented gaps: auth UI, billing, durable library. Form advertises “No signup required · Free beta” which matches current backend openness (C1).
- **affected files:** `frontend/app/page.tsx`, `frontend/app/components/VideoForm.tsx`, `ai/CURRENT_STATE.md`
- **business impact:** Cannot monetize or isolate tenants; OK only while intentionally open beta.
- **suggested priority:** P2 aligned with Supabase milestone — do not paper over with fake UI.

---

## Low

### L1 — No TODO/FIXME markers in source; temporary debug is unlabeled

- **description:** Grep found essentially no `TODO`/`FIXME` comments. Temporary diagnostics are instead unlabeled `DEBUG` prints (see H5). That means debt is invisible to standard TODO sweeps.
- **affected files:** `backend/services/curator.py`, `backend/services/clip_validator.py`
- **business impact:** Hygiene debt hides from planning tools.
- **suggested priority:** P3 — prefer logger + tracked tickets over permanent DEBUG prints.

### L2 — Folder organization is mostly sound

- **description:** `backend/app/` (HTTP) vs `backend/services/` (pipeline) matches DEC-013. Frontend `app/components`, `app/lib`, `app/hooks`, `types/` is clear. Minor: `backend/app/services/` naming overlaps `backend/services/` (job adapter vs pipeline).
- **affected files:** `backend/app/services/*`, `backend/services/*`
- **business impact:** New contributors may put pipeline code in the wrong `services` package.
- **suggested priority:** P3 — rename only with ADR if confusion bites (e.g. `app/jobs/`).

### L3 — CLI `__main__` print helpers mixed into production modules

- **description:** Many services include CLI entrypoints with `print` / `input`. Fine for offline debug; slightly inflates modules.
- **affected files:** `backend/services/engine.py`, `pipeline.py`, `curator.py`, `transcriber.py`, `video_downloader.py`, `video_cutter.py`
- **business impact:** Low — only if someone imports side effects (they don’t at import time).
- **suggested priority:** P3 — optional `scripts/` extraction later.

### L4 — `layout_segment_texts` / `words_from_cues` are test-oriented exports

- **description:** Production cutter uses `layout_segment` only; helpers are used by unit tests. Not dead — keep.
- **affected files:** `backend/services/subtitle_layout.py`, `backend/tests/test_subtitle_layout.py`
- **business impact:** None.
- **suggested priority:** None (note only).

### L5 — Health endpoint is liveness-only

- **description:** `/health` returns `{status: ok}` without checking FFmpeg, disk, OpenAI key, or cookie materialization.
- **affected files:** `backend/app/main.py`
- **business impact:** Orchestrators mark service healthy while jobs cannot run.
- **suggested priority:** P3 — add readiness checks when ops matures.

### L6 — CORS credentials + wildcard methods/headers

- **description:** CORS allowlist is env-driven (good). `allow_credentials=True` with `allow_methods=["*"]` / `allow_headers=["*"]` is broader than needed for a simple JSON API.
- **affected files:** `backend/app/main.py`, `backend/app/core/config.py`
- **business impact:** Low while no cookies/auth on API; tighten when auth lands.
- **suggested priority:** P3 with auth work.

### L7 — `JobStatus` component size / dual progress UIs

- **description:** Live stage list + fallback `PROCESS_STEPS` overview coexist. Works, but large for a single panel.
- **affected files:** `frontend/app/components/JobStatus.tsx`
- **business impact:** Maintainability only.
- **suggested priority:** P3 when restyling progress UX.

### L8 — Unicode Windows console issues (BUG-003)

- **description:** Known low-severity local console encoding issues; processing may still succeed.
- **affected files:** FFmpeg log capture paths in `transcriber.py` / `video_cutter.py` (utf-8 replace already used)
- **business impact:** Local Windows developer friction only.
- **suggested priority:** P3.

### L9 — Comparison / preset bake-off tooling outside product path

- **description:** `comparison/generate_presets.py` and related media are engineering tools, not SaaS runtime. Fine if kept out of deploy artifacts.
- **affected files:** `comparison/*`
- **business impact:** None if not deployed.
- **suggested priority:** P3 documentation note only.

---

## Cross-cutting inventory (requested scan axes)

| Axis | Verdict |
|------|---------|
| **Technical debt** | Documented in `ai/CURRENT_STATE.md` and confirmed in code: ephemeral jobs, no auth, no object storage, no Whisper chunking, open media. |
| **Dead code** | Cutter “latest file” resolvers largely unused by engine/CLI `__main__` (M4). No large abandoned frontend components found. |
| **Unused functions** | Same as M4; subtitle helpers used by tests. |
| **Duplicate logic** | Duration constants; YouTube URL parsing FE/BE/pipeline (M3). |
| **Large functions/modules** | `curate_clips`, `process_all_curated_clips`, `layout_segment`, `JobStatus` (M2). |
| **Missing tests** | Nearly everything except subtitle layout (H6). |
| **Race conditions** | Mitigated server pipeline race via lock; FE poll overlap (M7); filename overwrite race across jobs (H4). |
| **Memory / disk** | Disk growth critical (C4); FFmpeg `capture_output` buffers stderr (usually OK); Whisper uploads file stream (OK); in-memory job dict unbounded (H1 adjacent). |
| **Temporary debug** | Hot-path DEBUG prints (H5); CLI prints OK. |
| **TODO / FIXME** | Almost none; debt expressed as DEBUG prints + CURRENT_STATE instead (L1). |
| **Error handling** | Strong API boundary + user_errors; generic fallback; partial cuts under-communicated (M6). |
| **Logging** | App layer consistent; services mixed with prints (M5). |
| **Folder organization** | Sound overall; dual `services` naming (L2). |
| **Naming** | T-Clipper vs legacy AVR naming (M12). |
| **Production risks** | C1–C4, H1–H10 dominate closed-beta readiness. |

---

## What is already in good shape (for balance)

These are **not** findings — retained strengths to avoid false “rewrite” pressure:

1. Clear pipeline/API split (`services/` vs `app/`) and engine entrypoint.
2. Media download path traversal protections in `media.py`.
3. Public job responses strip absolute filesystem paths (`paths.to_public_job`).
4. User-facing error mapping avoids leaking Whisper/cookie internals.
5. Frontend production `NEXT_PUBLIC_API_BASE` fail-fast for localhost/non-HTTPS.
6. Deterministic validator + boundary snap/extend safety net around LLM output.
7. Subtitle layout has real unit tests.
8. Cookie values are not logged (presence flags only).

---

## Suggested remediation order (no implementation in this audit)

1. **P0:** Cookie gitignore + secret hygiene (C3); decide auth/rate-limit posture (C1); stop world-readable/colliding clip URLs (C2/H4); disk retention policy (C4).
2. **P1:** Job durability or honest ephemeral UX (H1/H2); remove DEBUG prints (H5); baseline tests + CI (H6/H9); metrics (H10); Whisper chunking if ICP videos need it (H7).
3. **P2:** Per-job temp files → drop global lock (H3/M1); module splits and duplicate cleanup when touching those files (M2/M3/M4).
4. **P3:** Naming/branding pass, readiness probe, CORS tighten with auth (L*).

---

## Audit constraints honored

- No code modified.
- No refactors performed.
- No commits created.
- Report only: `docs/production_health_check.md`

---

*Auditor role: Principal Software Engineer (read-only production readiness review).*  
*Sources: live codebase inspection + `docs/PROJECT.md`, `ai/CURRENT_STATE.md`, `ai/DECISIONS.md`, `ai/RULES.md`.*
