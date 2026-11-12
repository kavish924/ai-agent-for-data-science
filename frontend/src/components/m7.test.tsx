/** Spec 04 AC-11..16 and Spec 07 AC-12 (M7 UI polish). Written before the components. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";
import { api, type TargetSuggestion } from "@/lib/api/client";
import { plan, session } from "@/test/fixtures";
import { ErrorState } from "./ErrorState";
import { ModelPanel } from "./ModelPanel";
import { PlanHistory } from "./PlanHistory";
import { ReportView } from "./ReportView";
import { RESULT_TABS, ResultsTabs, readTab } from "./ResultsTabs";
import { Shell } from "./Shell";
import { useScreenFocus } from "./useScreenFocus";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { ...actual.api, planHistory: vi.fn() } };
});

function Tabs() {
  const [tab, setTab] = useState<(typeof RESULT_TABS)[number]["id"]>("overview");
  return (
    <ResultsTabs selected={tab} onSelect={setTab}>
      {(id) => <p>panel {id}</p>}
    </ResultsTabs>
  );
}

describe("M7 UI polish", () => {
  test("test_rv_ac11_tabs_follow_the_aria_pattern", async () => {
    const user = userEvent.setup();
    render(<Tabs />);
    const tabs = within(screen.getByRole("tablist", { name: /results/i })).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Overview", "Charts", "Models", "Report"]);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs.map((t) => t.getAttribute("tabindex"))).toEqual(["0", "-1", "-1", "-1"]);
    expect(screen.getByRole("tabpanel")).toHaveTextContent("panel overview");

    tabs[0].focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Charts" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Charts" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("panel charts");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Report" })).toHaveFocus();
    await user.keyboard("{ArrowRight}"); // wraps
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveFocus();
    await user.keyboard("{ArrowLeft}{Home}");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
  });

  test("test_rv_ac11_active_tab_lives_in_the_url", () => {
    expect(readTab(new URLSearchParams("session=x&tab=models"))).toBe("models");
    expect(readTab(new URLSearchParams("session=x&tab=nope"))).toBe("overview");
    expect(readTab(new URLSearchParams("session=x"))).toBe("overview");
  });

  test("test_rv_ac12_report_tab_embeds_a_sandboxed_report", () => {
    const { rerender } = render(
      <ReportView session={{ ...session, state: "reported" }} source="llm" busy={false} onCreate={vi.fn()} />,
    );
    const frame = screen.getByTitle(/process report/i);
    expect(frame.tagName).toBe("IFRAME");
    expect(frame).toHaveAttribute("src", `/api/v1/sessions/${session.id}/report`);
    // no scripts, forms, popups or navigation: only same-origin so it isn't blocked as opaque
    expect(frame.getAttribute("sandbox")).toBe("allow-same-origin");
    expect(frame.getAttribute("sandbox")).not.toContain("allow-scripts");

    rerender(<ReportView session={{ ...session, state: "modeled" }} source={null} busy={false} onCreate={vi.fn()} />);
    expect(screen.queryByTitle(/process report/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create report/i })).toBeInTheDocument();
  });

  test("test_rv_ac13_plan_history_shows_versions_read_only", async () => {
    const v1 = { ...plan, version: 1 };
    const v2 = { ...plan, version: 2, steps: (plan.steps ?? []).slice(0, 1) };
    vi.mocked(api.planHistory).mockResolvedValue([
      { version: 1, kind: "generated", plan: v1 },
      { version: 2, kind: "generated", plan: v2 },
      { version: 2, kind: "approved", plan: v2 },
    ]);
    const user = userEvent.setup();
    render(<PlanHistory sessionId={session.id} currentVersion={2} />);
    await user.click(screen.getByRole("button", { name: /plan history/i }));

    const items = await screen.findAllByRole("button", { name: /^v\d/ });
    expect(items.map((b) => b.textContent)).toEqual([
      expect.stringMatching(/v1.*generated.*4 steps/),
      expect.stringMatching(/v2.*generated.*1 step.*current/),
      expect.stringMatching(/v2.*approved.*1 step.*current/),
    ]);
    await user.click(items[0]);
    const detail = screen.getByRole("region", { name: /v1 · generated/i });
    expect(within(detail).getAllByRole("listitem")).toHaveLength(4);
    expect(within(detail).queryByRole("button", { name: /approve|skip/i })).not.toBeInTheDocument();
  });

  test("test_rv_ac14_missing_session_and_network_errors_offer_a_next_step", async () => {
    const onStartOver = vi.fn();
    const onRetry = vi.fn();
    const { rerender } = render(<ErrorState kind="missing" onStartOver={onStartOver} onRetry={onRetry} />);
    expect(screen.getByRole("heading", { name: /this analysis isn't available/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /start a new analysis/i }));
    expect(onStartOver).toHaveBeenCalled();

    rerender(<ErrorState kind="network" onStartOver={onStartOver} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/can't reach the server/i);
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  test("test_rv_ac15_focus_moves_to_the_new_heading_and_is_announced", () => {
    function Screen({ name }: { name: string }) {
      const { headingRef, announcement } = useScreenFocus(name, `${name} ready`);
      return (
        <>
          <h1 ref={headingRef} tabIndex={-1}>{name}</h1>
          <p role="status" aria-live="polite">{announcement}</p>
        </>
      );
    }
    const { rerender } = render(<Screen name="Upload" />);
    act(() => rerender(<Screen name="Profile" />));
    expect(screen.getByRole("heading", { name: "Profile" })).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("Profile ready");
  });

  test("test_rv_ac15_skip_link_targets_main", () => {
    render(<Shell current="Upload"><p>content</p></Shell>);
    const skip = screen.getByRole("link", { name: /skip to main content/i });
    expect(skip).toHaveAttribute("href", "#main");
    expect(document.getElementById("main")).toBeInTheDocument();
  });

  test("test_rv_ac15_stepper_reads_finished_steps", () => {
    render(<Shell current="Review plan"><p /></Shell>);
    const steps = within(screen.getByRole("navigation", { name: /progress/i })).getAllByRole("listitem");
    expect(steps[0]).toHaveTextContent(/upload.*done/i);
    expect(steps[1]).toHaveTextContent(/profile.*done/i);
    expect(steps[2]).not.toHaveTextContent(/done/i);
  });

  test("test_rv_ac16_no_framer_motion_imports", () => {
    const root = join(process.cwd(), "src");
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(ts|tsx)$/.test(name) && !name.endsWith(".test.tsx")) files.push(path);
      }
    };
    walk(root);
    const offenders = files.filter((f) => readFileSync(f, "utf8").includes('from "framer-motion"'));
    expect(offenders).toEqual([]);
  });

  test("test_ml_ac12_model_panel_hides_targets_changed_by_the_plan", () => {
    const suggestions: TargetSuggestion[] = [
      { column: "Survived", problem_type: "classification", reason: "Outcome-like", changed_by_plan: false },
      { column: "Embarked", problem_type: "classification", reason: "3 categories", changed_by_plan: true },
      { column: "Fare", problem_type: "regression", reason: "Continuous", changed_by_plan: true },
    ];
    render(<ModelPanel session={{ ...session, state: "executed", target: "Fare" }} runs={null}
      suggestions={suggestions} onTrain={vi.fn()} />);
    const options = Array.from((screen.getByLabelText(/column to predict/i) as HTMLSelectElement).options)
      .map((o) => o.value);
    expect(options).toContain("Survived");
    expect(options).not.toContain("Embarked");
    expect(options).toContain("Fare"); // the session's own target always stays
  });
});
