/** Spec 04 AC-1..8: plan review behaviour. The API is mocked; the server is never called. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ApiError, api } from "@/lib/api/client";
import { plan, profile, session } from "@/test/fixtures";
import { PlanReview } from "./PlanReview";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: { ...actual.api, approve: vi.fn(), execute: vi.fn(), generatePlan: vi.fn() },
  };
});

const mocked = vi.mocked(api);
const onStarted = vi.fn();

function setup() {
  const user = userEvent.setup();
  render(<PlanReview sessionId={session.id} initialPlan={plan} profile={profile} onStarted={onStarted} />);
  const cards = () => within(screen.getByRole("list", { name: "Plan steps" })).getAllByRole("listitem");
  const approveButton = () => screen.getByRole("button", { name: /approve plan & run/i });
  return { user, cards, approveButton };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.approve.mockResolvedValue(plan);
  mocked.execute.mockResolvedValue({ state: "executing" });
});

describe("Spec 04 plan review", () => {
  test("test_rv_ac1_renders_every_step_in_order", () => {
    const { cards } = setup();
    const rendered = cards();
    expect(rendered).toHaveLength(4);
    expect(rendered.map((card) => card.getAttribute("aria-label"))).toEqual([
      "step 1, Fill missing values Age",
      "step 2, Drop columns",
      "step 3, Drop duplicate rows",
      "step 4, Clip outliers Fare",
    ]);
    expect(within(rendered[0]).getByText("Age is 19.9% missing; the median is robust to outliers.")).toBeInTheDocument();
    expect(within(rendered[0]).getByText("strategy = median")).toBeInTheDocument();
  });

  test("test_rv_ac2_skipped_step_is_submitted_as_disabled", async () => {
    const { user, cards, approveButton } = setup();
    await user.click(within(cards()[1]).getByRole("button", { name: "Skip" }));
    await user.click(screen.getByRole("button", { name: "Approve all" }));
    await user.click(approveButton());

    const submitted = mocked.approve.mock.calls[0][1];
    expect(submitted.map((step) => [step.step_id, step.status])).toEqual([
      ["s1", "approved"], ["s2", "disabled"], ["s3", "approved"], ["s4", "approved"],
    ]);
    expect(mocked.execute).toHaveBeenCalledWith(session.id);
    expect(onStarted).toHaveBeenCalled();
  });

  test("test_rv_ac3_constant_without_value_blocks_approval", async () => {
    const { user, cards, approveButton } = setup();
    await user.click(screen.getByRole("button", { name: "Approve all" }));
    await user.selectOptions(within(cards()[0]).getByLabelText("Strategy"), "constant");

    expect(within(cards()[0]).getByText("A constant strategy needs a value.")).toBeInTheDocument();
    expect(approveButton()).toBeDisabled();

    await user.type(within(cards()[0]).getByLabelText("Value"), "30");
    expect(within(cards()[0]).queryByText("A constant strategy needs a value.")).not.toBeInTheDocument();
    expect(approveButton()).toBeEnabled();
  });

  test("test_rv_ac4_edited_step_is_labelled_and_submitted", async () => {
    const { user, cards, approveButton } = setup();
    await user.selectOptions(within(cards()[0]).getByLabelText("Strategy"), "mean");
    expect(within(cards()[0]).getByTestId("step-status")).toHaveTextContent("Edited");

    await user.click(screen.getByRole("button", { name: "Approve all" }));
    await user.click(approveButton());
    expect(mocked.approve.mock.calls[0][1][0].params).toEqual({ strategy: "mean" });
  });

  test("test_rv_ac5_approve_disabled_until_every_step_decided", async () => {
    const { user, cards, approveButton } = setup();
    expect(approveButton()).toBeDisabled();
    for (const card of cards().slice(0, 3)) {
      await user.click(within(card).getByRole("button", { name: "Approve" }));
    }
    expect(approveButton()).toBeDisabled();
    await user.click(within(cards()[3]).getByRole("button", { name: "Skip" }));
    expect(approveButton()).toBeEnabled();
  });

  test("test_rv_ac6_regenerate_shows_the_new_version", async () => {
    mocked.generatePlan.mockResolvedValue({
      ...plan,
      version: 2,
      steps: [{ step_id: "s1", op: "drop_duplicates", column: null, params: {}, status: "proposed", rationale: "Fresh." }],
    });
    const { user, cards } = setup();
    await user.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(mocked.generatePlan).toHaveBeenCalledWith(session.id);
    expect(await screen.findByText(/Version 2/)).toBeInTheDocument();
    expect(cards()).toHaveLength(1);
  });

  test("test_rv_ac7_destructive_steps_name_what_is_lost", () => {
    const { cards } = setup();
    expect(within(cards()[1]).getByText(/Removes 1 column \(Cabin\)/)).toBeInTheDocument();
    expect(within(cards()[2]).getByText(/Removes 3 duplicate rows/)).toBeInTheDocument();
    expect(within(cards()[0]).queryByText(/Destructive/)).not.toBeInTheDocument();
  });

  test("test_rv_ac8_server_issues_shown_on_their_step", async () => {
    mocked.approve.mockRejectedValue(
      new ApiError(422, "invalid_plan", "Plan rejected by the validation gate.", {
        issues: [{ step: 3, issue: "clip_outliers requires a numeric column" }],
      }),
    );
    const { user, cards, approveButton } = setup();
    await user.click(screen.getByRole("button", { name: "Approve all" }));
    await user.click(approveButton());

    expect(await within(cards()[3]).findByText("clip_outliers requires a numeric column")).toBeInTheDocument();
    expect(within(cards()[0]).queryByText("clip_outliers requires a numeric column")).not.toBeInTheDocument();
    expect(screen.getByText(/rejected some steps/)).toBeInTheDocument();
    expect(mocked.execute).not.toHaveBeenCalled();
  });
});
