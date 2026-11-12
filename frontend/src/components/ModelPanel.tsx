"use client";

import { motion } from "motion/react";
import { useState } from "react";
import type { ModelRuns, Session, TargetSuggestion } from "@/lib/api/client";
import { ErrorNote, Spinner } from "./Shell";

const MODEL_LABEL: Record<string, string> = {
  dummy: "Dummy",
  logistic_regression: "Logistic regression",
  linear_regression: "Linear regression",
  random_forest: "Random forest",
};
const METRIC_LABEL: Record<string, string> = {
  f1_macro: "F1 (macro)",
  accuracy: "Accuracy",
  roc_auc: "ROC AUC",
  rmse: "RMSE",
  mae: "MAE",
  r2: "R²",
};

const fmt = (value: number | null | undefined) => (value === null || value === undefined ? "—" : value.toFixed(3));

/** Baseline training + comparison on the Download screen (Spec 07 FR-ML-14 / AC-11). */
export function ModelPanel({
  session,
  runs,
  suggestions,
  onTrain,
}: {
  session: Session;
  runs: ModelRuns | null;
  suggestions: TargetSuggestion[];
  onTrain: (target: string) => void;
}) {
  // Columns the executed plan changed can't be targets (FR-ML-15); the session's own target stays
  const offered = suggestions.filter((s) => !s.changed_by_plan || s.column === session.target);
  const [target, setTarget] = useState(session.target ?? runs?.target ?? offered[0]?.column ?? "");
  const training = session.state === "modeling";
  const primary = runs?.primary_metric ?? "f1_macro";
  const secondary = runs?.problem_type === "regression" ? "r2" : "accuracy";
  const choice = offered.find((s) => s.column === target);

  return (
    <section aria-labelledby="models-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="models-heading" className="font-display text-lg font-semibold">Baseline models</h2>
        {runs && (
          <p className="text-xs text-muted">
            Predicting <span className="font-mono">{runs.target}</span> · {runs.problem_type} ·{" "}
            {runs.rows.used.toLocaleString()} rows · 5-fold CV + 20% hold-out
          </p>
        )}
      </div>

      {session.failed_stage === "model" && session.error && <ErrorNote>{session.error}</ErrorNote>}

      {training ? (
        <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5">
          <Spinner label="Training baseline models with 5-fold cross-validation…" />
          <div className="h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <motion.div className="h-full w-1/3 rounded-full bg-accent" animate={{ x: ["-100%", "300%"] }}
              transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }} />
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-surface p-4">
          <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-muted">
            Column to predict
            <select
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              className="h-10 rounded-lg border border-line-strong bg-surface px-3 font-mono text-sm text-ink"
            >
              {!target && <option value="">Choose a column</option>}
              {offered.map((s) => (
                <option key={s.column} value={s.column}>{s.column} ({s.problem_type})</option>
              ))}
              {target && !choice && <option value={target}>{target}</option>}
            </select>
          </label>
          <button
            type="button"
            disabled={!target}
            onClick={() => onTrain(target)}
            className="h-10 rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-50"
          >
            {runs ? "Retrain baseline models" : "Train baseline models"}
          </button>
          {choice && <p className="w-full text-xs text-ink-soft">{choice.reason}.</p>}
        </div>
      )}

      {runs && (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table aria-label="Baseline models" className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-[0.06em] text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Model</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">{METRIC_LABEL[primary]} · CV</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">{METRIC_LABEL[primary]} · hold-out</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">{METRIC_LABEL[secondary]} · CV</th>
                </tr>
              </thead>
              <tbody>
                {runs.models.map((model, index) => {
                  const best = model.name === runs.best_model;
                  const dummy = model.name === "dummy";
                  const cv = model.cv[primary];
                  return (
                    <motion.tr
                      key={model.name}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.07 }}
                      className={`border-b border-sunken last:border-0 ${dummy ? "text-muted" : ""} ${best ? "bg-accent-soft/60" : ""}`}
                    >
                      <td className="px-4 py-3">
                        <span className="font-medium">{MODEL_LABEL[model.name] ?? model.name}</span>
                        {best && <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-white">Best</span>}
                        {dummy && <span className="ml-2 text-xs">(floor: always guesses the most common answer)</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {fmt(cv?.mean)} <span className="text-xs text-muted">± {fmt(cv?.std)}</span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(model.holdout[primary])}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(model.cv[secondary]?.mean)}</td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-[13px] leading-relaxed text-ink-soft">
            {runs.beats_dummy
              ? `${MODEL_LABEL[runs.best_model]} beats the dummy floor by ${fmt(runs.margin_over_dummy)} ${METRIC_LABEL[primary]}. `
              : "No model beats the dummy floor: the features may not predict this target. "}
            {runs.note}
          </p>
        </>
      )}
    </section>
  );
}
