"use client";

import type { PlanStep, Profile } from "@/lib/api/client";

const field =
  "h-9 rounded-lg border border-line-strong bg-surface px-2.5 text-sm text-ink aria-[invalid=true]:border-danger aria-[invalid=true]:border-[1.5px]";
const labelText = "flex flex-col gap-1 text-xs text-muted";

/** Per-operation parameter editing (Spec 04 FR-RV-03). The server re-validates. */
export function ParamEditor({
  step,
  profile,
  issue,
  onChange,
}: {
  step: PlanStep;
  profile: Profile | null;
  issue: string | null;
  onChange: (params: Record<string, unknown>) => void;
}) {
  const params = step.params ?? {};
  const id = step.step_id ?? "step";
  const set = (patch: Record<string, unknown>) => onChange({ ...params, ...patch });
  const columnType = profile?.columns.find((c) => c.name === step.column)?.type;

  switch (step.op) {
    case "impute": {
      const strategies = columnType === "numeric" ? ["median", "mean", "mode", "constant"] : ["mode", "constant"];
      return (
        <div className="flex flex-wrap items-end gap-3">
          <label className={labelText}>
            Strategy
            <select
              className={`${field} min-w-36`}
              value={String(params.strategy ?? "")}
              onChange={(event) => {
                const strategy = event.target.value;
                const next = { ...params, strategy };
                if (strategy !== "constant") delete (next as Record<string, unknown>).value;
                onChange(next);
              }}
            >
              {strategies.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          {params.strategy === "constant" && (
            <label className={issue ? labelText.replace("text-muted", "text-danger") : labelText}>
              Value
              <input
                className={`${field} w-32`}
                value={params.value === undefined || params.value === null ? "" : String(params.value)}
                placeholder={columnType === "numeric" ? "e.g. 0" : "e.g. unknown"}
                aria-invalid={issue ? true : undefined}
                aria-describedby={issue ? `${id}-issue` : undefined}
                onChange={(event) => {
                  const raw = event.target.value;
                  const asNumber = Number(raw);
                  const value = columnType === "numeric" && raw.trim() !== "" && Number.isFinite(asNumber) ? asNumber : raw;
                  set({ value });
                }}
              />
            </label>
          )}
        </div>
      );
    }
    case "clip_outliers":
      return (
        <label className={labelText}>
          IQR factor
          <input
            className={`${field} w-28`}
            type="number"
            step="0.5"
            min="0.5"
            value={String(params.factor ?? 1.5)}
            aria-invalid={issue ? true : undefined}
            onChange={(event) => set({ factor: event.target.value === "" ? "" : Number(event.target.value) })}
          />
        </label>
      );
    case "cast_type":
      return (
        <label className={labelText}>
          Convert to
          <select className={`${field} min-w-36`} value={String(params.to ?? "")} onChange={(event) => set({ to: event.target.value })}>
            {["int", "float", "str", "bool", "category"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
      );
    case "parse_datetime":
      return (
        <label className={labelText}>
          Date format <span className="sr-only">(optional)</span>
          <input
            className={`${field} w-44 font-mono`}
            value={String(params.format ?? "")}
            placeholder="auto (e.g. %Y-%m-%d)"
            onChange={(event) => {
              const next = { ...params };
              if (event.target.value) next.format = event.target.value;
              else delete next.format;
              onChange(next);
            }}
          />
        </label>
      );
    case "standardize_text": {
      const ops = Array.isArray(params.ops) ? (params.ops as string[]) : [];
      return (
        <fieldset className="flex flex-wrap items-center gap-4 text-sm" aria-invalid={issue ? true : undefined}>
          <legend className="sr-only">Text operations</legend>
          {["trim", "lowercase", "collapse_spaces"].map((op) => (
            <label key={op} className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 accent-[var(--color-accent)]"
                checked={ops.includes(op)}
                onChange={(event) =>
                  set({ ops: event.target.checked ? [...ops, op] : ops.filter((o) => o !== op) })
                }
              />
              <span className="font-mono text-[13px]">{op}</span>
            </label>
          ))}
        </fieldset>
      );
    }
    default:
      return null;
  }
}
