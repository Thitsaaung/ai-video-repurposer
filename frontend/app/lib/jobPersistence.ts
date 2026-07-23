/** Persist the active job ID so polling can resume after refresh. */

const STORAGE_KEY = "avr:activeJobId";

export function loadActiveJobId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && value.trim() ? value.trim() : null;
  } catch {
    return null;
  }
}

export function saveActiveJobId(jobId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, jobId);
  } catch {
    // Ignore quota / private-mode failures; session still works in-memory.
  }
}

export function clearActiveJobId(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
}
