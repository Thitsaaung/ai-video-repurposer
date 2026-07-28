/** Shared job types for the FastAPI video-repurposer API. */

export type JobStatus = "queued" | "processing" | "completed" | "failed";

/** Optional progress detail while status === "processing". */
export type ProcessingStage =
  | "downloading"
  | "transcribing"
  | "curating"
  | "creating_clips";

export interface Job {
  job_id: string;
  status: JobStatus | string;
  url: string;
  created_at: string;
  video_path?: string | null;
  curated_json_path?: string | null;
  output_clip_paths?: string[] | null;
  error?: string | null;
  stage?: string | null;
}

/** Response body from POST /api/process-video (same shape as a Job). */
export type ProcessVideoResponse = Job;

const PROCESSING_STAGES: readonly ProcessingStage[] = [
  "downloading",
  "transcribing",
  "curating",
  "creating_clips",
] as const;

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

export function isProcessingStage(
  value: string | null | undefined,
): value is ProcessingStage {
  return (
    typeof value === "string" &&
    (PROCESSING_STAGES as readonly string[]).includes(value)
  );
}
