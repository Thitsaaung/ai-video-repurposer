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
        <Card className="border-dashed">
          <SectionTitle>Generated Clips (0)</SectionTitle>
          <p className="mt-2 text-[var(--muted)]">No clips were generated.</p>
        </Card>
      </section>
    );
  }

  return (
    <section
      ref={ref}
      id="generated-clips"
      tabIndex={-1}
      className="space-y-4 outline-none"
      aria-label={`Generated clips, ${total} total`}
    >
      <SectionTitle>{`Generated Clips (${total})`}</SectionTitle>
      <ul className="grid grid-cols-1 gap-3">
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
