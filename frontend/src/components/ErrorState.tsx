"use client";

import { motion } from "motion/react";

/**
 * Errors that always offer a next step (Spec 04 FR-RV-20): a session that no longer
 * exists, or a server that can't be reached.
 */
export function ErrorState({
  kind,
  onStartOver,
  onRetry,
}: {
  kind: "missing" | "network";
  onStartOver: () => void;
  onRetry: () => void;
}) {
  if (kind === "network") {
    return (
      <motion.div
        role="alert"
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto mt-4 flex w-full max-w-4xl flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger"
      >
        <span>Can&apos;t reach the server. Check that the backend is running, then retry.</span>
        <button
          type="button"
          onClick={onRetry}
          className="h-9 rounded-lg border border-danger/40 bg-surface px-3 font-medium text-danger hover:border-danger"
        >
          Retry
        </button>
      </motion.div>
    );
  }
  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
      <h1 className="font-display text-2xl font-semibold">This analysis isn&apos;t available</h1>
      <p className="text-sm leading-relaxed text-ink-soft">
        The link may be wrong, or the session was removed after its retention period. Your
        original file is never kept longer than that.
      </p>
      <button
        type="button"
        onClick={onStartOver}
        className="mt-2 h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-white hover:bg-accent-strong"
      >
        Start a new analysis
      </button>
    </main>
  );
}
