"use client";

import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export default function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`rounded-lg border border-[var(--line)] bg-[var(--surface)] px-4 py-4 ${className}`}
    >
      {children}
    </div>
  );
}
