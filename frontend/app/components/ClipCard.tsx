"use client";

import { useState } from "react";
import Card from "./Card";
import { downloadClip, getClipMediaUrl } from "../lib/api";
import { notify } from "../lib/notify";

type ClipCardProps = {
  path: string;
  index: number;
  isOpen: boolean;
  onTogglePlay: () => void;
};

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
    <Card className="flex flex-col gap-5 px-5 py-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="font-[family-name:var(--font-display)] text-xl text-[var(--ink)]">
            Clip {clipNumber}
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Vertical short · ready to share
          </p>
          {downloadError ? (
            <p className="mt-2 text-sm text-[var(--danger)]" role="alert">
              {downloadError}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={onTogglePlay}
            aria-expanded={isOpen}
            aria-controls={previewRegionId}
            className="min-h-11 rounded-lg border border-[var(--line)] bg-[var(--bg)] px-4 py-2.5 text-sm font-medium text-[var(--ink)] transition hover:border-[var(--accent)] hover:text-[var(--accent)]"
          >
            {isOpen ? "Close preview" : "Preview"}
          </button>
          <button
            type="button"
            onClick={() => {
              void handleDownload();
            }}
            disabled={isDownloading}
            className="min-h-11 rounded-lg border border-[var(--accent)] bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-[var(--accent-ink)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isDownloading ? "Downloading…" : "Download"}
          </button>
        </div>
      </div>

      {isOpen ? (
        <div
          id={previewRegionId}
          className="overflow-hidden rounded-lg border border-[var(--line)] bg-black"
        >
          <video
            key={mediaUrl}
            controls
            playsInline
            preload="metadata"
            aria-label={`Preview of clip ${clipNumber}`}
            className="aspect-[9/16] max-h-[70vh] w-full bg-black object-contain sm:aspect-video sm:max-h-[480px]"
            src={mediaUrl}
          >
            Your browser does not support the video tag.
          </video>
        </div>
      ) : null}
    </Card>
  );
}
