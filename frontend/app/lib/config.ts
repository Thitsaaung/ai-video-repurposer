/** Frontend runtime config (Next.js public env). */

function readInt(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function isLocalApiBase(base: string): boolean {
  try {
    const host = new URL(base).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0";
  } catch {
    return false;
  }
}

/**
 * Resolve the FastAPI origin for browser calls.
 *
 * Production (Vercel): set ``NEXT_PUBLIC_API_BASE`` to the Railway HTTPS URL
 * (no trailing slash). Localhost fallback is development-only — production
 * builds fail fast if the env var is missing or points at loopback.
 */
function resolveApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE?.trim();
  const fallback = "http://127.0.0.1:8000";
  const base = (raw || fallback).replace(/\/$/, "");

  if (process.env.NODE_ENV === "production") {
    if (!raw) {
      throw new Error(
        "NEXT_PUBLIC_API_BASE is required for production builds. " +
          "Set it to your Railway HTTPS API URL (e.g. https://your-api.up.railway.app).",
      );
    }
    if (isLocalApiBase(base)) {
      throw new Error(
        `NEXT_PUBLIC_API_BASE must not be a localhost URL in production (got: ${base}). ` +
          "Use your Railway HTTPS API URL.",
      );
    }
    if (!/^https:\/\//i.test(base)) {
      throw new Error(
        `NEXT_PUBLIC_API_BASE must use HTTPS in production (got: ${base}).`,
      );
    }
  }

  return base;
}

export const API_BASE = resolveApiBase();

/** Job status poll interval in milliseconds. */
export const POLL_INTERVAL_MS = readInt(
  process.env.NEXT_PUBLIC_POLL_INTERVAL_MS,
  5000,
);
