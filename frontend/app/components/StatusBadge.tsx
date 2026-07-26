"use client";

import type { JobStatus } from "@/types/job";
import { isJobStatus } from "@/types/job";

type StatusBadgeProps = {
  status: string;
};

const BADGE_STYLES: Record<JobStatus, string> = {
  queued: "bg-stone-200 text-stone-800 border-stone-400",
  processing: "bg-blue-100 text-blue-900 border-blue-400",
  completed: "bg-green-100 text-green-900 border-green-400",
  failed: "bg-red-100 text-red-900 border-red-400",
};

const LABELS: Record<JobStatus, string> = {
  queued: "In queue",
  processing: "In progress",
  completed: "Ready",
  failed: "Failed",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const known = isJobStatus(status) ? status : null;
  const className = known
    ? BADGE_STYLES[known]
    : "bg-stone-100 text-stone-700 border-stone-300";
  const label = known ? LABELS[known] : status;

  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-sm font-semibold capitalize ${className}`}
    >
      {label}
    </span>
  );
}
