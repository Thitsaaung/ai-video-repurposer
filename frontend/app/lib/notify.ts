/** Single place for ephemeral user notifications (Sonner). */

import { toast } from "sonner";

export const notify = {
  jobSubmitted(): void {
    toast.success("Started — processing your video…");
  },

  jobCompleted(clipCount: number): void {
    toast.success(
      clipCount === 1
        ? "Your clip is ready."
        : `Your clips are ready — ${clipCount} shorts.`,
    );
  },

  connectionRetry(): void {
    toast.warning("Connection issue while checking job status. Retrying…");
  },

  downloadStarted(): void {
    toast.message("Download started…");
  },
};
