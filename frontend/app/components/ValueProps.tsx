const VALUE_PROPS = [
  "Save hours of editing",
  "Ready for TikTok, Reels & Shorts",
  "AI finds the best highlights",
] as const;

export default function ValueProps() {
  return (
    <ul
      aria-label="Why T-Clipper"
      className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-[var(--muted)] sm:gap-x-6"
    >
      {VALUE_PROPS.map((label) => (
        <li key={label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="h-1 w-1 shrink-0 rounded-full bg-[var(--accent)]"
          />
          <span>{label}</span>
        </li>
      ))}
    </ul>
  );
}
