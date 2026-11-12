"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { api, type ChartEntry, type ChartManifest } from "@/lib/api/client";

/** Chart gallery for the Download screen (Spec 06 FR-CH-13 / AC-10). */
export function ChartGallery({ sessionId, manifest }: { sessionId: string; manifest: ChartManifest }) {
  const [open, setOpen] = useState<ChartEntry | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const opener = useRef<HTMLButtonElement | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (!open) opener.current?.focus();
  }, [open]);

  if (manifest.status === "failed") {
    return (
      <section aria-labelledby="charts-heading" className="rounded-xl border border-line bg-surface p-5">
        <h2 id="charts-heading" className="font-display text-lg font-semibold">Charts</h2>
        <p className="mt-1.5 text-sm text-ink-soft">
          The charts couldn&apos;t be created for this run. Your cleaned dataset is complete and
          ready to download.
        </p>
      </section>
    );
  }

  const skipped = manifest.skipped;
  return (
    <section aria-labelledby="charts-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="charts-heading" className="font-display text-lg font-semibold">Charts</h2>
        <p className="text-xs text-muted">
          {manifest.charts.length} of up to {manifest.max_charts} · from the cleaned data
        </p>
      </div>

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {manifest.charts.map((chart, index) => (
          <motion.li
            key={chart.file}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(index * 0.05, 0.4) }}
          >
            <button
              type="button"
              aria-label={`Open ${chart.title}`}
              onClick={(event) => {
                opener.current = event.currentTarget;
                setOpen(chart);
              }}
              className="group flex w-full flex-col gap-2 rounded-xl border border-line bg-surface p-3 text-left transition-colors hover:border-accent"
            >
              <motion.div layoutId={`chart-${chart.file}`} className="overflow-hidden rounded-lg bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element -- plain PNGs from our API; image optimisation is off */}
                <img
                  src={api.chartUrl(sessionId, chart.file)}
                  alt={chart.title}
                  loading="lazy"
                  className="h-44 w-full object-contain"
                />
              </motion.div>
              <span className="flex items-center justify-between gap-2 text-[13px]">
                <span className="truncate font-medium">{chart.title}</span>
                {chart.before_overlay && (
                  <span className="shrink-0 rounded-full bg-sunken px-2 py-0.5 text-[11px] text-ink-soft">
                    before vs after
                  </span>
                )}
              </span>
            </button>
          </motion.li>
        ))}
      </ul>

      {skipped.length > 0 && (
        <div className="text-[13px]">
          <button
            type="button"
            aria-expanded={showSkipped}
            onClick={() => setShowSkipped((value) => !value)}
            className="rounded text-accent-ink underline-offset-2 hover:underline"
          >
            {skipped.length} {skipped.length === 1 ? "chart" : "charts"} skipped
          </button>
          <AnimatePresence initial={false}>
            {showSkipped && (
              <motion.ul
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-2 overflow-hidden rounded-lg border border-line bg-surface"
              >
                {skipped.map((entry) => (
                  <li key={`${entry.kind}-${entry.column}`} className="flex justify-between gap-4 border-b border-sunken px-3 py-2 last:border-0">
                    <span className="font-mono text-xs">{entry.column ?? entry.kind.replace("_", " ")}</span>
                    <span className="text-right text-xs text-muted">{entry.reason}</span>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            key="overlay"
            className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(null)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label={open.title}
              className="flex max-h-full w-full max-w-4xl flex-col gap-3 rounded-2xl bg-surface p-4"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-display text-base font-semibold">{open.title}</p>
                <button
                  ref={closeButton}
                  type="button"
                  onClick={() => setOpen(null)}
                  className="h-9 rounded-lg border border-line-strong px-3 text-sm font-medium hover:border-accent"
                >
                  Close
                </button>
              </div>
              <motion.div layoutId={`chart-${open.file}`} className="min-h-0 overflow-auto rounded-lg bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element -- see above */}
                <img src={api.chartUrl(sessionId, open.file)} alt={open.title} className="mx-auto max-h-[75vh] w-auto" />
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
