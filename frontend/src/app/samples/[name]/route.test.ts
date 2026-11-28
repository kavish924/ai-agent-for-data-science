// @vitest-environment node
/** Spec 11 AC-2: samples come from SAMPLES_DIR when set, else <cwd>/../samples; the whitelist still applies. */
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, test, vi } from "vitest";
import { GET } from "./route";

const call = (name: string) => GET(new Request(`http://app.test/samples/${name}`), { params: Promise.resolve({ name }) });

afterEach(() => vi.unstubAllEnvs());

describe("Spec 11 samples route", () => {
  test("test_dp_ac2_samples_dir_is_configurable", async () => {
    const dir = mkdtempSync(path.join(tmpdir(), "samples-"));
    writeFileSync(path.join(dir, "titanic.csv"), "a,b\n1,2\n");
    vi.stubEnv("SAMPLES_DIR", dir);
    const res = await call("titanic.csv");
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("a,b\n1,2\n");
    expect((await call("secrets.csv")).status).toBe(404);
  });

  test("test_dp_ac2_default_is_the_repo_samples_folder", async () => {
    vi.stubEnv("SAMPLES_DIR", "");
    const res = await call("titanic.csv");
    expect(res.status).toBe(200);
    expect((await res.text()).split("\n")[0]).toContain("Survived");
    expect((await call("../package.json")).status).toBe(404);
  });
});
