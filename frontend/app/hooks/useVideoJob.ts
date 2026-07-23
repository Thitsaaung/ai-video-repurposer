"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { getJob, submitVideo } from "@/app/lib/api";
import { POLL_INTERVAL_MS } from "@/app/lib/config";
import {
  clearActiveJobId,
  loadActiveJobId,
  saveActiveJobId,
} from "@/app/lib/jobPersistence";
import { isTerminalStatus, type Job } from "@/types/job";

const MAX_POLL_FAILURES = 3;

export type UseVideoJobResult = {
  job: Job | null;
  jobId: string | null;
  error: string | null;
  connectionWarning: string | null;
  lastUpdated: string | null;
  isSubmitting: boolean;
  isPolling: boolean;
  isBusy: boolean;
  isRestoring: boolean;
  /** Changes when a job newly reaches completed — drives scroll/focus once. */
  resultsFocusToken: string | null;
  submit: (url: string) => Promise<void>;
};

export function useVideoJob(): UseVideoJobResult {
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connectionWarning, setConnectionWarning] = useState<string | null>(
    null,
  );
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [shouldPoll, setShouldPoll] = useState(false);
  const [resultsFocusToken, setResultsFocusToken] = useState<string | null>(
    null,
  );
  const submittingLock = useRef(false);
  const pollFailures = useRef(0);
  const previousStatus = useRef<string | null>(null);
  const warnedConnection = useRef(false);
  const restoreStarted = useRef(false);

  const touchUpdated = useCallback(() => {
    setLastUpdated(new Date().toISOString());
  }, []);

  const applyJob = useCallback(
    (next: Job, options?: { announceCompletion?: boolean }) => {
      const prev = previousStatus.current;
      previousStatus.current = next.status;
      setJob(next);
      touchUpdated();

      if (
        options?.announceCompletion !== false &&
        next.status === "completed" &&
        prev !== null &&
        prev !== "completed"
      ) {
        const count = (next.output_clip_paths ?? []).length;
        toast.success(
          count === 1
            ? "Job completed — 1 clip ready."
            : `Job completed — ${count} clips ready.`,
        );
        setResultsFocusToken(`${next.job_id}:${Date.now()}`);
      }
    },
    [touchUpdated],
  );

  // Restore active job from localStorage after refresh.
  useEffect(() => {
    if (restoreStarted.current) return;
    restoreStarted.current = true;

    let cancelled = false;

    const restore = async () => {
      const storedId = loadActiveJobId();
      if (!storedId) {
        if (!cancelled) setIsRestoring(false);
        return;
      }

      try {
        const restored = await getJob(storedId);
        if (cancelled) return;
        previousStatus.current = restored.status;
        setJobId(restored.job_id);
        applyJob(restored, { announceCompletion: false });
        if (!isTerminalStatus(restored.status)) {
          setShouldPoll(true);
        }
      } catch (err) {
        if (cancelled) return;
        clearActiveJobId();
        const message =
          err instanceof Error ? err.message : "Failed to restore job";
        setError(message);
        toast.error(message);
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    };

    void restore();
    return () => {
      cancelled = true;
    };
  }, [applyJob]);

  useEffect(() => {
    if (!jobId || !shouldPoll) return;

    let cancelled = false;

    const pollOnce = async () => {
      try {
        const next = await getJob(jobId);
        if (cancelled) return;
        pollFailures.current = 0;
        warnedConnection.current = false;
        setConnectionWarning(null);
        applyJob(next);
        if (isTerminalStatus(next.status)) {
          setShouldPoll(false);
        }
      } catch (err) {
        if (cancelled) return;
        pollFailures.current += 1;
        const message =
          err instanceof Error ? err.message : "Failed to fetch job";
        const warning = `${message} (retry ${pollFailures.current}/${MAX_POLL_FAILURES})`;
        setConnectionWarning(warning);

        if (!warnedConnection.current) {
          warnedConnection.current = true;
          toast.warning("Connection issue while checking job status. Retrying…");
        }

        if (pollFailures.current >= MAX_POLL_FAILURES) {
          setError(
            "Lost connection to the API while checking job status. Refresh and try again.",
          );
          toast.error(
            "Lost connection while checking job status. Refresh and try again.",
          );
          setShouldPoll(false);
        }
      }
    };

    void pollOnce();
    const intervalId = setInterval(() => {
      void pollOnce();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [jobId, shouldPoll, applyJob]);

  const submit = useCallback(
    async (url: string) => {
      if (submittingLock.current) return;
      submittingLock.current = true;
      setIsSubmitting(true);
      setShouldPoll(false);
      setError(null);
      setConnectionWarning(null);
      pollFailures.current = 0;
      warnedConnection.current = false;
      previousStatus.current = null;
      setJobId(null);
      setJob(null);
      setLastUpdated(null);
      clearActiveJobId();

      try {
        const created = await submitVideo(url);
        saveActiveJobId(created.job_id);
        setJob(created);
        setJobId(created.job_id);
        previousStatus.current = created.status;
        touchUpdated();
        toast.success("Job submitted — analyzing your video…");
        if (!isTerminalStatus(created.status)) {
          setShouldPoll(true);
        } else if (created.status === "completed") {
          const count = (created.output_clip_paths ?? []).length;
          toast.success(
            count === 1
              ? "Job completed — 1 clip ready."
              : `Job completed — ${count} clips ready.`,
          );
          setResultsFocusToken(`${created.job_id}:${Date.now()}`);
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to submit video";
        setError(message);
        toast.error(message);
      } finally {
        submittingLock.current = false;
        setIsSubmitting(false);
      }
    },
    [touchUpdated],
  );

  const isPolling = shouldPoll;
  const isBusy = isSubmitting || isPolling || isRestoring;

  return {
    job,
    jobId,
    error,
    connectionWarning,
    lastUpdated,
    isSubmitting,
    isPolling,
    isBusy,
    isRestoring,
    resultsFocusToken,
    submit,
  };
}
