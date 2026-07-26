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

/**
 * Human title from cutter filenames like ``clip_1_Solis_Magic.mp4``.
 * Falls back to ``Highlight #N`` when the slug is missing.
 */
export function clipTitleFromPath(
  filePath: string,
  fallbackIndex?: number,
): string {
  const base = clipBasename(filePath);
  const withoutExt = base.replace(/\.[^.]+$/u, "");
  const match = /^clip_\d+_(.+)$/iu.exec(withoutExt);
  const slug = (match?.[1] ?? withoutExt).trim();

  const titled = slug
    .replace(/_+/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();

  if (titled && !/^clip\s*\d*$/iu.test(titled)) {
    return titled;
  }

  if (fallbackIndex != null && fallbackIndex >= 0) {
    return `Highlight #${fallbackIndex + 1}`;
  }
  return "Highlight";
}
