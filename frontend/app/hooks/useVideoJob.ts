"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getJob, submitVideo } from "@/app/lib/api";
import { POLL_INTERVAL_MS } from "@/app/lib/config";
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
  const [shouldPoll, setShouldPoll] = useState(false);
  const submittingLock = useRef(false);
  const pollFailures = useRef(0);

  const touchUpdated = useCallback(() => {
    setLastUpdated(new Date().toISOString());
  }, []);

  useEffect(() => {
    if (!jobId || !shouldPoll) return;

    let cancelled = false;

    const pollOnce = async () => {
      try {
        const next = await getJob(jobId);
        if (cancelled) return;
        pollFailures.current = 0;
        setConnectionWarning(null);
        setJob(next);
        touchUpdated();
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
        if (pollFailures.current >= MAX_POLL_FAILURES) {
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
  }, [jobId, shouldPoll, touchUpdated]);

  const submit = useCallback(
    async (url: string) => {
      if (submittingLock.current) return;
      submittingLock.current = true;
      setIsSubmitting(true);
      setShouldPoll(false);
      setError(null);
      setConnectionWarning(null);
      pollFailures.current = 0;
      setJobId(null);
      setJob(null);
      setLastUpdated(null);

      try {
        const created = await submitVideo(url);
        setJob(created);
        setJobId(created.job_id);
        touchUpdated();
        if (!isTerminalStatus(created.status)) {
          setShouldPoll(true);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit video");
      } finally {
        submittingLock.current = false;
        setIsSubmitting(false);
      }
    },
    [touchUpdated],
  );

  const isPolling = shouldPoll;
  const isBusy = isSubmitting || isPolling;

  return {
    job,
    jobId,
    error,
    connectionWarning,
    lastUpdated,
    isSubmitting,
    isPolling,
    isBusy,
    submit,
  };
}
