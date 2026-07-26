/** Client-side YouTube URL helpers — no backend metadata required. */

const ID_PATTERNS = [
  /(?:youtube\.com\/watch\?[^#]*v=)([\w-]{11})/i,
  /(?:youtu\.be\/)([\w-]{11})/i,
  /(?:youtube\.com\/shorts\/)([\w-]{11})/i,
  /(?:youtube\.com\/embed\/)([\w-]{11})/i,
  /(?:youtube\.com\/live\/)([\w-]{11})/i,
];

export function extractYoutubeVideoId(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) return null;
  for (const pattern of ID_PATTERNS) {
    const match = trimmed.match(pattern);
    if (match?.[1]) return match[1];
  }
  return null;
}

/** Public thumbnail derived from the video id in the URL (not a backend field). */
export function youtubeThumbnailUrl(url: string): string | null {
  const id = extractYoutubeVideoId(url);
  if (!id) return null;
  return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
}

export function truncateUrl(url: string, maxLen = 48): string {
  const trimmed = url.trim();
  if (trimmed.length <= maxLen) return trimmed;
  return `${trimmed.slice(0, maxLen - 1)}…`;
}
