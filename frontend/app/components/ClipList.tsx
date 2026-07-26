"use client";

import { forwardRef, useState } from "react";
import Card from "./Card";
import ClipCard from "./ClipCard";

type ClipListProps = {
  paths: string[] | null | undefined;
};

/** Rough minutes a creator might spend finding, cutting, and captioning one short by hand. */
const ESTIMATED_MINUTES_SAVED_PER_CLIP = 8;

function formatMinutesSaved(minutes: number): string {
  if (minutes < 60) {
    return `~${minutes} min saved`;
  }
  const hours = minutes / 60;
  const rounded =
    hours >= 10 ? Math.round(hours) : Math.round(hours * 10) / 10;
  return `~${rounded} hr saved`;
}

const ClipList = forwardRef<HTMLElement, ClipListProps>(function ClipList(
  { paths },
  ref,
) {
  const clips = paths ?? [];
  const total = clips.length;
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const minutesSaved = total * ESTIMATED_MINUTES_SAVED_PER_CLIP;

  if (total === 0) {
    return (
      <section
        ref={ref}
        id="generated-clips"
        tabIndex={-1}
        className="outline-none"
        aria-label="Generated clips, 0 total"
      >
        <Card className="border-dashed px-6 py-10 sm:px-8">
          <p className="font-[family-name:var(--font-display)] text-2xl text-[var(--ink)]">
            No highlights this time
          </p>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-[var(--muted)]">
            We couldn’t generate clips from this video. Try another YouTube
            link.
          </p>
        </Card>
      </section>
    );
  }

  return (
    <section
      ref={ref}
      id="generated-clips"
      tabIndex={-1}
      className="space-y-8 outline-none sm:space-y-10"
      aria-label={`Generated clips, ${total} total`}
    >
      <header className="space-y-5 rounded-2xl border border-emerald-300/80 bg-gradient-to-br from-emerald-50 to-[var(--surface)] px-6 py-8 sm:px-8 sm:py-10">
        <div className="space-y-2">
          <p className="font-[family-name:var(--font-display)] text-3xl tracking-tight text-[var(--ink)] sm:text-4xl">
            Your clips are ready
          </p>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
            Ready to post
          </p>
        </div>

        <p className="max-w-xl text-base leading-relaxed text-[var(--muted)] sm:text-lg">
          {total === 1
            ? "1 vertical short is ready to preview and download."
            : `${total} vertical shorts are ready to preview and download.`}
        </p>

        <dl className="flex flex-wrap gap-3 pt-1">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)]/90 px-4 py-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Clips
            </dt>
            <dd className="mt-1 font-[family-name:var(--font-display)] text-2xl text-[var(--ink)]">
              {total}
            </dd>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)]/90 px-4 py-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Est. time saved
            </dt>
            <dd className="mt-1 font-[family-name:var(--font-display)] text-2xl text-[var(--ink)]">
              {formatMinutesSaved(minutesSaved)}
            </dd>
          </div>
        </dl>
      </header>

      <div className="space-y-2">
        <h2 className="font-[family-name:var(--font-display)] text-xl text-[var(--ink)]">
          Your shorts
        </h2>
        <p className="text-sm text-[var(--muted)]">
          Preview each vertical clip, then download the ones you want to post.
        </p>
      </div>

      <ul className="grid grid-cols-1 gap-5 sm:gap-6">
        {clips.map((path, index) => (
          <li key={`${index}-${path}`}>
            <ClipCard
              path={path}
              index={index}
              isOpen={openIndex === index}
              onTogglePlay={() =>
                setOpenIndex((current) => (current === index ? null : index))
              }
            />
          </li>
        ))}
      </ul>
    </section>
  );
});

export default ClipList;
