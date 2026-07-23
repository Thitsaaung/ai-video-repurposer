/** Path helpers for clip file display (Windows + POSIX). */

export function clipBasename(filePath: string): string {
  const normalized = filePath.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || filePath;
}

/** Prefer a path relative to ``output_clips/`` when present. */
export function clipRelativePath(filePath: string): string {
  const normalized = filePath.replace(/\\/g, "/");
  const lower = normalized.toLowerCase();
  const marker = "output_clips/";
  const index = lower.lastIndexOf(marker);
  if (index >= 0) {
    return normalized.slice(index);
  }
  return clipBasename(filePath);
}
