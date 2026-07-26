"use client";

import { useEffect, useState } from "react";
import { downloadClip, getClipMediaUrl } from "../lib/api";
import { notify } from "../lib/notify";
import { CloseIcon, DownloadIcon, PlayIcon } from "./icons";

type ClipCardProps = {
  path: string;
  index: number;
  isOpen: boolean;
  onTogglePlay: () => void;
};

function formatClipDuration(totalSeconds: number): string {
  const safe = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default function ClipCard({
  path,
  index,
  isOpen,
  onTogglePlay,
}: ClipCardProps) {
  const clipNumber = index + 1;
  const mediaUrl = getClipMediaUrl(path);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [durationSec, setDurationSec] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const video = document.createElement("video");
    video.preload = "metadata";
    video.src = mediaUrl;

    const onMeta = () => {
      if (
        cancelled ||
        !Number.isFinite(video.duration) ||
        video.duration <= 0
      ) {
        return;
      }
      setDurationSec(video.duration);
    };

    video.addEventListener("loadedmetadata", onMeta);
    return () => {
      cancelled = true;
      video.removeEventListener("loadedmetadata", onMeta);
      video.removeAttribute("src");
      video.load();
    };
  }, [mediaUrl]);

  const handleDownload = async () => {
    if (isDownloading) return;
    setDownloadError(null);
    setIsDownloading(true);
    notify.downloadStarted();
    try {
      await downloadClip(path);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Download failed";
      setDownloadError(message);
    } finally {
      setIsDownloading(false);
    }
  };

  const previewRegionId = `clip-preview-${clipNumber}`;

  return (
    <article
      className={`group rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-5 py-6 shadow-sm transition duration-300 ease-out sm:px-7 sm:py-7 ${
        isOpen
          ? "shadow-md ring-1 ring-[var(--accent)]/25"
          : "hover:-translate-y-0.5 hover:border-[var(--accent)]/35 hover:shadow-md"
      }`}
    >
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-3">
          <p className="font-[family-name:var(--font-display)] text-2xl tracking-tight text-[var(--ink)] sm:text-[1.75rem]">
            Highlight #{clipNumber}
          </p>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-[var(--muted)]">
            {durationSec != null ? (
              <>
                <span className="font-medium text-[var(--ink)]">
                  {formatClipDuration(durationSec)}
                </span>
                <span aria-hidden className="text-[var(--line)]">
                  ·
                </span>
              </>
            ) : null}
            <span>Vertical · Ready to Post</span>
          </div>

          {downloadError ? (
            <p className="text-sm text-[var(--danger)]" role="alert">
              {downloadError}
            </p>
          ) : null}
        </div>

        <div className="flex w-full shrink-0 flex-col gap-2.5 sm:w-auto sm:flex-row">
          <button
            type="button"
            onClick={onTogglePlay}
            aria-expanded={isOpen}
            aria-controls={previewRegionId}
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--bg)] px-5 py-3 text-sm font-semibold text-[var(--ink)] transition duration-200 hover:border-[var(--accent)] hover:bg-[var(--wash)]/50 hover:text-[var(--accent)] active:scale-[0.98]"
          >
            {isOpen ? (
              <>
                <CloseIcon className="h-4 w-4" />
                Close
              </>
            ) : (
              <>
                <PlayIcon className="h-4 w-4" />
                Preview
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => {
              void handleDownload();
            }}
            disabled={isDownloading}
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-[var(--accent-ink)] transition duration-200 hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <DownloadIcon className="h-4 w-4" />
            {isDownloading ? "Downloading…" : "Download"}
          </button>
        </div>
      </div>

      {isOpen ? (
        <div
          id={previewRegionId}
          className="mt-6 overflow-hidden rounded-2xl border border-[var(--line)] bg-black shadow-inner transition duration-300"
        >
          <video
            key={mediaUrl}
            controls
            playsInline
            preload="metadata"
            aria-label={`Preview of highlight ${clipNumber}`}
            className="aspect-[9/16] max-h-[70vh] w-full bg-black object-contain sm:aspect-video sm:max-h-[520px]"
            src={mediaUrl}
          >
            Your browser does not support the video tag.
          </video>
        </div>
      ) : null}
    </article>
  );
}
