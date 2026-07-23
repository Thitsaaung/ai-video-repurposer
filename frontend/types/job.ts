/** Shared job types for the FastAPI video-repurposer API. */

export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface Job {
  job_id: string;
  status: JobStatus | string;
  url: string;
  created_at: string;
  video_path?: string | null;
  curated_json_path?: string | null;
  output_clip_paths?: string[] | null;
  error?: string | null;
}

/** Response body from POST /api/process-video (same shape as a Job). */
export type ProcessVideoResponse = Job;

export function isJobStatus(value: string): value is JobStatus {
  return (
    value === "queued" ||
    value === "processing" ||
    value === "completed" ||
    value === "failed"
  );
}

export function isTerminalStatus(status: string): boolean {
  return status === "completed" || status === "failed";
}
