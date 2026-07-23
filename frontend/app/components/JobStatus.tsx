"use client";

import type { Job } from "@/types/job";
import Card from "./Card";
import LoadingSpinner from "./LoadingSpinner";
import SectionTitle from "./SectionTitle";
import StatusBadge from "./StatusBadge";

type JobStatusProps = {
  job: Job | null;
  lastUpdated: string | null;
  isPolling?: boolean;
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
}: JobStatusProps) {
  if (!job) {
    return (
      <Card className="border-dashed text-[var(--muted)]">
        Submit a YouTube URL to start a job.
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Job details</SectionTitle>
        {isPolling ? <LoadingSpinner label="Updating every 5s…" /> : null}
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

      {job.status === "failed" && job.error ? (
        <p className="mt-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {job.error}
        </p>
      ) : null}
    </Card>
  );
}
