/** Spec 08 AC-11 / FR-RP-16: report actions on the Download screen. Written before the component. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { session } from "@/test/fixtures";
import { ReportPanel } from "./ReportPanel";

describe("Spec 08 report panel", () => {
  test("test_rp_ac11_create_report_before_one_exists", async () => {
    const onCreate = vi.fn();
    render(<ReportPanel session={{ ...session, state: "modeled" }} source={null} busy={false} onCreate={onCreate} />);
    expect(screen.queryByRole("link", { name: /open report/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /create report/i }));
    expect(onCreate).toHaveBeenCalledWith(false);
  });

  test("test_rp_ac11_links_and_summary_source_once_reported", async () => {
    const onCreate = vi.fn();
    render(<ReportPanel session={{ ...session, state: "reported" }} source="llm" busy={false} onCreate={onCreate} />);

    const open = screen.getByRole("link", { name: /open report/i });
    expect(open).toHaveAttribute("href", `/api/v1/sessions/${session.id}/report`);
    expect(open).toHaveAttribute("target", "_blank");
    expect(open.getAttribute("rel")).toContain("noopener");
    expect(screen.getByRole("link", { name: /download all/i }))
      .toHaveAttribute("href", `/api/v1/sessions/${session.id}/bundle.zip`);
    expect(screen.getByText(/summary written by the ai/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /rewrite summary/i }));
    expect(onCreate).toHaveBeenCalledWith(true);
  });

  test("test_rp_fr16_template_source_and_progress", () => {
    const { rerender } = render(
      <ReportPanel session={{ ...session, state: "reported" }} source="template" busy={false} onCreate={vi.fn()} />,
    );
    expect(screen.getByText(/template summary/i)).toBeInTheDocument();
    rerender(<ReportPanel session={{ ...session, state: "modeled" }} source={null} busy onCreate={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent(/building the report/i);
  });
});
