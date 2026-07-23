"use client";

type LoadingSpinnerProps = {
  label?: string;
  className?: string;
};

export default function LoadingSpinner({
  label = "Loading…",
  className = "",
}: LoadingSpinnerProps) {
  return (
    <div
      className={`inline-flex items-center gap-3 text-[var(--muted)] ${className}`}
      role="status"
      aria-live="polite"
    >
      <span
        className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[var(--line)] border-t-[var(--accent)]"
        aria-hidden
      />
      <span className="text-sm">{label}</span>
    </div>
  );
}
