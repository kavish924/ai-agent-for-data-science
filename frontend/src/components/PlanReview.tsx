"use client";

import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { api, ApiError, type Plan, type Profile } from "@/lib/api/client";
import {
  canApprove,
  clientIssue,
  destructiveWarning,
  displayStatus,
  issueCount,
  OP_LABELS,
  paramSummary,
  toReview,
  toSubmission,
  undecidedCount,
  type Decision,
  type ReviewStep,
} from "@/lib/plan";
import { ParamEditor } from "./ParamEditor";
import { PlanHistory } from "./PlanHistory";
import { ErrorNote, Spinner } from "./Shell";

const STATUS_STYLE: Record<string, string> = {
  Approved: "text-accent-ink",
  Edited: "text-edit",
  Skipped: "text-muted",
  "Needs decision": "text-muted",
};

function DecisionToggle({
  value,
  label,
  onChange,
}: {
  value: Decision;
  label: string;
  onChange: (decision: Decision) => void;
}) {
  const option = (decision: Decision, text: string) => {
    const pressed = value === decision;
    return (
      <button
        type="button"
        aria-pressed={pressed}
        onClick={() => onChange(pressed ? "proposed" : decision)}
        className={`relative h-9 rounded-md px-3 text-[13px] font-medium transition-colors ${
          pressed ? (decision === "approved" ? "text-white" : "text-ink") : "text-muted hover:text-ink"
        }`}
      >
        {pressed && (
          <motion.span
            layoutId={`decision-${label}`}
            className={`absolute inset-0 rounded-md ${decision === "approved" ? "bg-accent" : "bg-line"}`}
            transition={{ type: "spring", stiffness: 500, damping: 36 }}
          />
        )}
        <span className="relative">{text}</span>
      </button>
    );
  };
  return (
    <div role="group" aria-label={`Decision for ${label}`} className="flex rounded-lg border border-line p-0.5">
      {option("approved", "Approve")}
      {option("disabled", "Skip")}
    </div>
  );
}

function StepCard({
  index,
  step,
  profile,
  serverIssues,
  onDecision,
  onParams,
}: {
  index: number;
  step: ReviewStep;
  profile: Profile | null;
  serverIssues: string[];
  onDecision: (decision: Decision) => void;
  onParams: (params: Record<string, unknown>) => void;
}) {
  const { current } = step;
  const status = displayStatus(step);
  const skipped = step.decision === "disabled";
  const hint = skipped ? null : clientIssue(current);
  const warning = destructiveWarning(current, profile);
  const label = `step ${index + 1}, ${OP_LABELS[current.op]}${current.column ? ` ${current.column}` : ""}`;
  const issueId = `${current.step_id ?? index}-issue`;
  const flagged = Boolean(hint) || serverIssues.length > 0;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, layout: { type: "spring", stiffness: 380, damping: 34 } }}
      aria-label={label}
      className={`rounded-xl border px-4 py-4 sm:px-5 ${
        flagged ? "border-danger/40 bg-surface" : warning && !skipped ? "border-warn-line bg-surface" : "border-line"
      } ${skipped ? "bg-[#fbfbf9]" : "bg-surface"}`}
    >
      <div className="flex flex-wrap items-start gap-3">
        <span className="mt-1 font-mono text-xs text-muted tabular-nums">{String(index + 1).padStart(2, "0")}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`font-mono text-[13px] font-medium ${skipped ? "text-muted" : ""}`}>{current.op}</span>
            {current.column && (
              <span className="rounded-md bg-sunken px-2 py-0.5 font-mono text-xs">{current.column}</span>
            )}
            {paramSummary(current) && <span className="text-xs text-muted">{paramSummary(current)}</span>}
            <motion.span
              key={status}
              initial={{ opacity: 0, y: -3 }}
              animate={{ opacity: 1, y: 0 }}
              className={`ml-auto text-xs font-semibold ${STATUS_STYLE[status]}`}
              data-testid="step-status"
            >
              {status}
            </motion.span>
          </div>
          {current.rationale && (
            <p className={`mt-1.5 text-sm leading-relaxed ${skipped ? "text-muted" : "text-ink-soft"}`}>{current.rationale}</p>
          )}
          {!skipped && (
            <div className="mt-3">
              <ParamEditor step={current} profile={profile} issue={hint} onChange={onParams} />
            </div>
          )}
          {warning && !skipped && (
            <p className="mt-3 rounded-lg bg-warn-soft px-3 py-2 text-[13px] text-warn">
              <span className="font-semibold">Destructive: </span>
              {warning}
            </p>
          )}
          {(hint || serverIssues.length > 0) && (
            <ul id={issueId} className="mt-2 space-y-1 text-[13px] text-danger" role="alert">
              {hint && <li>{hint}</li>}
              {serverIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </div>
        <DecisionToggle value={step.decision} label={label} onChange={onDecision} />
      </div>
    </motion.li>
  );
}

export function PlanReview({
  sessionId,
  initialPlan,
  profile,
  initialError,
  onStarted,
}: {
  sessionId: string;
  initialPlan: Plan;
  profile: Profile | null;
  initialError?: string | null;
  onStarted: () => void;
}) {
  const [plan, setPlan] = useState(initialPlan);
  const [steps, setSteps] = useState<ReviewStep[]>(() => toReview(initialPlan));
  const [serverIssues, setServerIssues] = useState<Record<number, string[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(initialError ?? null);

  const undecided = undecidedCount(steps);
  const issues = issueCount(steps);
  const ready = canApprove(steps) && busy === null;

  const summary = useMemo(() => {
    const decided = steps.length - undecided;
    const parts = [`${decided} of ${steps.length} steps decided`];
    if (issues) parts.push(`${issues} ${issues === 1 ? "needs" : "need"} a fix`);
    return parts.join(" · ");
  }, [steps.length, undecided, issues]);

  function update(index: number, patch: Partial<ReviewStep>) {
    setSteps((all) => all.map((step, i) => (i === index ? { ...step, ...patch } : step)));
    setServerIssues((all) => Object.fromEntries(Object.entries(all).filter(([key]) => Number(key) !== index)));
  }

  async function regenerate() {
    setBusy("Asking the AI planner for a new plan…");
    setError(null);
    try {
      const next = await api.generatePlan(sessionId);
      setPlan(next);
      setSteps(toReview(next));
      setServerIssues({});
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't regenerate the plan.");
    } finally {
      setBusy(null);
    }
  }

  async function approveAndRun() {
    setBusy("Approving the plan…");
    setError(null);
    try {
      await api.approve(sessionId, toSubmission(steps));
      setBusy("Starting the run…");
      await api.execute(sessionId);
      onStarted();
    } catch (err) {
      if (err instanceof ApiError && err.gateIssues.length > 0) {
        const byStep: Record<number, string[]> = {};
        for (const { step, issue } of err.gateIssues) (byStep[step] ??= []).push(issue);
        setServerIssues(byStep);
        setError("The server rejected some steps. Fix them and approve again.");
      } else {
        setError(err instanceof ApiError ? err.message : "Approval failed.");
      }
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 px-4 py-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[26px] font-semibold">Cleaning plan</h1>
          <p className="mt-1 text-[13px] text-muted">
            Version {plan.version ?? 1} · proposed by the AI planner · nothing changes until you approve
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy !== null || steps.length === 0}
            onClick={() => setSteps((all) => all.map((s) => (s.decision === "proposed" ? { ...s, decision: "approved" } : s)))}
            className="h-11 rounded-lg border border-line-strong bg-surface px-4 text-sm font-medium hover:border-accent disabled:opacity-50"
          >
            Approve all
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void regenerate()}
            className="h-11 rounded-lg border border-line-strong bg-surface px-4 text-sm font-medium hover:border-accent disabled:opacity-50"
          >
            Regenerate
          </button>
        </div>
      </div>

      <PlanHistory key={plan.version ?? 1} sessionId={sessionId} currentVersion={plan.version ?? null} />

      <AnimatePresence>{error && <ErrorNote key="error">{error}</ErrorNote>}</AnimatePresence>

      {steps.length === 0 ? (
        <p className="rounded-xl border border-line bg-surface p-6 text-sm text-ink-soft">
          The planner found nothing that needs cleaning. Approve to export the data unchanged, or regenerate.
        </p>
      ) : (
        <ol className="flex flex-col gap-3" aria-label="Plan steps">
          {steps.map((step, index) => (
            <StepCard
              key={`${plan.version}-${step.current.step_id ?? index}`}
              index={index}
              step={step}
              profile={profile}
              serverIssues={serverIssues[index] ?? []}
              onDecision={(decision) => update(index, { decision })}
              onParams={(params) =>
                update(index, {
                  current: { ...step.current, params },
                  decision: step.decision === "proposed" ? "approved" : step.decision,
                })
              }
            />
          ))}
        </ol>
      )}

      <div className="sticky bottom-4 mt-auto flex flex-wrap items-center justify-between gap-3 rounded-xl bg-ink px-5 py-3.5 text-ground shadow-lg">
        <span className="text-sm" aria-live="polite">
          {busy ? <Spinner label={busy} className="text-ground" /> : summary}
        </span>
        <motion.button
          type="button"
          disabled={!ready}
          onClick={() => void approveAndRun()}
          whileTap={ready ? { scale: 0.97 } : undefined}
          className="h-11 rounded-lg bg-[#2dd4bf] px-5 text-sm font-semibold text-[#0b1f1d] transition-opacity disabled:cursor-not-allowed disabled:opacity-45"
        >
          Approve plan &amp; run
        </motion.button>
      </div>
    </main>
  );
}
