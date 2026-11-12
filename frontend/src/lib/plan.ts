/**
 * Review-state logic for the plan screen (Spec 04), kept free of React so it is easy to
 * test. Client checks are hints only: the server Gate re-validates everything.
 */
import type { Op, Plan, PlanStep, Profile } from "./api/client";

export type Decision = "proposed" | "approved" | "disabled";

export interface ReviewStep {
  /** The step as the planner proposed it (never mutated). */
  original: PlanStep;
  /** The step with the user's edits applied. */
  current: PlanStep;
  decision: Decision;
}

export type DisplayStatus = "Needs decision" | "Approved" | "Edited" | "Skipped";

const PARAM_DEFAULTS: Partial<Record<Op, Record<string, unknown>>> = {
  clip_outliers: { method: "iqr", factor: 1.5 },
};

export const OP_LABELS: Record<Op, string> = {
  drop_duplicates: "Drop duplicate rows",
  drop_column: "Drop columns",
  impute: "Fill missing values",
  clip_outliers: "Clip outliers",
  cast_type: "Change type",
  parse_datetime: "Parse dates",
  standardize_text: "Tidy text",
};

function normalized(step: PlanStep): string {
  const params = { ...(PARAM_DEFAULTS[step.op] ?? {}), ...(step.params ?? {}) };
  const sorted = Object.fromEntries(Object.entries(params).sort(([a], [b]) => a.localeCompare(b)));
  return JSON.stringify({ column: step.column ?? null, params: sorted });
}

export function toReview(plan: Plan): ReviewStep[] {
  return (plan.steps ?? []).map((step) => ({
    original: step,
    current: { ...step, params: { ...(step.params ?? {}) } },
    decision:
      step.status === "disabled" ? "disabled" : step.status === "proposed" ? "proposed" : "approved",
  }));
}

export function isEdited(step: ReviewStep): boolean {
  return normalized(step.original) !== normalized(step.current);
}

export function displayStatus(step: ReviewStep): DisplayStatus {
  if (step.decision === "disabled") return "Skipped";
  if (step.decision === "proposed") return "Needs decision";
  return isEdited(step) ? "Edited" : "Approved";
}

/** A client-side hint for an obviously incomplete edit (Spec 04 AC-3); null when fine. */
export function clientIssue(step: PlanStep): string | null {
  const params = step.params ?? {};
  switch (step.op) {
    case "impute":
      if (params.strategy === "constant" && (params.value === undefined || params.value === null || params.value === ""))
        return "A constant strategy needs a value.";
      return null;
    case "clip_outliers": {
      const factor = params.factor ?? 1.5;
      return typeof factor === "number" && factor > 0 ? null : "The factor must be a number above 0.";
    }
    case "standardize_text":
      return Array.isArray(params.ops) && params.ops.length > 0 ? null : "Pick at least one text operation.";
    case "drop_column":
      return Array.isArray(params.columns) && params.columns.length > 0 ? null : "Name at least one column.";
    default:
      return null;
  }
}

/** What a destructive step will remove, in words (Spec 04 FR-RV-07 / AC-7). */
export function destructiveWarning(step: PlanStep, profile: Profile | null): string | null {
  if (step.op === "drop_column") {
    const columns = (step.params?.columns as string[] | undefined) ?? [];
    if (columns.length === 0) return null;
    const noun = columns.length === 1 ? "column" : "columns";
    return `Removes ${columns.length} ${noun} (${columns.join(", ")}) from the cleaned file.`;
  }
  if (step.op === "drop_duplicates") {
    const rows = profile?.duplicate_rows;
    return rows === undefined
      ? "Removes duplicate rows, keeping the first of each."
      : `Removes ${rows} duplicate ${rows === 1 ? "row" : "rows"}, keeping the first of each.`;
  }
  return null;
}

export function undecidedCount(steps: ReviewStep[]): number {
  return steps.filter((step) => step.decision === "proposed").length;
}

export function issueCount(steps: ReviewStep[]): number {
  return steps.filter((step) => step.decision !== "disabled" && clientIssue(step.current)).length;
}

export function canApprove(steps: ReviewStep[]): boolean {
  return undecidedCount(steps) === 0 && issueCount(steps) === 0;
}

/** The review the server reconciles by step_id (Spec 04 FR-RV-09). */
export function toSubmission(steps: ReviewStep[]): PlanStep[] {
  return steps.map(({ current, decision }) => ({
    step_id: current.step_id,
    op: current.op,
    column: current.column,
    params: current.params ?? {},
    rationale: current.rationale,
    status: decision,
  }));
}

/** Short parameter summary for a step's header line. */
export function paramSummary(step: PlanStep): string {
  const params = step.params ?? {};
  switch (step.op) {
    case "impute":
      return params.strategy === "constant"
        ? `strategy = constant (${String(params.value ?? "?")})`
        : `strategy = ${String(params.strategy)}`;
    case "clip_outliers":
      return `IQR × ${String(params.factor ?? 1.5)}`;
    case "cast_type":
      return `to ${String(params.to)}`;
    case "parse_datetime":
      return params.format ? `format ${String(params.format)}` : "format auto";
    case "standardize_text":
      return Array.isArray(params.ops) ? params.ops.join(", ") : "";
    default:
      return "";
  }
}
