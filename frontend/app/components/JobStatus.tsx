"use client";

import { useEffect, useState } from "react";
import type { Job } from "@/types/job";
import { isTerminalStatus } from "@/types/job";
import { POLL_INTERVAL_MS } from "@/app/lib/config";
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

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

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

export default function JobStatusPanel({
  job,
  lastUpdated,
  isPolling = false,
  connectionWarning = null,
  isRestoring = false,
}: JobStatusProps) {
  const isActive = Boolean(job && !isTerminalStatus(job.status));
  const elapsedSeconds = useElapsedSeconds(job?.created_at ?? null, isActive);

  if (isRestoring && !job) {
    return (
      <Card className="border-dashed">
        <LoadingSpinner label="Restoring previous job…" />
      </Card>
    );
  }

  if (!job) {
    return (
      <Card className="border-dashed text-[var(--muted)]">
        Submit a YouTube URL to start a job.
      </Card>
    );
  }

  const pollSeconds = Math.round(POLL_INTERVAL_MS / 1000);

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Job details</SectionTitle>
        {isPolling ? (
          <LoadingSpinner label={`Checking status every ${pollSeconds}s…`} />
        ) : null}
      </div>

      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
          <dt className="w-28 shrink-0 text-[var(--muted)]">Job ID</dt>
          <dd className="break-all font-mono text-[var(--ink)]">{job.job_id}</dd>
        </div>

        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
          <dt className="w-28 shrink-0 text-[var(--muted)]">Current Status</dt>
          <dd>
            <StatusBadge status={job.status} />
          </dd>
        </div>

        {isActive ? (
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
            <dt className="w-28 shrink-0 text-[var(--muted)]">Elapsed</dt>
            <dd className="font-mono text-[var(--ink)]" aria-live="polite">
              {formatElapsed(elapsedSeconds)}
            </dd>
          </div>
        ) : null}

        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
          <dt className="w-28 shrink-0 text-[var(--muted)]">Last Updated</dt>
          <dd className="text-[var(--ink)]">{formatTimestamp(lastUpdated)}</dd>
        </div>

        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
          <dt className="w-28 shrink-0 text-[var(--muted)]">Created</dt>
          <dd className="text-[var(--ink)]">
            {formatTimestamp(job.created_at)}
          </dd>
        </div>
      </dl>

      {isActive ? (
        <div
          className="mt-4 rounded-md border border-[var(--line)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--ink)]"
          role="status"
          aria-live="polite"
        >
          <p className="font-medium">Analyzing your video…</p>
          <p className="mt-1 text-[var(--muted)]">
            This usually takes 2–5 minutes.
          </p>
        </div>
      ) : null}

      {connectionWarning ? (
        <p
          className="mt-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
          role="status"
          aria-live="polite"
        >
          {connectionWarning}
        </p>
      ) : null}

      {job.status === "failed" && job.error ? (
        <p
          className="mt-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {job.error}
        </p>
      ) : null}

      {job.status === "failed" && !job.error ? (
        <p
          className="mt-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          Processing failed. Please try again.
        </p>
      ) : null}

      {job.status === "completed" ? (
        <p
          className="mt-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900"
          role="status"
          aria-live="polite"
        >
          Ready — {(job.output_clip_paths ?? []).length} clip
          {(job.output_clip_paths ?? []).length === 1 ? "" : "s"} generated.
        </p>
      ) : null}
    </Card>
  );
}
