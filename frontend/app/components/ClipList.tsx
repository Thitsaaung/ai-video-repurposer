"use client";

import { useState } from "react";
import Card from "./Card";
import ClipCard from "./ClipCard";
import SectionTitle from "./SectionTitle";

type ClipListProps = {
  paths: string[] | null | undefined;
};

export default function ClipList({ paths }: ClipListProps) {
  const clips = paths ?? [];
  const total = clips.length;
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (total === 0) {
    return (
      <Card className="border-dashed">
        <SectionTitle>Generated Clips (0)</SectionTitle>
        <p className="mt-2 text-[var(--muted)]">No clips were generated.</p>
      </Card>
    );
  }

  return (
    <section
      className="space-y-4"
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
}
