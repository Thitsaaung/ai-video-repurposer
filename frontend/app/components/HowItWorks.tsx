import { DownloadIcon, LinkIcon, SparklesIcon } from "./icons";

const STEPS = [
  {
    title: "Paste YouTube Link",
    detail: "Drop in any public video URL.",
    Icon: LinkIcon,
  },
  {
    title: "AI Finds Highlights",
    detail: "We pick the strongest moments for you.",
    Icon: SparklesIcon,
  },
  {
    title: "Download Ready-to-Post Clips",
    detail: "Vertical shorts, ready for social.",
    Icon: DownloadIcon,
  },
] as const;

export default function HowItWorks() {
  return (
    <section
      aria-labelledby="how-it-works-heading"
      className="space-y-8"
    >
      <h2
        id="how-it-works-heading"
        className="font-[family-name:var(--font-display)] text-2xl tracking-tight text-[var(--ink)]"
      >
        How it works
      </h2>

      <ol className="grid grid-cols-1 gap-8 sm:grid-cols-3 sm:gap-6">
        {STEPS.map(({ title, detail, Icon }, index) => (
          <li key={title} className="relative flex gap-4 sm:flex-col sm:gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--surface)] text-[var(--accent)]">
              <Icon className="h-5 w-5" />
            </div>
            <div className="min-w-0 space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">
                Step {index + 1}
              </p>
              <p className="text-base font-semibold leading-snug text-[var(--ink)]">
                {title}
              </p>
              <p className="text-sm leading-relaxed text-[var(--muted)]">
                {detail}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
