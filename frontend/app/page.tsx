"use client";

import { useEffect, useRef } from "react";
import ClipList from "./components/ClipList";
import JobStatusPanel from "./components/JobStatus";
import LoadingSpinner from "./components/LoadingSpinner";
import VideoForm from "./components/VideoForm";
import { useVideoJob } from "./hooks/useVideoJob";
import { notify } from "./lib/notify";

export default function HomePage() {
  const {
    job,
    error,
    connectionWarning,
    lastUpdated,
    isSubmitting,
    isPolling,
    isBusy,
    isRestoring,
    notice,
    submit,
  } = useVideoJob();

  const resultsRef = useRef<HTMLElement | null>(null);
  const handledNoticeId = useRef<number | null>(null);

  // Page owns notification + scroll/focus side effects from lifecycle notices.
  useEffect(() => {
    if (!notice) return;
    if (handledNoticeId.current === notice.id) return;
    handledNoticeId.current = notice.id;

    if (notice.type === "submitted") {
      notify.jobSubmitted();
      return;
    }

    if (notice.type === "connection_retry") {
      notify.connectionRetry();
      return;
    }

    if (notice.type === "completed") {
      notify.jobCompleted(notice.clipCount);

      const frame = window.requestAnimationFrame(() => {
        const target = resultsRef.current;
        if (!target) return;
        const prefersReducedMotion = window.matchMedia(
          "(prefers-reduced-motion: reduce)",
        ).matches;
        target.scrollIntoView({
          behavior: prefersReducedMotion ? "auto" : "smooth",
          block: "start",
        });
        target.focus({ preventScroll: true });
      });

      return () => window.cancelAnimationFrame(frame);
    }
  }, [notice]);

  return (
    <main className="relative min-h-screen overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--wash)_0%,_transparent_55%),linear-gradient(160deg,_var(--bg)_0%,_var(--bg-deep)_100%)]"
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center gap-8 px-6 py-16">
        <header>
          <h1 className="font-[family-name:var(--font-display)] text-4xl tracking-tight text-[var(--ink)] sm:text-5xl">
            AI Video Repurposer
          </h1>
          <p className="mt-3 max-w-xl text-base text-[var(--muted)] sm:text-lg">
            Paste a YouTube URL to generate short vertical clips automatically.
          </p>
        </header>

        <VideoForm onSubmit={submit} disabled={isBusy} />

        {isSubmitting ? <LoadingSpinner label="Submitting video…" /> : null}

        {error ? (
          <p
            className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        <JobStatusPanel
          job={job}
          lastUpdated={lastUpdated}
          isPolling={isPolling}
          connectionWarning={connectionWarning}
          isRestoring={isRestoring}
        />

        {job?.status === "completed" ? (
          <ClipList ref={resultsRef} paths={job.output_clip_paths} />
        ) : null}
      </div>
    </main>
  );
}
