/** Frontend runtime config (Next.js public env). */

function readInt(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

/** Job status poll interval in milliseconds. */
export const POLL_INTERVAL_MS = readInt(
  process.env.NEXT_PUBLIC_POLL_INTERVAL_MS,
  5000,
);
