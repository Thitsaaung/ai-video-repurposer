"use client";

import { useEffect, useState } from "react";
import type { Job } from "@/types/job";
import { isTerminalStatus } from "@/types/job";
import {
  truncateUrl,
  youtubeThumbnailUrl,
} from "@/app/lib/youtube";
import Card from "./Card";
import LoadingSpinner from "./LoadingSpinner";
import SectionTitle from "./SectionTitle";
import StatusBadge from "./StatusBadge";

type JobStatusProps = {
  job: Job | null;
  lastUpdated: string | null;
  isPolling?: boolean;
  connectionWarning?: string | null;
  isRestoring?: boolean;
};

/** Honest overview of the pipeline — not live stage tracking. */
const PROCESS_STEPS = [
  "Downloading your video…",
  "Listening to the audio…",
  "Finding the best moments…",
  "Creating your short clips…",
] as const;

function formatElapsed(totalSeconds: number): string {
  const safe = Math.max(0, totalSeconds);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function useElapsedSeconds(startedAt: string | null, active: boolean): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active || !startedAt) {
      setElapsed(0);
      return;
    }

    const startMs = new Date(startedAt).getTime();
    if (Number.isNaN(startMs)) {
      setElapsed(0);
      return;
    }

    const tick = () => {
      setElapsed(Math.floor((Date.now() - startMs) / 1000));
    };

    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [startedAt, active]);

  return elapsed;
}

function VideoIdentity({ url }: { url: string }) {
  const thumbnail = youtubeThumbnailUrl(url);
  // Title is not in the job payload yet — show URL until backend ships metadata.
  const label = truncateUrl(url);

  return (
    <div className="flex items-center gap-4">
      {thumbnail ? (
        // eslint-disable-next-line @next/next/no-img-element -- external YouTube CDN thumb
        <img
          src={thumbnail}
          alt=""
          width={160}
          height={90}
          className="h-[4.5rem] w-32 shrink-0 rounded-md object-cover shadow-sm ring-1 ring-[var(--line)]"
        />
      ) : (
        <div
          aria-hidden
          className="flex h-[4.5rem] w-32 shrink-0 items-center justify-center rounded-md bg-[var(--bg-deep)] text-xs text-[var(--muted)] ring-1 ring-[var(--line)]"
        >
          YouTube
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          Your video
        </p>
        <p
          className="mt-1.5 text-base font-medium leading-snug text-[var(--ink)]"
          title={url}
        >
          {label}
        </p>
      </div>
    </div>
  );
}

export default function JobStatusPanel({
  job,
  lastUpdated: _lastUpdated,
  isPolling: _isPolling = false,
  connectionWarning = null,
  isRestoring = false,
}: JobStatusProps) {
  const isActive = Boolean(job && !isTerminalStatus(job.status));
  const elapsedSeconds = useElapsedSeconds(job?.created_at ?? null, isActive);

  if (isRestoring && !job) {
    return (
      <Card className="border-dashed px-6 py-10">
        <LoadingSpinner label="Restoring your session…" />
      </Card>
    );
  }

  if (!job) {
    return (
      <Card className="border-dashed px-6 py-10 text-[var(--muted)]">
        <p className="text-lg text-[var(--ink)]">Ready when you are</p>
        <p className="mt-3 max-w-md text-sm leading-relaxed">
          Paste a YouTube link above and we’ll create short vertical clips you
          can preview and download.
        </p>
      </Card>
    );
  }

  const clipCount = (job.output_clip_paths ?? []).length;
  const videoUrl = (job.url || "").trim();

  // —— Processing: premium wait experience ——
  if (isActive) {
    return (
      <Card className="relative overflow-hidden px-6 py-10 sm:px-10 sm:py-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-[var(--accent)]/20"
        >
          <div className="processing-breathe-bar mx-auto h-full w-2/3 rounded-full bg-[var(--accent)]" />
        </div>

        <div className="flex items-center justify-between gap-4">
          <p className="text-sm font-medium text-[var(--muted)]">
            {job.status === "queued" ? "In queue" : "In progress"}
          </p>
          <span className="inline-flex items-center gap-2 text-sm text-[var(--accent)]">
            <span
              aria-hidden
              className="processing-glow-dot h-2 w-2 rounded-full bg-[var(--accent)]"
            />
            Working
          </span>
        </div>

        <div className="mt-10 text-center" role="status" aria-live="polite">
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
            Elapsed time
          </p>
          <p className="mt-3 font-mono text-5xl tracking-tight text-[var(--ink)] sm:text-6xl">
            {formatElapsed(elapsedSeconds)}
          </p>
          <p className="mx-auto mt-5 max-w-sm text-base leading-relaxed text-[var(--muted)]">
            {elapsedSeconds >= 5 * 60
              ? "Still working — larger videos can take longer."
              : "This usually takes 2–5 minutes."}
          </p>
        </div>

        {videoUrl ? (
          <div className="mt-12 rounded-xl border border-[var(--line)] bg-[var(--bg)]/80 px-4 py-4 sm:px-5">
            <VideoIdentity url={videoUrl} />
          </div>
        ) : null}

        <div className="mt-12">
          <p className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">
            What we’re doing
          </p>
          <ol className="mt-6 space-y-5">
            {PROCESS_STEPS.map((step) => (
              <li
                key={step}
                className="flex items-center gap-4 text-base text-[var(--ink)]"
              >
                <span
                  aria-hidden
                  className="processing-glow-dot h-2 w-2 shrink-0 rounded-full bg-[var(--accent)]"
                />
                <span className="leading-snug">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        {connectionWarning ? (
          <p
            className="mt-10 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            role="status"
            aria-live="polite"
          >
            Connection issue — retrying automatically.
          </p>
        ) : null}
      </Card>
    );
  }

  // —— Completed / failed ——
  return (
    <Card className="px-6 py-8 sm:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <SectionTitle>
          {job.status === "completed" ? "Complete" : "Something went wrong"}
        </SectionTitle>
        <StatusBadge status={job.status} />
      </div>

      {videoUrl ? (
        <div className="mt-8 rounded-xl border border-[var(--line)] bg-[var(--bg)]/80 px-4 py-4 sm:px-5">
          <VideoIdentity url={videoUrl} />
        </div>
      ) : null}

      {job.status === "failed" && job.error ? (
        <p
          className="mt-8 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          {job.error}
        </p>
      ) : null}

      {job.status === "failed" && !job.error ? (
        <p
          className="mt-8 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          Something went wrong while processing. Please try again with another
          video.
        </p>
      ) : null}

      {job.status === "completed" ? (
        <div
          className="mt-8 rounded-xl border border-emerald-300 bg-emerald-50 px-5 py-6"
          role="status"
          aria-live="polite"
        >
          <p className="font-[family-name:var(--font-display)] text-2xl text-emerald-950">
            Your clips are ready
          </p>
          <p className="mt-2 text-sm leading-relaxed text-emerald-900">
            {clipCount === 0
              ? "No clips were generated for this video."
              : clipCount === 1
                ? "1 short clip is ready to preview and download below."
                : `${clipCount} short clips are ready to preview and download below.`}
          </p>
        </div>
      ) : null}
    </Card>
  );
}
