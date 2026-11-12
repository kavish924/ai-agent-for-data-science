/** Spec 06 AC-10 / FR-CH-13: chart gallery on the Download screen. Written before the component. */
import { render, screen, waitForElementToBeRemoved, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";
import type { ChartManifest } from "@/lib/api/client";
import { ChartGallery } from "./ChartGallery";

const manifest: ChartManifest = {
  status: "completed",
  max_charts: 12,
  duration_ms: 420,
  charts: [
    { file: "01_correlation.png", kind: "correlation", column: null, title: "Correlation", before_overlay: false },
    { file: "02_distribution_Age.png", kind: "distribution", column: "Age", title: "Age — distribution", before_overlay: true },
    { file: "03_bar_Sex.png", kind: "bar", column: "Sex", title: "Sex — top values", before_overlay: false },
  ],
  skipped: [
    { kind: "missing_map", column: null, reason: "no missing values" },
    { kind: "column", column: "Name", reason: "identifier column (no chart)" },
  ],
};

describe("Spec 06 chart gallery", () => {
  test("test_ch_ac10_gallery_shows_each_chart_and_skips", async () => {
    render(<ChartGallery sessionId="abc" manifest={manifest} />);

    const images = screen.getAllByRole("img");
    expect(images).toHaveLength(3);
    expect(images.map((img) => img.getAttribute("alt"))).toEqual([
      "Correlation",
      "Age — distribution",
      "Sex — top values",
    ]);
    expect(images[1]).toHaveAttribute("src", "/api/v1/sessions/abc/charts/02_distribution_Age.png");
    expect(screen.getByText(/before vs after/i)).toBeInTheDocument(); // overlay badge on Age

    await userEvent.click(screen.getByRole("button", { name: /2 charts skipped/i }));
    expect(screen.getByText("no missing values")).toBeInTheDocument();
    expect(screen.getByText("identifier column (no chart)")).toBeInTheDocument();
  });

  test("test_ch_fr13_chart_opens_large_and_closes_with_escape", async () => {
    const user = userEvent.setup();
    render(<ChartGallery sessionId="abc" manifest={manifest} />);
    await user.click(screen.getByRole("button", { name: /open age — distribution/i }));

    const dialog = screen.getByRole("dialog", { name: "Age — distribution" });
    expect(within(dialog).getByRole("img")).toHaveAttribute("alt", "Age — distribution");
    await user.keyboard("{Escape}");
    // the dialog leaves through an exit animation, so wait for it to be removed
    await waitForElementToBeRemoved(() => screen.queryByRole("dialog"));
  });

  test("test_ch_ac6_failed_charts_explained_without_breaking", () => {
    render(
      <ChartGallery
        sessionId="abc"
        manifest={{ ...manifest, status: "failed", charts: [], skipped: [], error: "chart rendering failed: boom" }}
      />,
    );
    expect(screen.getByText(/charts couldn't be created/i)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
