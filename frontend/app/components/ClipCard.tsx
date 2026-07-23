"use client";

import { useState } from "react";
import { toast } from "sonner";
import Card from "./Card";
import { downloadClip, getClipMediaUrl } from "../lib/api";
import { clipBasename, clipRelativePath } from "../lib/clipPaths";

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
  const filename = clipBasename(path);
  const relative = clipRelativePath(path);
  const clipNumber = index + 1;
  const mediaUrl = getClipMediaUrl(path);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDownload = async () => {
    if (isDownloading) return;
    setDownloadError(null);
    setIsDownloading(true);
    toast.message("Download started…");
    try {
      await downloadClip(path);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Download failed";
      setDownloadError(message);
      toast.error(message);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Clip {clipNumber}
          </p>
          <p
            className="truncate text-base font-medium text-[var(--ink)]"
            title={filename}
          >
            {filename}
          </p>
          <p
            className="break-all font-mono text-xs text-[var(--muted)]"
            title={path}
          >
            {relative}
          </p>
          {downloadError ? (
            <p className="text-sm text-[var(--danger)]" role="alert">
              {downloadError}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={onTogglePlay}
            aria-expanded={isOpen}
            className="rounded-md border border-[var(--line)] bg-[var(--bg)] px-3 py-2 text-sm font-medium text-[var(--ink)] transition hover:border-[var(--accent)] hover:text-[var(--accent)]"
          >
            {isOpen ? "Close" : "Play"}
          </button>
          <button
            type="button"
            onClick={() => {
              void handleDownload();
            }}
            disabled={isDownloading}
            className="rounded-md border border-[var(--accent)] bg-[var(--accent)] px-3 py-2 text-sm font-medium text-[var(--accent-ink)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isDownloading ? "Downloading…" : "Download"}
          </button>
        </div>
      </div>

      {isOpen ? (
        <div className="overflow-hidden rounded-md border border-[var(--line)] bg-black">
          <video
            key={mediaUrl}
            controls
            playsInline
            preload="metadata"
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
