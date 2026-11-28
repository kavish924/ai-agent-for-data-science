// @vitest-environment node
/** Spec 11 AC-6: the /api/v1 proxy waits long enough for the slowest LLM call. */
import { describe, expect, test } from "vitest";
import { resolveProxyTimeout } from "./deploy-config";

describe("Spec 11 proxy timeout", () => {
  test("test_dp_ac6_proxy_timeout_defaults_to_five_minutes", () => {
    expect(resolveProxyTimeout(undefined)).toBe(300_000);
    expect(resolveProxyTimeout("")).toBe(300_000);
    expect(resolveProxyTimeout("1000")).toBe(1_000);
    expect(resolveProxyTimeout("not a number")).toBe(300_000);
  });
});
