# Engineering Rules

> **T-Clipper Operating System (TOS)** — Mandatory rules for every engineer and AI agent.  
> If a request conflicts with these rules, stop and resolve the conflict before coding.  
> These rules override convenience.

---

## Project Understanding

1. You are working on **T-Clipper**, a production-bound SaaS that turns long-form YouTube video into captioned vertical short clips.
2. This is **not** a toy repo. Prefer production-safe behavior over clever demos.
3. The offline pipeline (`backend/services/`) and the HTTP API (`backend/app/`) are intentionally decoupled. Preserve that split.
4. Launch AI is **transcript-first**. Do not invent vision pipelines without an accepted decision in `ai/DECISIONS.md`.
5. Product identity, status, decisions, and rules live in:
   - `docs/PROJECT.md`
   - `ai/CURRENT_STATE.md`
   - `ai/DECISIONS.md`
   - `ai/RULES.md` (this file)

---

## Always Read Before Coding

Before writing or modifying code, read (as applicable):

1. `docs/PROJECT.md` — what the product is and is not
2. `ai/CURRENT_STATE.md` — what works, what is blocked, what is in progress
3. `ai/DECISIONS.md` — constraints you must not silently reverse
4. Relevant module(s) and nearby tests/docs for the change
5. Existing API contracts used by the frontend

**Do not code from memory of similar projects.** Verify against this repository.

---

## Architecture Rules

1. Keep video processing in `backend/services/`; keep HTTP/job orchestration in `backend/app/`.
2. Do not embed FFmpeg/Whisper/yt-dlp business logic inside route handlers.
3. Prefer extending `engine.process_video_to_clips` (or thin adapters) over new orchestration frameworks.
4. Do not introduce queues, workers, databases, or auth systems unless the current session objective explicitly requires it **and** it aligns with accepted decisions.
5. Preserve backward compatibility of public API shapes unless a versioning plan is approved.
6. Frontend remains the Next.js app under `frontend/` unless a superseding ADR exists.
7. Never “fix” reliability problems by rewriting the whole pipeline.

---

## Code Quality Rules

1. **Never rewrite working code** by default. Improve it locally.
2. Keep changes **minimal** and scoped to the requested objective.
3. Match existing style, naming, and patterns in the touched files.
4. Use async/await for I/O-bound work (downloads, API calls, subprocess orchestration patterns already used in-repo).
5. Wrap external API calls and FFmpeg subprocesses in robust error handling with meaningful logs.
6. Do not guess library methods or CLI flags. Verify against docs or installed versions.
7. Do not add temporary scaffolding, dead code, or speculative abstractions “just in case.”
8. Do not add comments that only narrate what the code does; comment non-obvious constraints only.
9. Prefer clear names and small functions over cleverness.
10. Think like a Senior Engineer: readability, operability, and blast-radius control beat novelty.

---

## Debugging Rules

1. **Investigate first.** Reproduce, read logs, inspect inputs/outputs, form a root-cause hypothesis.
2. Always explain the **root cause**, not only the patch.
3. Prefer the smallest fix that addresses the cause.
4. Do not spray unrelated refactors into a bugfix.
5. Add diagnostics only when needed; **remove temporary diagnostics after debugging** unless they are approved permanent observability.
6. Confirm the fix against the failing scenario before declaring done.
7. If production-only (e.g. YouTube bot checks), verify env/cookie/deploy realities—not only local happy paths.

---

## Deployment Rules

1. Assume backend production is **Railway** (`backend/` root) unless superseded.
2. Assume frontend production target is **Vercel** (`frontend/` root) unless superseded.
3. Never commit secrets (`.env`, API keys, `cookies.txt`, base64 cookie blobs).
4. Treat cookie files and `YOUTUBE_COOKIES_*` as credentials.
5. Do not change deploy topology casually (new hosts, builders, or directories) without updating decisions/docs.
6. Prefer config/env fixes over code changes when the defect is configuration.
7. Preserve FFmpeg availability assumptions for caption burn-in and cutting.
8. Prefer production-safe rollouts: additive changes, clear logs, reversible diffs.

---

## Documentation Rules

1. After meaningful sessions, update `ai/CURRENT_STATE.md`.
2. Record important decisions in `ai/DECISIONS.md` **before or immediately when** they are adopted.
3. Do not invent features in docs. Document current truth and clearly labeled future intent.
4. Do not create unsolicited markdown files. Only update TOS/docs when required by the task or explicitly requested.
5. Keep TOS docs professional, structured, and easy for the next agent to skim.
6. If code behavior changes a public contract, update the relevant docs in the same effort when documentation is in scope.

---

## Git Rules

1. Only commit when the user explicitly asks.
2. Never update git config.
3. Never force-push to `main`/`master` unless explicitly requested (and warn if asked).
4. Never commit secrets or credential files.
5. Do not use destructive git operations unless explicitly requested.
6. Keep commits focused; do not bundle unrelated work.
7. Write commit messages that explain **why**, not only what.

---

## Testing Rules

1. Prefer verifying the path you changed (module CLI, API call, or UI flow).
2. For pipeline changes, prefer smallest reproducible fixture/URL path over full speculative suites.
3. Do not claim “tested” without evidence from this environment.
4. When fixing bugs, include a regression check for the failing case when practical.
5. Do not delete or weaken tests to make changes pass.
6. Manual production smoke checks matter for download/CORS/caption paths.

---

## Performance Rules

1. Do not optimize prematurely.
2. Avoid loading entire huge artifacts into memory when streaming/chunking patterns already exist or are required.
3. Respect Whisper size limits; do not silently upload oversized audio.
4. Be mindful of LLM token usage—compress transcripts where the pipeline already does.
5. FFmpeg jobs are expensive: fail fast on bad inputs; do not spawn redundant cuts.
6. Measure before proposing large performance rewrites.

---

## Security Rules

1. **Never expose secrets** in code, logs, screenshots, commits, or client bundles.
2. Do not log full cookie files, Authorization headers, or API keys.
3. Validate and sanitize external inputs (URLs, paths, job IDs) using existing validation patterns.
4. Do not return absolute internal filesystem paths to clients.
5. Preserve CORS allowlisting discipline in production.
6. Treat user-supplied URLs as untrusted input.
7. Do not weaken auth/security controls later once introduced.
8. If a change could enable SSRF, path traversal, or arbitrary file read/write, stop and redesign safely.

---

## Refactoring Rules

1. Refactor only when required to complete the objective safely—or when explicitly requested.
2. No drive-by cleanups, renames, or dependency upgrades.
3. Never rewrite a working module for taste.
4. If a refactor is necessary, keep behavior identical and preserve public contracts.
5. Large refactors require explicit scope and usually an ADR entry.
6. Known debt belongs in `ai/CURRENT_STATE.md`, not as silent opportunistic rewrites.

---

## Definition of Done

A change is done only when all applicable items are true:

1. Requested objective is met—no more, no less.
2. Root cause is understood (for bug fixes).
3. Existing working flows still work (no reckless breakage).
4. Public API/UI contracts remain compatible unless explicitly changed and documented.
5. Secrets are not exposed.
6. Temporary debug code is removed.
7. Errors are handled and logged meaningfully for production diagnosis.
8. `ai/CURRENT_STATE.md` is updated if status meaningfully changed.
9. New durable decisions are recorded in `ai/DECISIONS.md`.
10. You can explain the change clearly to another senior engineer in a few sentences.

---

## General Rules

1. Focus only on the current objective. Do not build future-day features early.
2. Prefer production-safe changes over experimental ones.
3. Do not add temporary code unless requested.
4. Do not leave the codebase noisier than you found it.
5. Ask for clarification when requirements conflict with TOS decisions.
6. If unsure about a library API, verify—do not hallucinate.
7. Always preserve backward compatibility unless an approved breaking change is in scope.
8. Communicate concisely; lead with the outcome and root cause.
9. Agents must follow these rules even when a prompt asks for a shortcut that would violate them.
10. When rules conflict with a user request, explain the conflict and propose a compliant path.

---

## Quick Anti-Patterns (Do Not Do)

- Rewrite `services/` because it “looks messy”
- Add vision models to “fix” gaming clips without an ADR
- Commit `cookies.txt` or `.env`
- Change API response shapes casually
- Leave `DEBUG` prints / temporary files in production paths
- Bundle formatting-only churn with behavioral fixes
- Claim deploy success without checking the actual failure mode (CORS, cookies, FFmpeg, env)

---

*Violations of these rules are defects in process, not cleverness.*
