"use client";

import { forwardRef, useState } from "react";
import Card from "./Card";
import ClipCard from "./ClipCard";

type ClipListProps = {
  paths: string[] | null | undefined;
};

const ClipList = forwardRef<HTMLElement, ClipListProps>(function ClipList(
  { paths },
  ref,
) {
  const clips = paths ?? [];
  const total = clips.length;
  const [openIndex, setOpenIndex] = useState<number | null>(null);

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
      <header className="space-y-3 rounded-2xl border border-emerald-300/80 bg-gradient-to-br from-emerald-50 to-[var(--surface)] px-6 py-8 sm:px-8 sm:py-10">
        <p className="font-[family-name:var(--font-display)] text-3xl tracking-tight text-[var(--ink)] sm:text-4xl">
          <span aria-hidden>🎉 </span>Your clips are ready!
        </p>
        <p className="max-w-xl text-base leading-relaxed text-[var(--muted)] sm:text-lg">
          {total === 1
            ? "1 AI-generated highlight is ready to preview and download."
            : `${total} AI-generated highlights are ready to preview and download.`}
        </p>
      </header>

      <div className="space-y-2">
        <h2 className="font-[family-name:var(--font-display)] text-xl text-[var(--ink)]">
          Your workspace
        </h2>
        <p className="text-sm text-[var(--muted)]">
          Preview each short, then download the ones you want to post.
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
