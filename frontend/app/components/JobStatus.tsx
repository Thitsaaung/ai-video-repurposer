"use client";

import type { Job } from "@/types/job";
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
};

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function JobStatusPanel({
  job,
  lastUpdated,
  isPolling = false,
  connectionWarning = null,
}: JobStatusProps) {
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

      {connectionWarning ? (
        <p className="mt-4 text-sm text-amber-800" role="status">
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

      {job.status === "completed" ? (
        <p className="mt-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Ready — {(job.output_clip_paths ?? []).length} clip
          {(job.output_clip_paths ?? []).length === 1 ? "" : "s"} generated.
        </p>
      ) : null}
    </Card>
  );
}
