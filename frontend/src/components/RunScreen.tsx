"use client";

import { motion } from "framer-motion";
import {
  api,
  type ChartManifest,
  type ExecutionLog,
  type ModelRuns,
  type Session,
  type TargetSuggestion,
} from "@/lib/api/client";
import { ChartGallery } from "./ChartGallery";
import { ModelPanel } from "./ModelPanel";
import { ReportPanel } from "./ReportPanel";
import { Spinner } from "./Shell";

const fmt = (n: number | undefined) => (n === undefined ? "—" : n.toLocaleString());

/** Shown while the background run is in progress (Spec 04 FR-RV-15). */
export function RunningScreen() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-6 px-4 py-16 text-center">
      <h1 className="font-display text-[26px] font-semibold">Applying your approved plan</h1>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
        <motion.div
          className="h-full w-1/3 rounded-full bg-accent"
          animate={{ x: ["-100%", "300%"] }}
          transition={{ repeat: Infinity, duration: 1.2, ease: "easeInOut" }}
        />
      </div>
      <Spinner label="Running steps in order. Your original upload is never modified." />
    </main>
  );
}

/** The run summary and deliverable download. */
export function DoneScreen({
  session,
  log,
  charts,
  runs = null,
  suggestions = [],
  onTrain = () => undefined,
  report = { source: null, busy: false, onCreate: () => undefined },
}: {
  session: Session;
  log: ExecutionLog;
  charts: ChartManifest | null;
  runs?: ModelRuns | null;
  suggestions?: TargetSuggestion[];
  onTrain?: (target: string) => void;
  report?: { source: "llm" | "template" | null; busy: boolean; onCreate: (renarrate: boolean) => void };
}) {
  const ran = log.steps.filter((s) => s.status === "executed");
  const skipped = log.steps.filter((s) => s.status === "disabled");
  const last = ran.at(-1)?.after;
  const first = ran[0]?.before;
  const colDelta = first && last ? last.cols - first.cols : 0;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-wrap gap-6 px-4 py-8 sm:px-8">
      <section className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
        <div className="flex items-center gap-3">
          <motion.span
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 420, damping: 22 }}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-accent">
              <motion.path d="M5 12l5 5L20 7" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                transition={{ delay: 0.15, duration: 0.35 }} />
            </svg>
          </motion.span>
          <div>
            <h1 className="font-display text-[26px] font-semibold">Plan applied</h1>
            <p className="text-[13px] text-muted">
              {ran.length} {ran.length === 1 ? "step" : "steps"} ran · {skipped.length} skipped · {log.duration_ms} ms ·
              original upload unchanged
            </p>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase tracking-[0.06em] text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Step</th>
                <th scope="col" className="px-4 py-3 font-medium">Column</th>
                <th scope="col" className="px-4 py-3 font-medium">Rows</th>
                <th scope="col" className="px-4 py-3 font-medium">Missing cells</th>
                <th scope="col" className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {log.steps.map((entry, index) => (
                <motion.tr
                  key={entry.step_id ?? index}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.06 }}
                  className={`border-b border-sunken last:border-0 ${entry.status === "executed" ? "" : "text-muted"}`}
                >
                  <td className="px-4 py-3 font-mono text-[13px]">{entry.op}</td>
                  <td className="px-4 py-3 font-mono text-[13px]">{entry.column ?? "—"}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {entry.before ? `${fmt(entry.before.rows)} → ${fmt(entry.after?.rows)}` : "—"}
                  </td>
                  <td className="px-4 py-3 tabular-nums">
                    {entry.before ? `${fmt(entry.before.null_cells)} → ${fmt(entry.after?.null_cells)}` : "—"}
                  </td>
                  <td className={`px-4 py-3 font-semibold ${entry.status === "executed" ? "text-accent-ink" : ""}`}>
                    {entry.status === "executed" ? "Executed" : entry.status === "disabled" ? "Skipped" : entry.status}
                  </td>
                </motion.tr>
              ))}
              {log.steps.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-6 text-muted">No steps ran: the data was exported unchanged.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <ModelPanel session={session} runs={runs} suggestions={suggestions} onTrain={onTrain} />

        {charts && <ChartGallery sessionId={session.id} manifest={charts} />}
      </section>

      <aside className="flex flex-[1_1_300px] flex-col gap-4">
        <section className="flex flex-col gap-3.5 rounded-xl bg-ink p-6 text-ground">
          <p className="text-xs uppercase tracking-[0.06em] text-[#b9bab3]">Your cleaned dataset</p>
          <p className="break-all font-mono text-[15px]">cleaned_{session.original_filename}</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="font-display text-2xl font-semibold">{fmt(last?.rows ?? session.n_rows ?? undefined)}</p>
              <p className="text-xs text-[#b9bab3]">rows</p>
            </div>
            <div>
              <p className="font-display text-2xl font-semibold">{fmt(last?.cols ?? session.n_columns ?? undefined)}</p>
              <p className="text-xs text-[#b9bab3]">columns{colDelta ? ` (${colDelta})` : ""}</p>
            </div>
          </div>
          <a
            href={api.cleanedCsvUrl(session.id)}
            download
            className="flex h-12 items-center justify-center gap-2 rounded-lg bg-[#2dd4bf] text-[15px] font-semibold text-[#0b1f1d] transition-transform hover:-translate-y-0.5"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 4v12M7 11l5 5 5-5M4 20h16" />
            </svg>
            Download cleaned CSV
          </a>
        </section>
        <ReportPanel session={session} source={report.source} busy={report.busy} onCreate={report.onCreate} />
      </aside>
    </main>
  );
}
