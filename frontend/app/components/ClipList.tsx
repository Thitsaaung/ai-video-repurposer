"use client";

import { forwardRef, useState } from "react";
import Card from "./Card";
import ClipCard from "./ClipCard";
import SectionTitle from "./SectionTitle";

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
        <Card className="border-dashed px-5 py-6">
          <SectionTitle>Your clips</SectionTitle>
          <p className="mt-2 text-[var(--muted)]">
            No clips were generated for this video. Try another link.
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
      className="space-y-5 outline-none"
      aria-label={`Generated clips, ${total} total`}
    >
      <div className="space-y-1">
        <SectionTitle>
          {total === 1 ? "Your clip" : `Your clips (${total})`}
        </SectionTitle>
        <p className="text-sm text-[var(--muted)]">
          Preview each short, then download the ones you want to post.
        </p>
      </div>
      <ul className="grid grid-cols-1 gap-4">
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
