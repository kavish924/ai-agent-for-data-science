/** Spec 04 AC-9 (upload errors), AC-10 (target picker), FR-RV-12 (screen per state). */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ApiError, api } from "@/lib/api/client";
import { profile, session } from "@/test/fixtures";
import { screenFor } from "./AgentFlow";
import { ProfileScreen } from "./ProfileScreen";
import { UploadScreen } from "./UploadScreen";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { ...actual.api, upload: vi.fn(), setTarget: vi.fn(), generatePlan: vi.fn() } };
});

const mocked = vi.mocked(api);

beforeEach(() => vi.clearAllMocks());

describe("Spec 04 screens", () => {
  test("test_rv_ac9_upload_error_shows_server_message", async () => {
    mocked.upload.mockRejectedValue(new ApiError(413, "file_too_large", "File exceeds the 25 MB limit."));
    const onUploaded = vi.fn();
    render(<UploadScreen onUploaded={onUploaded} />);

    const file = new File(["a,b\n1,2\n"], "big.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText(/drop a csv here/i), file);

    expect(await screen.findByRole("alert")).toHaveTextContent("File exceeds the 25 MB limit.");
    expect(onUploaded).not.toHaveBeenCalled();
    expect(screen.getByText(/drop a csv here/i)).toBeInTheDocument(); // still on the upload screen
  });

  test("test_rv_ac10_id_like_columns_not_offered_as_target", () => {
    render(<ProfileScreen session={{ ...session, state: "profiled" }} profile={profile} onPlanned={vi.fn()} />);
    const options = Array.from(
      (screen.getByLabelText(/prediction target/i) as HTMLSelectElement).options,
    ).map((option) => option.value);
    expect(options).toEqual(["", "Survived", "Age", "Cabin", "Embarked", "Fare"]);
    expect(options).not.toContain("PassengerId");
  });

  test("test_rv_fr14_missing_llm_key_is_explained", async () => {
    mocked.generatePlan.mockRejectedValue(new ApiError(503, "llm_not_configured", "needs key"));
    render(<ProfileScreen session={{ ...session, state: "profiled" }} profile={profile} onPlanned={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /generate plan with ai/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/isn't configured/);
  });

  test("test_rv_fr12_screen_follows_session_state", () => {
    expect(screenFor(null)).toBe("Upload");
    expect(screenFor({ ...session, state: "uploaded" })).toBe("Profile");
    expect(screenFor({ ...session, state: "profiled" })).toBe("Profile");
    expect(screenFor({ ...session, state: "awaiting_approval" })).toBe("Review plan");
    expect(screenFor({ ...session, state: "approved" })).toBe("Review plan");
    expect(screenFor({ ...session, state: "executing" })).toBe("Run");
    expect(screenFor({ ...session, state: "executed" })).toBe("Download");
  });
});
