"use client";

import { Toaster } from "sonner";

/** App-wide toast host — keep styling close to the existing cream/teal UI. */
export default function AppToaster() {
  return (
    <Toaster
      position="top-center"
      closeButton
      toastOptions={{
        classNames: {
          toast:
            "border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] shadow-sm",
          title: "text-[var(--ink)]",
          description: "text-[var(--muted)]",
          closeButton:
            "border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)]",
        },
      }}
    />
  );
}
