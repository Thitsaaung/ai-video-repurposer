/** Single place for ephemeral user notifications (Sonner). */

import { toast } from "sonner";

export const notify = {
  jobSubmitted(): void {
    toast.success("Job submitted — analyzing your video…");
  },

  jobCompleted(clipCount: number): void {
    toast.success(
      clipCount === 1
        ? "Job completed — 1 clip ready."
        : `Job completed — ${clipCount} clips ready.`,
    );
  },

  connectionRetry(): void {
    toast.warning("Connection issue while checking job status. Retrying…");
  },

  downloadStarted(): void {
    toast.message("Download started…");
  },
};
