# Project

> **T-Clipper Operating System (TOS)** — Product identity document.  
> Read this before writing product, architecture, or feature code.  
> This is internal engineering documentation, not end-user documentation.

---

## Product Name

**T-Clipper**

Internal / repository aliases may still reference “AI Video Repurposer.” Product-facing and operating documents use **T-Clipper**.

---

## Mission

Help creators and content teams turn long-form video into high-quality, platform-ready short clips with minimal manual editing—so they publish more, faster, without sacrificing editorial quality.

---

## Vision

Become the default production system for speech-driven short-form clip creation: reliable download → accurate transcription → intelligent clip selection → vertical captioned export, delivered as a production SaaS with clear APIs, durable jobs, and creator-grade output.

---

## Problem Statement

Creators already have valuable long-form content (podcasts, interviews, education, commentary). Repurposing it for TikTok, YouTube Shorts, and Instagram Reels is slow and repetitive:

- Manual scrubbing for “moments”
- Hand-cutting vertical crops
- Writing and syncing captions
- Inconsistent quality and weak hooks

Most tools either dump low-signal clips, ignore speech structure, or force heavy manual cleanup. Creators lose time; audiences never see the best moments.

---

## Solution

T-Clipper automates the end-to-end clip pipeline:

1. **Ingest** a YouTube URL (yt-dlp)
2. **Transcribe** speech with timestamps (OpenAI Whisper)
3. **Curate** engaging clip windows with an LLM (transcript-first)
4. **Harden** candidates deterministically (boundary snap, duration extend, validate)
5. **Render** 9:16 MP4s with burned-in captions (FFmpeg)

The product prioritizes **excellent clips over filler**, speech-heavy verticals, and production-safe engineering over speculative AI architecture.

---

## Target Users

- Solo creators and small content teams
- Podcast / interview / education producers
- Sports commentary and talk-format channels
- Agencies or freelancers who repurpose client long-form video

Primary workflow: paste a YouTube URL → wait for processing → preview and download vertical clips.

---

## Ideal Customer Profile (ICP)

| Attribute | Profile |
|-----------|---------|
| **Who** | Creator or small team shipping weekly long-form video |
| **Content** | Speech-heavy (podcasts, interviews, tutorials, commentary) |
| **Need** | Consistent short-form output without a full editing bench |
| **Pain** | Hours lost to scrubbing, cropping, and captioning |
| **Buying trigger** | Need to grow Shorts/Reels/TikTok from existing catalog |
| **Not ideal (launch)** | Pure gameplay / visual-only highlights with sparse speech |

---

## Primary User Journey

1. User opens T-Clipper web app
2. Pastes a YouTube URL and submits a job
3. Backend downloads, transcribes, curates, and cuts clips
4. UI shows job progress (queued → processing → complete / failed)
5. User previews captioned 9:16 clips
6. User downloads selected clips for publishing

Success = usable vertical clips with readable burned-in captions and strong spoken hooks—without opening a traditional NLE for the first draft.

---

## Core Features (Current MVP)

| Feature | Status intent |
|---------|----------------|
| YouTube URL ingestion via yt-dlp | Core |
| Whisper transcription with segment timestamps | Core |
| LLM transcript-based clip curation | Core |
| Deterministic clip extend + validation (15–60s) | Core |
| FFmpeg trim → 9:16 center crop → caption burn-in → MP4 | Core |
| FastAPI job API (`process-video`, job status, media) | Core |
| Next.js frontend (submit, poll, preview, download) | Core |
| Railway backend deployment | In progress / operational |
| YouTube cookies support for cloud bot challenges | Operational necessity |

---

## Future Vision

- Auth, billing, and durable job storage (Supabase or equivalent)
- Multi-user workspaces and clip libraries
- Stronger curation quality (prompt and eval loops first)
- Broader source inputs beyond YouTube
- Optional visual understanding for gaming / visual-only moments (explicit product decision required)
- Vercel (or equivalent) production frontend with hardened CORS and observability
- Queue/worker architecture when in-memory jobs are no longer enough

---

## Tech Stack Overview

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js (App Router), React, TypeScript, Tailwind CSS |
| **Backend API** | Python 3.11+, FastAPI |
| **Processing** | yt-dlp, OpenAI Whisper API, LLM curation (OpenAI / optional Anthropic), FFmpeg |
| **Auth / DB (planned)** | Supabase |
| **Backend hosting** | Railway (Railpack; FFmpeg via apt packages) |
| **Frontend hosting** | Vercel (planned / in progress) |
| **AI tooling** | Cursor Pro (implementation IDE); ChatGPT (software architecture partner) |

Processing modules live in `backend/services/` and stay decoupled from HTTP routes in `backend/app/`.

---

## Project Principles

1. **Production-first** — Prefer safe, deployable changes over clever prototypes.
2. **Investigate before changing** — Understand root cause and current contracts before editing.
3. **Minimal safe changes** — Smallest diff that solves the problem; no drive-by rewrites.
4. **Modularity** — Video pipeline ≠ web server; keep them separated.
5. **Quality over quantity** — Fewer strong clips beat padded mediocre sets.
6. **Transcript-first AI (launch)** — Speech drives clip selection until product evidence demands vision.
7. **Deterministic safety nets** — LLM proposes; snap / extend / validate protect duration and bounds.
8. **No hallucinations** — Do not invent APIs, configs, or behaviors; verify against code and docs.
9. **Backward compatibility** — Do not break job/API contracts without an explicit versioning plan.
10. **Secrets stay secret** — Never commit keys, cookies, or credentials.

---

## Non-goals

For the current phase, T-Clipper is **not**:

- A full video editor / NLE replacement
- A social network or publishing scheduler (unless explicitly scoped later)
- A vision-first gaming highlight engine at launch
- A multi-cloud infrastructure science project
- A rewrite of a working pipeline for aesthetic architecture reasons
- User-facing marketing documentation (this TOS is internal)

---

## Success Metrics

| Metric | Intent |
|--------|--------|
| **End-to-end success rate** | URL → usable clips without manual intervention |
| **Clip usefulness** | Creators keep / publish a meaningful share of returned clips |
| **Time-to-clips** | Acceptable latency for MVP job sizes |
| **Caption readability** | Burned-in captions sync and remain legible on mobile |
| **API/frontend reliability** | Jobs complete or fail with clear, actionable errors |
| **Deploy health** | Backend (Railway) and frontend (Vercel when live) stay reachable |

Qualitative bar: a speech-heavy podcast episode should yield several strong vertical clips, not a dump of weak segments.

---

## Design Philosophy

- **One clear job** — Turn long-form speech video into short vertical clips.
- **Honest AI** — Do not fake “viral scores” or over-promise visual understanding.
- **Editor’s instinct in software** — Prefer hooks, clarity, and complete thoughts over arbitrary cuts.
- **Operational clarity** — Logs, errors, and job states must be diagnosable in production.
- **UI as a control surface** — Frontend submits work and presents results; heavy lifting stays in the backend pipeline.

---

## Long-term Business Goal

Build a durable SaaS business around automated, high-trust clip production for speech-driven creators—recurring revenue from teams who depend on T-Clipper as part of their publishing workflow, with quality and reliability as the moat, not feature sprawl.

---

*Document owner: Engineering / Founding team*  
*Audience: Engineers and AI agents working on T-Clipper*
