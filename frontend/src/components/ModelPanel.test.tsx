/** Spec 07 AC-11 / FR-ML-14 and FR-ML-01 (UI). Written before the components. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import type { ModelRuns, TargetSuggestion } from "@/lib/api/client";
import { profile, session } from "@/test/fixtures";
import { ModelPanel } from "./ModelPanel";
import { ProfileScreen } from "./ProfileScreen";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { ...actual.api, setTarget: vi.fn(), generatePlan: vi.fn() } };
});

const suggestions: TargetSuggestion[] = [
  { column: "Survived", problem_type: "classification", reason: "Its name looks like an outcome; it has yes/no values" },
  { column: "Fare", problem_type: "regression", reason: "It is a continuous number" },
];

const metric = (mean: number) => ({ folds: [mean, mean, mean, mean, mean], mean, std: 0.01 });
const runs: ModelRuns = {
  target: "Survived",
  problem_type: "classification",
  primary_metric: "f1_macro",
  best_model: "random_forest",
  beats_dummy: true,
  margin_over_dummy: 0.41,
  models: [
    { name: "dummy", cv: { accuracy: metric(0.62), f1_macro: metric(0.38), roc_auc: metric(0.5) },
      holdout: { accuracy: 0.61, f1_macro: 0.38, roc_auc: 0.5 }, fit_seconds: 0.1 },
    { name: "logistic_regression", cv: { accuracy: metric(0.8), f1_macro: metric(0.78), roc_auc: metric(0.85) },
      holdout: { accuracy: 0.79, f1_macro: 0.77, roc_auc: 0.84 }, fit_seconds: 0.4 },
    { name: "random_forest", cv: { accuracy: metric(0.82), f1_macro: metric(0.79), roc_auc: metric(0.87) },
      holdout: { accuracy: 0.81, f1_macro: 0.8, roc_auc: 0.86 }, fit_seconds: 1.2 },
  ],
  rows: { total: 891, dropped_missing_target: 0, used: 891, sampled: false, train: 712, test: 179 },
  features: { numeric: ["Age", "Fare"], categorical: ["Sex"], excluded: ["Name"] },
  note: "These are baselines.",
};

describe("Spec 07 model panel", () => {
  test("test_ml_ac11_results_table_marks_the_best_model", () => {
    render(<ModelPanel session={{ ...session, state: "modeled", target: "Survived" }} runs={runs}
      suggestions={suggestions} onTrain={vi.fn()} />);

    const table = screen.getByRole("table", { name: /baseline models/i });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Dummy");
    expect(rows[0]).toHaveTextContent(/floor/i);
    expect(rows[2]).toHaveTextContent("Random forest");
    expect(within(rows[2]).getByText("Best")).toBeInTheDocument();
    expect(rows[2]).toHaveTextContent("0.790");
    expect(screen.getByText(/not production models|baselines/i)).toBeInTheDocument();
  });

  test("test_ml_ac11_train_sends_the_chosen_target", async () => {
    const onTrain = vi.fn();
    render(<ModelPanel session={{ ...session, state: "executed", target: null }} runs={null}
      suggestions={suggestions} onTrain={onTrain} />);

    const select = screen.getByLabelText(/column to predict/i) as HTMLSelectElement;
    expect(select.value).toBe("Survived"); // top suggestion preselected
    await userEvent.selectOptions(select, "Fare");
    await userEvent.click(screen.getByRole("button", { name: /train baseline models/i }));
    expect(onTrain).toHaveBeenCalledWith("Fare");
  });

  test("test_ml_fr14_training_in_progress_is_shown", () => {
    render(<ModelPanel session={{ ...session, state: "modeling", target: "Survived" }} runs={null}
      suggestions={suggestions} onTrain={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent(/training/i);
    expect(screen.queryByRole("button", { name: /train baseline models/i })).not.toBeInTheDocument();
  });

  test("test_ml_fr01_profile_screen_offers_the_top_suggestion", async () => {
    render(<ProfileScreen session={{ ...session, state: "profiled" }} profile={profile}
      suggestions={suggestions} onPlanned={vi.fn()} />);
    expect(screen.getByText(/its name looks like an outcome/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /use survived/i }));
    expect((screen.getByLabelText(/prediction target/i) as HTMLSelectElement).value).toBe("Survived");
  });
});
