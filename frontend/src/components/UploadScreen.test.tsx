/** Spec 11 AC-14 (hosted storage notice) and AC-19 (limits come from GET /config). */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { api, type PublicConfig } from "@/lib/api/client";
import { UploadScreen } from "./UploadScreen";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { ...actual.api, config: vi.fn() } };
});

const mocked = vi.mocked(api);
const hostedFree: PublicConfig = {
  max_file_size_mb: 5, max_rows: 20_000, retention_days: 7, storage_persistent: false, hosted: true,
};

beforeEach(() => vi.clearAllMocks());

describe("Spec 11 upload screen", () => {
  test("test_dp_ac19_limits_come_from_the_backend", async () => {
    mocked.config.mockResolvedValue(hostedFree);
    render(<UploadScreen onUploaded={vi.fn()} />);
    expect(await screen.findByText(/Up to 5 MB and 20,000 rows/)).toBeInTheDocument();
  });

  test("test_dp_ac19_local_defaults_when_config_fails", async () => {
    mocked.config.mockRejectedValue(new Error("offline"));
    render(<UploadScreen onUploaded={vi.fn()} />);
    expect(await screen.findByText(/Up to 25 MB and 100,000 rows/)).toBeInTheDocument();
  });

  test("test_dp_ac14_temporary_storage_notice_when_hosted_without_a_disk", async () => {
    mocked.config.mockResolvedValue(hostedFree);
    render(<UploadScreen onUploaded={vi.fn()} />);
    const notice = await screen.findByText(/kept only temporarily/);
    expect(notice).toHaveTextContent("7 days");
  });

  test("test_dp_ac14_retention_notice_when_hosted_with_a_disk", async () => {
    mocked.config.mockResolvedValue({ ...hostedFree, storage_persistent: true });
    render(<UploadScreen onUploaded={vi.fn()} />);
    expect(await screen.findByText(/kept on the server for 7 days/)).toBeInTheDocument();
    expect(screen.queryByText(/kept only temporarily/)).not.toBeInTheDocument();
  });

  test("test_dp_ac14_no_notice_when_not_hosted", async () => {
    mocked.config.mockResolvedValue({ ...hostedFree, hosted: false });
    render(<UploadScreen onUploaded={vi.fn()} />);
    await screen.findByText(/Up to 5 MB/);
    expect(screen.queryByText(/kept only temporarily|kept on the server/)).not.toBeInTheDocument();
  });
});
