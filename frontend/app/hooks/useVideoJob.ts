"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getJob, submitVideo } from "@/app/lib/api";
import { POLL_INTERVAL_MS } from "@/app/lib/config";
import {
  clearActiveJobId,
  loadActiveJobId,
  saveActiveJobId,
} from "@/app/lib/jobPersistence";
import { isTerminalStatus, type Job } from "@/types/job";

const MAX_POLL_FAILURES = 3;

/** One-shot lifecycle signals for the page to turn into UI side effects. */
export type JobNotice =
  | { id: number; type: "submitted" }
  | { id: number; type: "completed"; clipCount: number }
  | { id: number; type: "connection_retry" };

type JobNoticeInput =
  | { type: "submitted" }
  | { type: "completed"; clipCount: number }
  | { type: "connection_retry" };

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
  notice: JobNotice | null;
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
  const [notice, setNotice] = useState<JobNotice | null>(null);
  const submittingLock = useRef(false);
  const pollFailures = useRef(0);
  const previousStatus = useRef<string | null>(null);
  const warnedConnection = useRef(false);
  const restoreStarted = useRef(false);
  const noticeId = useRef(0);

  const emitNotice = useCallback((next: JobNoticeInput) => {
    noticeId.current += 1;
    setNotice({ ...next, id: noticeId.current });
  }, []);

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
        emitNotice({
          type: "completed",
          clipCount: (next.output_clip_paths ?? []).length,
        });
      }
    },
    [emitNotice, touchUpdated],
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
        // Hard failure: inline alert only (no toast duplicate).
        setError(
          err instanceof Error ? err.message : "Failed to restore job",
        );
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
        setConnectionWarning(
          `${message} (retry ${pollFailures.current}/${MAX_POLL_FAILURES})`,
        );

        if (!warnedConnection.current) {
          warnedConnection.current = true;
          emitNotice({ type: "connection_retry" });
        }

        if (pollFailures.current >= MAX_POLL_FAILURES) {
          // Hard failure: inline alert only (no toast duplicate).
          setError(
            "Lost connection to the API while checking job status. Refresh and try again.",
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
  }, [jobId, shouldPoll, applyJob, emitNotice]);

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

        if (!isTerminalStatus(created.status)) {
          emitNotice({ type: "submitted" });
          setShouldPoll(true);
        } else if (created.status === "completed") {
          emitNotice({
            type: "completed",
            clipCount: (created.output_clip_paths ?? []).length,
          });
        }
      } catch (err) {
        // Hard failure: inline alert only (no toast duplicate).
        setError(
          err instanceof Error ? err.message : "Failed to submit video",
        );
      } finally {
        submittingLock.current = false;
        setIsSubmitting(false);
      }
    },
    [emitNotice, touchUpdated],
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
    notice,
    submit,
  };
}
