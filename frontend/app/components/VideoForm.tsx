"use client";

type VideoFormProps = {
  onSubmit: (url: string) => void;
  disabled?: boolean;
};

export default function VideoForm({
  onSubmit,
  disabled = false,
}: VideoFormProps) {
  return (
    <form
      className="flex w-full flex-col gap-3 sm:flex-row sm:items-stretch"
      onSubmit={(event) => {
        event.preventDefault();
        if (disabled) return;
        const formData = new FormData(event.currentTarget);
        const url = String(formData.get("url") ?? "").trim();
        if (!url) return;
        onSubmit(url);
      }}
    >
      <label className="sr-only" htmlFor="youtube-url">
        YouTube URL
      </label>
      <input
        id="youtube-url"
        name="url"
        type="url"
        required
        disabled={disabled}
        placeholder="https://www.youtube.com/watch?v=..."
        className="min-w-0 flex-1 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-[var(--ink)] outline-none ring-[var(--accent)] placeholder:text-[var(--muted)] focus:ring-2 disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={disabled}
        className="rounded-lg bg-[var(--accent)] px-5 py-3 font-medium text-[var(--accent-ink)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {disabled ? "Working…" : "Generate Clips"}
      </button>
    </form>
  );
}
