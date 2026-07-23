"use client";

type SectionTitleProps = {
  children: string;
  className?: string;
};

export default function SectionTitle({
  children,
  className = "",
}: SectionTitleProps) {
  return (
    <h2
      className={`font-[family-name:var(--font-display)] text-lg text-[var(--ink)] sm:text-xl ${className}`}
    >
      {children}
    </h2>
  );
}
