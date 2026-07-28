import { CheckIcon } from "./icons";

const BENEFITS = [
  "No editing skills required",
  "Ready for TikTok",
  "Ready for Reels",
  "Ready for Shorts",
] as const;

export default function TrustBenefits() {
  return (
    <section
      aria-label="Why creators use T-Clipper"
      className="border-y border-[var(--line)] py-8 sm:py-10"
    >
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-x-8 sm:gap-y-4">
        {BENEFITS.map((label) => (
          <li
            key={label}
            className="flex items-center gap-3 text-sm text-[var(--ink)] sm:text-base"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--wash)] text-[var(--accent)]">
              <CheckIcon className="h-3.5 w-3.5" />
            </span>
            <span>{label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
