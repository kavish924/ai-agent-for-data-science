import type { Plan, Profile, Session } from "@/lib/api/client";

export const session: Session = {
  id: "7f3a0000000000000000000000000c21",
  original_filename: "titanic.csv",
  state: "awaiting_approval",
  n_rows: 891,
  n_columns: 12,
  created_at: "2026-11-12T09:00:00+00:00",
  updated_at: "2026-11-12T09:00:00+00:00",
  retention_expires_at: "2026-11-19T09:00:00+00:00",
  target: null,
  plan_version: 1,
};

const column = (name: string, type: string, nulls = 0) => ({
  name,
  type,
  nulls,
  null_pct: Math.round((nulls / 891) * 1000) / 10,
  unique: 10,
  flags: [],
  top_values: [],
});

export const profile: Profile = {
  session_id: session.id,
  n_rows: 891,
  n_columns: 6,
  duplicate_rows: 3,
  total_null_cells: 866,
  inference: {},
  issues: {},
  columns: [
    column("PassengerId", "id_like"),
    column("Survived", "boolean"),
    column("Age", "numeric", 177),
    column("Cabin", "text", 687),
    column("Embarked", "categorical", 2),
    column("Fare", "numeric"),
  ],
};

export const plan: Plan = {
  schema_version: "v1",
  version: 1,
  steps: [
    { step_id: "s1", op: "impute", column: "Age", params: { strategy: "median" }, status: "proposed",
      rationale: "Age is 19.9% missing; the median is robust to outliers." },
    { step_id: "s2", op: "drop_column", column: null, params: { columns: ["Cabin"] }, status: "proposed",
      rationale: "Cabin is 77.1% missing." },
    { step_id: "s3", op: "drop_duplicates", column: null, params: {}, status: "proposed",
      rationale: "3 duplicate rows found." },
    { step_id: "s4", op: "clip_outliers", column: "Fare", params: {}, status: "proposed",
      rationale: "116 extreme fares." },
  ],
};
