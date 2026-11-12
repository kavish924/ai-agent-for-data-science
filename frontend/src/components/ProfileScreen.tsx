"use client";

import { motion } from "framer-motion";
import { useState } from "react";
import {
  api,
  ApiError,
  type ColumnProfile,
  type Profile,
  type Session,
  type TargetSuggestion,
} from "@/lib/api/client";
import { ErrorNote, Spinner } from "./Shell";

const TYPE_LABEL: Record<string, string> = {
  numeric: "number",
  categorical: "category",
  datetime: "date",
  boolean: "yes/no",
  text: "text",
  id_like: "identifier",
};

/** Target candidates: every column except identifiers (Spec 04 AC-10, Spec 07 FR-ML-10). */
export function targetCandidates(profile: Profile): ColumnProfile[] {
  return profile.columns.filter((column) => column.type !== "id_like");
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div>
      <p className="font-display text-2xl font-semibold">{value}</p>
      <p className="text-xs text-muted">{label}</p>
    </div>
  );
}

export function ProfileScreen({
  session,
  profile,
  suggestions = [],
  onPlanned,
}: {
  session: Session;
  profile: Profile;
  suggestions?: TargetSuggestion[];
  onPlanned: () => void;
}) {
  const [target, setTarget] = useState<string>(session.target ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const candidates = targetCandidates(profile);
  const top = suggestions[0];

  async function generate() {
    setError(null);
    try {
      if ((session.target ?? "") !== target) {
        setBusy("Saving target…");
        await api.setTarget(session.id, target || null);
      }
      setBusy("Asking the AI planner for a cleaning plan…");
      await api.generatePlan(session.id);
      onPlanned();
    } catch (err) {
      if (err instanceof ApiError && err.code === "llm_not_configured") {
        setError("The AI planner isn't configured on the server. Set GEMINI_API_KEY, or LLM_PROVIDER=offline for a demo.");
      } else {
        setError(err instanceof ApiError ? err.message : "Planning failed.");
      }
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.06em] text-muted">Dataset</p>
          <h1 className="mt-1 font-mono text-xl font-medium">{session.original_filename}</h1>
        </div>
        <div className="flex gap-8">
          <Stat value={profile.n_rows.toLocaleString()} label="rows" />
          <Stat value={profile.n_columns} label="columns" />
          <Stat value={profile.duplicate_rows} label="duplicate rows" />
          <Stat value={profile.total_null_cells.toLocaleString()} label="missing cells" />
        </div>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        <section aria-labelledby="columns-heading" className="min-w-0 flex-[999_1_560px] overflow-hidden rounded-xl border border-line bg-surface">
          <h2 id="columns-heading" className="sr-only">Columns</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-[0.06em] text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Column</th>
                  <th scope="col" className="px-4 py-3 font-medium">Type</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Missing</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Unique</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Outliers</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map((column, index) => (
                  <motion.tr
                    key={column.name}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(index * 0.02, 0.3) }}
                    className="border-b border-sunken last:border-0"
                  >
                    <td className="px-4 py-2.5 font-mono text-[13px]">{column.name}</td>
                    <td className="px-4 py-2.5 text-muted">{TYPE_LABEL[column.type] ?? column.type}</td>
                    <td className={`px-4 py-2.5 text-right tabular-nums ${column.null_pct >= 15 ? "font-medium text-warn" : ""}`}>
                      {column.nulls ? `${column.null_pct}%` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-muted">{column.unique.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-muted">{column.outliers_iqr || "—"}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="flex flex-[1_1_300px] flex-col gap-4">
          <section className="rounded-xl border border-line bg-surface p-5">
            <label htmlFor="target" className="text-sm font-semibold">Prediction target <span className="font-normal text-muted">(optional)</span></label>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
              The column you want to predict later. The plan will never change it.
            </p>
            <select
              id="target"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              className="mt-3 h-11 w-full rounded-lg border border-line-strong bg-surface px-3 font-mono text-sm"
            >
              <option value="">No target</option>
              {candidates.map((column) => (
                <option key={column.name} value={column.name}>{column.name}</option>
              ))}
            </select>
            {top && target !== top.column && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 flex items-start justify-between gap-3 rounded-lg bg-accent-soft px-3 py-2.5 text-[13px] text-accent-ink"
              >
                <span>
                  <span className="font-semibold">Suggested: </span>
                  <span className="font-mono">{top.column}</span> · {top.reason}.
                </span>
                <button
                  type="button"
                  onClick={() => setTarget(top.column)}
                  aria-label={`Use ${top.column} as the target`}
                  className="shrink-0 rounded-md border border-accent/40 bg-surface px-2.5 py-1 text-xs font-semibold hover:border-accent"
                >
                  Use it
                </button>
              </motion.div>
            )}
          </section>

          <section className="flex gap-2.5 rounded-xl border border-dashed border-line-strong p-4 text-xs leading-relaxed text-ink-soft">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" aria-hidden="true" className="mt-0.5 shrink-0">
              <rect x="4" y="11" width="16" height="10" rx="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
            <span>Only column statistics are sent to the AI — never your rows, names or IDs.</span>
          </section>

          <motion.button
            type="button"
            onClick={() => void generate()}
            disabled={busy !== null}
            whileTap={{ scale: 0.98 }}
            className="h-12 rounded-lg bg-accent px-5 text-[15px] font-semibold text-white transition-colors hover:bg-accent-strong disabled:opacity-60"
          >
            Generate plan with AI
          </motion.button>
          <div aria-live="polite">
            {busy && <Spinner label={busy} />}
            {error && <ErrorNote>{error}</ErrorNote>}
          </div>
        </aside>
      </div>
    </main>
  );
}
