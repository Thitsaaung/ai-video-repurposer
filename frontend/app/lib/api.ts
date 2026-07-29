/** FastAPI client — single place for backend HTTP calls. */

import type { Job, ProcessVideoResponse } from "@/types/job";
import { clipBasename } from "./clipPaths";
import { API_BASE } from "./config";

export { API_BASE };

function friendlyNetworkError(err: unknown): Error {
  if (err instanceof TypeError) {
    return new Error(
      "Cannot reach the API. Is the FastAPI server running on the configured API base?",
    );
  }
  if (err instanceof Error) return err;
  return new Error("Unexpected network error");
}

async function parseError(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (typeof data !== "object" || data === null || !("detail" in data)) {
      return response.statusText || `HTTP ${response.status}`;
    }

    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (
            typeof item === "object" &&
            item !== null &&
            "msg" in item &&
            typeof (item as { msg: unknown }).msg === "string"
          ) {
            return (item as { msg: string }).msg;
          }
          return null;
        })
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) return messages.join("; ");
    }

    return JSON.stringify(detail);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (err) {
    throw friendlyNetworkError(err);
  }
}

/** Public URL for a generated clip (authenticated ``/media/clips`` route). */
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
  const response = await apiFetch(getClipDownloadUrl(filename));

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
  const response = await apiFetch(`${API_BASE}/api/process-video`, {
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
  const response = await apiFetch(
    `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`,
  );

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<Job>;
}
