# T-Score™ — Clip Quality Scoring Design

> **T-Clipper Operating System (TOS)** — Design foundation for explainable clip ranking.  
> **Status:** Design only. Not implemented.  
> **Date:** 2026-07-30  
> **Related:** `docs/04_AI_CURATION.md`, `ai/DECISIONS.md` (transcript-first, quality over quantity)

---

## Purpose

Creators need to know **which clips to post first** and **why**.

Today T-Clipper’s curator emits a single opaque `virality_score` (1–100). That number:

- Is hard to trust (“72 feels made up”)
- Cannot be audited or improved category-by-category
- Mixes editorial judgment with packaging readiness

**T-Score™** is T-Clipper’s explainable clip quality score: a **0–100** overall with transparent category breakdowns, so ranking, UI, and future models share one vocabulary.

**Principles**

1. **Explainable** — every point must map to a named category and reason.  
2. **Speech-first (MVP)** — score what the transcript + clip window can prove; no fake vision.  
3. **Discriminating** — use the full range; do not cluster everything at 70–85.  
4. **Actionable** — low categories tell the creator (or the pipeline) what failed.  
5. **Deterministic core + AI assist** — prefer measurable rules for packaging; use LLM judgment only where editorial taste is required, and always with a text rationale.

---

## 1. Overall score (0–100)

| Field | Definition |
|-------|------------|
| **Name** | **T-Score™** |
| **Range** | Integer **0–100** (display); internal may keep one decimal before rounding |
| **Meaning** | Expected **posting priority** for speech-driven short-form (TikTok / Shorts / Reels), not a guarantee of views |
| **Display** | e.g. `T-Score™ 78` with expandable category bars |

### Band guide (product copy)

| Band | Range | Creator meaning |
|------|------:|-----------------|
| Excellent | 85–100 | Post first; strong hook + complete moment |
| Strong | 70–84 | Solid candidate; minor weaknesses |
| Fair | 55–69 | Usable with caution or light edit |
| Weak | 40–54 | Low priority; usually skip |
| Poor | 0–39 | Do not recommend for publishing |

Bands are **labels**, not hard gates. Ranking uses the numeric score.

### Relationship to current `virality_score`

| Phase | Behavior |
|-------|----------|
| **Now (pre-T-Score)** | LLM `virality_score` + validator sort |
| **T-Score v1** | Compute T-Score™ after curation; **replace ranking key**; optionally keep LLM score as one *input* to Hook/Emotion, not the final number |
| **Migration** | API may expose `t_score` + `t_score_breakdown`; deprecate opaque sole `virality_score` behind compatibility alias when ready |

---

## 2. Score categories

Seven categories. Each is scored **0–100**, then weighted into the overall T-Score™.

| ID | Category | What it measures | Primary signals (MVP) |
|----|----------|------------------|------------------------|
| **H** | **Hook Strength** | Does the first ~1–3s open with a cold, concrete line? | Opening transcript lines; LLM rationale; presence of question / claim / tension |
| **C** | **Completeness** | Is the thought finished (setup → payoff)? | Window covers full phrases; no mid-sentence start/end; duration in sweet band |
| **P** | **Pacing** | Is density right for short-form (not draggy, not chopped)? | Words/sec; pause density; segment count vs duration |
| **E** | **Emotional / Insight Charge** | Surprise, humor, stakes, clear takeaway | Lexical cues + LLM editorial note (bounded) |
| **R** | **Retention Shape** | Likelihood of watch-through (mid-hold + clean exit) | Hook→payoff distance; ending strength; avoids long setup |
| **A** | **Audio / Speech Clarity** | Can captions + speech carry mute viewing? | Transcript confidence proxies (segment length regularity); filler ratio; later: Whisper confidence if available |
| **K** | **Packaging Readiness** | Ready for vertical burn-in without obvious product defects | Duration 15–60s; caption layout health; pad/chrome risk flags |

### Category notes

- **Hook (H)** and **Completeness (C)** are the highest-leverage editorial axes for podcast/interview ICP.  
- **Packaging (K)** is mostly **deterministic** — it should not be “vibes.”  
- **Emotional (E)** is the most subjective; always pair with a one-sentence `reason`.  
- **Vision / gaming** moments are **out of scope for v1** (see roadmap). Incomplete visual highlights should not invent high E/H from silence.

### Sub-signals (normative for implementers later)

#### H — Hook Strength
- Opening line is concrete (not “um”, intros, CTAs)
- Question / bold claim / contrast in first 2 segments
- Matches curator `hook` paraphrase fidelity (optional check)

#### C — Completeness
- Start/end on transcript boundaries (already true post-snap)
- No orphan setup without payoff inside window
- Duration preferably **20–45s** (soft), hard band still **15–60s**

#### P — Pacing
- Target speech rate band for vertical (e.g. ~2.0–3.5 words/sec as soft guide)
- Penalize long silences (large segment gaps) and machine-gun microsegments

#### E — Emotional / Insight Charge
- Detectable punchline, reveal, disagreement, number/stat, confession
- Penalize pure logistics (“as I said earlier”, scheduling talk)

#### R — Retention Shape
- Payoff not delayed past ~70% of clip without interim hooks
- Ending lands (resolution / twist / clear button) rather than trailing filler

#### A — Audio / Speech Clarity
- Low filler ratio (`um`, `uh`, repeated stutters)
- Prefer continuous speech over sparse commentary (gaming caveat: will score mid unless roadmap vision lands)

#### K — Packaging Readiness
- Passes validator duration/bounds
- Caption layout: average ≤3 lines/cue; no pathological cue density
- Flag if editorial pad risks chrome collision (informational)

---

## 3. Weighting

MVP weights (sum = 1.00):

| Category | Weight | Rationale |
|----------|-------:|-----------|
| Hook Strength (H) | **0.22** | Mute scroll; first line decides stop |
| Completeness (C) | **0.18** | Unfinished thoughts kill trust |
| Retention Shape (R) | **0.16** | Watch-through > raw “interesting” |
| Emotional / Insight (E) | **0.14** | Shareability / rewatch |
| Pacing (P) | **0.12** | Short-form feel |
| Packaging Readiness (K) | **0.10** | Product reliability |
| Audio / Speech Clarity (A) | **0.08** | Captions can rescue weak A somewhat |
| **Total** | **1.00** | |

### Weight profile variants (future, not MVP)

| Profile | Shift | Use |
|---------|-------|-----|
| **Growth** | ↑ H, E, R | Aggressive Shorts growth |
| **Education** | ↑ C, P, A | Tutorials / courses |
| **Safe brand** | ↑ C, K, A; ↓ E volatility | Agency / corporate |

MVP ships **one default profile** (table above). Profiles are config, not new scorers.

---

## 4. Formula

### 4.1 Category scores

Each category \(i\) produces \(S_i \in [0, 100]\).

Implementation may compose \(S_i\) from sub-features \(f_{i,j} \in [0, 1]\):

\[
S_i = 100 \times \mathrm{clamp}_{[0,1]}\!\left(\sum_j \alpha_{i,j}\, f_{i,j}\right)
\]

with \(\sum_j \alpha_{i,j} = 1\) per category.

LLM-assisted categories (primarily **H**, **E**, optionally **R**) must return:

- `score` (0–100)
- `reason` (≤140 chars)
- optional `evidence` (quoted transcript snippet)

Deterministic categories (**C**, **P**, **K**, largely **A**) should be rule-based in v1 so scores are reproducible for the same transcript + window.

### 4.2 Overall T-Score™

\[
\mathrm{TScore}_{\mathrm{raw}} = \sum_{i \in \{H,C,P,E,R,A,K\}} w_i \, S_i
\]

\[
\mathrm{TScore} = \mathrm{round}\!\left(\mathrm{clamp}_{[0,100]}(\mathrm{TScore}_{\mathrm{raw}})\right)
\]

With MVP weights:

\[
\begin{aligned}
\mathrm{TScore}_{\mathrm{raw}} =\ &
0.22 S_H + 0.18 S_C + 0.16 S_R + 0.14 S_E \\
&+ 0.12 S_P + 0.10 S_K + 0.08 S_A
\end{aligned}
\]

### 4.3 Optional confidence

\[
\mathrm{Confidence} = \mathrm{round}\!\left(100 \times \frac{\text{deterministic weight mass used}}{\text{total weight}}\right)
\]

Roughly: higher when **C/P/K/A** dominate the outcome; lower when **H/E** LLM judgment drives the rank. Display as secondary (“Confidence 72”) — not part of the 0–100 T-Score™ itself.

### 4.4 Ranking rule

For a job’s clip list:

1. Compute T-Score™ per clip.  
2. Sort descending by T-Score™.  
3. Tie-break: higher **H**, then higher **C**, then longer duration within 20–45s preference, then `clip_id`.  
4. Validator overlap rules still apply **before** final ranking (same as today).

### 4.5 Floor / ceiling policy

- Do **not** force a minimum of 60.  
- Cap individual categories at 100; no “bonus overflow.”  
- If packaging **K < 40**, UI may show a warning chip even if overall is mid — explainable defect.

---

## 5. Explainability

### 5.1 Required payload shape (future API)

```json
{
  "t_score": 78,
  "t_score_band": "strong",
  "t_score_version": "1.0-design",
  "breakdown": {
    "hook": { "score": 86, "weight": 0.22, "contribution": 18.9, "reason": "Opens on a concrete Reader tip, not an intro." },
    "completeness": { "score": 80, "weight": 0.18, "contribution": 14.4, "reason": "Setup and payoff both inside the window." },
    "retention": { "score": 74, "weight": 0.16, "contribution": 11.8, "reason": "Payoff arrives before the final third." },
    "emotion": { "score": 70, "weight": 0.14, "contribution": 9.8, "reason": "Clear pet-peeve energy; mild humor." },
    "pacing": { "score": 76, "weight": 0.12, "contribution": 9.1, "reason": "Steady speech; no long dead air." },
    "packaging": { "score": 82, "weight": 0.10, "contribution": 8.2, "reason": "34s length; caption cues ≤3 lines." },
    "clarity": { "score": 72, "weight": 0.08, "contribution": 5.8, "reason": "Low filler; continuous sentences." }
  },
  "top_strengths": ["hook", "completeness"],
  "top_gaps": ["emotion"],
  "summary": "Strong cold-open tip with a complete payoff; solid post candidate."
}
```

`contribution = weight × score` (shown so creators see **what moved the needle**).

### 5.2 UI patterns (future)

- List row: `T-Score™ 78` + band color.  
- Detail: horizontal bars per category + one-line reason.  
- “Why this rank?”: top 2 strengths + top 1 gap.  
- Never show only a naked number without expand affordance.

### 5.3 Auditability

For any scored clip, logs/artifacts should retain:

- Score version string  
- Category scores + reasons  
- Clip `start_time` / `end_time` / source `video_id`  
- Whether LLM assisted H/E  

This enables offline eval sets and A/B of weights without guessing.

### 5.4 Anti-patterns (forbidden)

- Single LLM call that returns only `78` with no breakdown.  
- Inventing visual scores without frames.  
- Inflating all clips into 80–90.  
- Using T-Score™ as a vanity metric disconnected from ranking.

---

## 6. Future AI scoring roadmap

| Stage | Name | Scope |
|-------|------|--------|
| **S0** | Design (this doc) | Contract + weights + explainability |
| **S1** | Deterministic Packaging + Completeness | Implement **K**, **C**, **P**, baseline **A** from transcript math; keep LLM `virality_score` only as weak prior |
| **S2** | Explainable Hook / Emotion | Structured LLM outputs for **H**, **E**, **R** reasons; blend into T-Score™; replace validator sort key |
| **S3** | Calibration | Human label set (post / skip / love); fit weights; report Spearman vs creator preference |
| **S4** | Multimodal (optional) | Face presence, motion, scene change — **only** after product ADR; gaming path |
| **S5** | Outcome learning | Optional: anonymized post metrics (views/retention) to reweight profiles per niche |

### Guardrails (roadmap)

- Prompt-first improvements remain preferred over new services until S2 is stable (`DEC-003` spirit).  
- Vision stays behind an explicit decision (`DEC-017`).  
- Quality over quantity: T-Score™ should **surface fewer excellent clips**, not inflate weak ones (`DEC-004`).

---

## 7. Example reports

### Example A — Excellent tip clip (podcast / education)

**Clip:** “Safari Reader strips ads so you can focus.” ~34s  

| Category | Score | Reason |
|----------|------:|--------|
| Hook | 88 | Cold open on the tip name and pain (“flooded with ads”). |
| Completeness | 84 | Problem → demo → benefit inside the window. |
| Retention | 80 | Payoff mid-clip; clean close. |
| Emotion | 74 | Relatable annoyance; light humor. |
| Pacing | 78 | Conversational, not sluggish. |
| Packaging | 86 | Duration sweet-spot; captions tidy. |
| Clarity | 80 | Clear diction in transcript. |

\[
\begin{aligned}
\mathrm{TScore} &\approx 0.22\cdot88 + 0.18\cdot84 + 0.16\cdot80 + 0.14\cdot74 \\
&\quad + 0.12\cdot78 + 0.10\cdot86 + 0.08\cdot80 \\
&\approx 81
\end{aligned}
\]

**Band:** Strong / near Excellent  
**Summary:** Post-first candidate — strong hook and complete payoff.  
**Gaps:** Emotion is good, not viral-meme level (acceptable for education).

---

### Example B — Weak intro filler

**Clip:** Channel welcome + “don’t forget to subscribe.” ~22s  

| Category | Score | Reason |
|----------|------:|--------|
| Hook | 28 | Starts with branding/CTA, not a moment. |
| Completeness | 40 | No insight arc. |
| Retention | 30 | Nothing to hold past 3s. |
| Emotion | 25 | Generic. |
| Pacing | 55 | Fine mechanically. |
| Packaging | 70 | Length OK; burn-in fine. |
| Clarity | 75 | Clear speech, empty content. |

\[
\mathrm{TScore} \approx 38
\]

**Band:** Poor  
**Summary:** Do not recommend. Packaging cannot save empty editorial.  
**Gaps:** Hook, retention, emotion.

---

### Example C — Good insight, soft open

**Clip:** Strong takeaway but starts with “So yeah, as I was saying…” ~40s  

| Category | Score | Reason |
|----------|------:|--------|
| Hook | 48 | Soft open; value delayed ~6s. |
| Completeness | 82 | Full argument lands. |
| Retention | 68 | Recovers after slow start. |
| Emotion | 72 | Clear opinionated take. |
| Pacing | 70 | Slightly long setup. |
| Packaging | 80 | Solid length. |
| Clarity | 78 | Clean transcript. |

\[
\mathrm{TScore} \approx 69
\]

**Band:** Fair / Strong edge  
**Summary:** Usable; consider trimming into the punch line for a higher Hook.  
**Gaps:** Hook (actionable: start later).

---

### Example D — High energy, incomplete thought

**Clip:** Loud reaction, ends mid-sentence. ~16s  

| Category | Score | Reason |
|----------|------:|--------|
| Hook | 80 | Instant reaction. |
| Completeness | 35 | Cuts off before payoff. |
| Retention | 40 | Abrupt end feels broken. |
| Emotion | 78 | High charge. |
| Pacing | 72 | Snappy. |
| Packaging | 55 | Short; ending risk. |
| Clarity | 70 | Fine. |

\[
\mathrm{TScore} \approx 58
\]

**Band:** Fair  
**Summary:** Exciting but unfinished — extend or drop.  
**Gaps:** Completeness, retention.

---

## Implementation sketch (non-binding, future)

| Layer | Responsibility |
|-------|----------------|
| `services/t_score.py` (future) | Pure scoring from clip + transcript (+ optional LLM bundle) |
| Curator | May stop owning final rank score; still proposes windows |
| Validator | Overlap/duration gates unchanged; sort by T-Score™ |
| API / UI | Expose `t_score` + `breakdown` |

No code in this document.

---

## Success metrics (when built)

1. Creators agree with top-3 ordering on ≥70% of eval videos (offline study).  
2. Score distribution not collapsed (e.g. stddev meaningful across clips).  
3. Every UI score expandable to category reasons in &lt;1 click.  
4. Deterministic categories bit-stable for identical inputs.

---

## Open decisions (Founder)

1. Keep `virality_score` as alias of T-Score™ vs separate legacy field.  
2. Default weight profile name in product (“Balanced” vs niche profiles at launch).  
3. Whether T-Score™ is shown in Closed Beta UI immediately at S2.  
4. Calibration dataset ownership (internal vs creator panel).

---

*T-Score™ is a T-Clipper product term for explainable clip quality. This design is the foundation for future ranking work.*
