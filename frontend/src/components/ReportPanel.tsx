"use client";

import { motion } from "motion/react";
import { api, type Session } from "@/lib/api/client";
import { Spinner } from "./Shell";

/** Report actions on the Download screen (Spec 08 FR-RP-16 / AC-11). */
export function ReportPanel({
  session,
  source,
  busy,
  onCreate,
}: {
  session: Session;
  source: "llm" | "template" | null;
  busy: boolean;
  onCreate: (renarrate: boolean) => void;
}) {
  const ready = session.state === "reported";
  const training = session.state === "modeling";

  return (
    <section aria-labelledby="report-heading" className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5">
      <div>
        <h2 id="report-heading" className="text-sm font-semibold">Process report</h2>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
          One HTML file: snapshot, issues, every step with its reason and counts, before vs after,
          charts{session.state !== "executed" ? ", models" : ""} and a written summary.
        </p>
      </div>

      {busy ? (
        <Spinner label="Building the report…" />
      ) : ready ? (
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-2.5">
          <a
            href={api.reportUrl(session.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-11 items-center justify-center rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-strong"
          >
            Open report
          </a>
          <a
            href={api.bundleUrl(session.id)}
            download
            className="flex h-11 items-center justify-center rounded-lg border border-line-strong px-4 text-sm font-medium hover:border-accent"
          >
            Download all (.zip)
          </a>
          {source && (
            <p className="text-xs text-muted">
              {source === "llm"
                ? "Summary written by the AI from the report's numbers."
                : "Template summary (the AI narration was unavailable)."}
            </p>
          )}
          <button type="button" onClick={() => onCreate(true)}
            className="self-start rounded text-xs font-medium text-accent-ink underline-offset-2 hover:underline">
            Rewrite summary
          </button>
        </motion.div>
      ) : (
        <button
          type="button"
          disabled={training}
          onClick={() => onCreate(false)}
          className="h-11 rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-50"
        >
          Create report
        </button>
      )}
      {training && !busy && <p className="text-xs text-muted">Available when training finishes.</p>}
    </section>
  );
}
