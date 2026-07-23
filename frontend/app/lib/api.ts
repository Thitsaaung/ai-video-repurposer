/** FastAPI client — single place for backend HTTP calls. */

import type { Job, ProcessVideoResponse } from "@/types/job";
import { clipBasename } from "./clipPaths";

export const API_BASE = "http://127.0.0.1:8000";

async function parseError(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof (data as { detail: unknown }).detail === "string"
    ) {
      return (data as { detail: string }).detail;
    }
    return JSON.stringify(data);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

/** Public URL for a generated clip served by FastAPI StaticFiles (preview). */
export function getClipMediaUrl(filePathOrName: string): string {
  const filename = clipBasename(filePathOrName);
  return `${API_BASE}/media/clips/${encodeURIComponent(filename)}`;
}

/** Attachment URL for downloading a clip. */
export function getClipDownloadUrl(filePathOrName: string): string {
  const filename = clipBasename(filePathOrName);
  return `${API_BASE}/media/download/${encodeURIComponent(filename)}`;
}

/**
 * Download a clip without navigating away.
 * Fetches as a blob (cross-origin safe) and triggers a same-tab save dialog.
 */
export async function downloadClip(filePathOrName: string): Promise<void> {
  const filename = clipBasename(filePathOrName);
  const response = await fetch(getClipDownloadUrl(filename));

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/** POST /api/process-video — enqueue a YouTube URL for processing. */
export async function submitVideo(url: string): Promise<ProcessVideoResponse> {
  const response = await fetch(`${API_BASE}/api/process-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<ProcessVideoResponse>;
}

/** GET /api/jobs/{jobId} — fetch current job state. */
export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(
    `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`,
  );

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<Job>;
}
