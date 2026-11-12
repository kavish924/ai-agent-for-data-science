"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { api, ApiError, type PlanHistoryEntry } from "@/lib/api/client";
import { paramSummary } from "@/lib/plan";
import { Spinner } from "./Shell";

const label = (entry: PlanHistoryEntry) => `v${entry.version} · ${entry.kind}`;

/** Every stored plan version, read-only (Spec 04 FR-RV-19 / AC-6, AC-13). */
export function PlanHistory({ sessionId, currentVersion }: { sessionId: string; currentVersion: number | null }) {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<PlanHistoryEntry[] | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && entries === null) {
      try {
        setEntries(await api.planHistory(sessionId));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't load the plan history.");
      }
    }
  }

  const selected = chosen === null || !entries ? null : entries[chosen];

  return (
    <section className="rounded-xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => void toggle()}
        className="flex h-11 w-full items-center justify-between gap-2 rounded-xl px-4 text-left text-sm font-medium"
      >
        Plan history
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" aria-hidden="true" className={`transition-transform ${open ? "rotate-180" : ""}`}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="history"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            style={{ overflow: "hidden" }}
          >
            <div className="flex flex-col gap-3 border-t border-line p-4 md:flex-row">
              {error && <p role="alert" className="text-sm text-danger">{error}</p>}
              {!entries && !error && <Spinner label="Loading versions…" />}
              {entries && (
                <ul className="flex shrink-0 flex-col gap-1 md:w-64" aria-label="Plan versions">
                  {entries.map((entry, i) => {
                    const count = entry.plan.steps?.length ?? 0;
                    const current = entry.version === currentVersion;
                    return (
                      <li key={`${entry.version}-${entry.kind}`}>
                        <button
                          type="button"
                          aria-pressed={chosen === i}
                          onClick={() => setChosen(i)}
                          className={`flex min-h-10 w-full items-center justify-between gap-2 rounded-lg px-3 text-left text-[13px] ${
                            chosen === i ? "bg-accent-soft text-accent-ink" : "hover:bg-sunken"
                          }`}
                        >
                          <span>
                            {label(entry)} · {count} {count === 1 ? "step" : "steps"}
                          </span>
                          {current && <span className="text-[11px] font-semibold">current</span>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {selected && (
                <section aria-label={label(selected)} className="min-w-0 flex-1 rounded-lg bg-sunken/60 p-3">
                  <p className="mb-2 text-xs text-muted">Read-only: older versions can&apos;t be edited or run.</p>
                  <ol className="flex flex-col gap-2">
                    {(selected.plan.steps ?? []).map((step, i) => (
                      <li key={step.step_id ?? i} className="rounded-md bg-surface px-3 py-2 text-[13px]">
                        <span className="font-mono font-medium">{step.op}</span>
                        {step.column && <span className="font-mono"> · {step.column}</span>}
                        {paramSummary(step) && <span className="text-muted"> · {paramSummary(step)}</span>}
                        <span className="ml-2 text-xs text-muted">({step.status})</span>
                        {step.rationale && <p className="mt-0.5 text-ink-soft">{step.rationale}</p>}
                      </li>
                    ))}
                    {(selected.plan.steps ?? []).length === 0 && (
                      <li className="text-[13px] text-muted">This version had no steps.</li>
                    )}
                  </ol>
                </section>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
