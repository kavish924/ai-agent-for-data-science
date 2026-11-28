// @vitest-environment node
/** Spec 11 AC-8 (frontend fails closed), AC-10 (access gate), AC-11 (token added to the /api/v1 proxy). */
import { NextRequest } from "next/server";
import { afterEach, describe, expect, test, vi } from "vitest";
import { GET as healthz } from "@/app/healthz/route";
import { middleware } from "./middleware";

const BASE = "http://app.test";
const ok = { ACCESS_USER: "demo", ACCESS_PASSWORD: "s3cret", INTERNAL_API_TOKEN: "tok", BACKEND_URL: "https://api.test" };

function req(path: string, headers: Record<string, string> = {}) {
  return new NextRequest(new URL(path, BASE), { headers });
}
const basic = (user: string, pass: string) => ({ authorization: `Basic ${btoa(`${user}:${pass}`)}` });
const rewriteOf = (res: Response) => res.headers.get("x-middleware-rewrite");

function withEnv(env: Record<string, string | undefined>) {
  for (const key of ["APP_ENV", "ACCESS_USER", "ACCESS_PASSWORD", "INTERNAL_API_TOKEN", "BACKEND_URL"]) {
    vi.stubEnv(key, env[key] ?? "");
  }
}

afterEach(() => vi.unstubAllEnvs());

describe("Spec 11 access gate", () => {
  test("test_dp_ac10_gate_requires_the_shared_password", async () => {
    withEnv(ok);
    for (const path of ["/", "/samples/titanic.csv", "/api/v1/health"]) {
      for (const headers of [{}, basic("demo", "wrong"), basic("other", "s3cret")]) {
        const res = middleware(req(path, headers));
        expect(res.status, `${path} ${JSON.stringify(headers)}`).toBe(401);
        expect(res.headers.get("www-authenticate")).toMatch(/^Basic /);
      }
      expect(middleware(req(path, basic("demo", "s3cret"))).status).toBe(200);
    }
    const health = middleware(req("/healthz"));
    expect(health.status).toBe(200);
    expect(await (await healthz()).json()).toEqual({ status: "ok" });
  });

  test("test_dp_ac10_nothing_is_gated_in_development", () => {
    withEnv({});
    expect(middleware(req("/")).status).toBe(200);
    expect(middleware(req("/samples/titanic.csv")).status).toBe(200);
  });

  test("test_dp_ac8_frontend_fails_closed_when_production_is_misconfigured", async () => {
    for (const missing of ["ACCESS_PASSWORD", "INTERNAL_API_TOKEN", "BACKEND_URL"]) {
      withEnv({ ...ok, APP_ENV: "production", [missing]: undefined });
      const res = middleware(req("/", basic("demo", "s3cret")));
      expect(res.status, missing).toBe(503);
      expect(await res.text()).toContain(missing);
      expect(middleware(req("/healthz")).status).toBe(200);
    }
    withEnv({ ...ok, APP_ENV: "production" });
    expect(middleware(req("/", basic("demo", "s3cret"))).status).toBe(200);
  });
});

describe("Spec 11 /api/v1 proxy", () => {
  test("test_dp_ac11_proxy_adds_the_internal_token", () => {
    withEnv(ok);
    const res = middleware(req("/api/v1/sessions/abc?x=1", basic("demo", "s3cret")));
    expect(rewriteOf(res)).toBe("https://api.test/api/v1/sessions/abc?x=1");
    expect(res.headers.get("x-middleware-request-x-internal-token")).toBe("tok");
    // the user's password is not forwarded to the backend
    expect(res.headers.get("x-middleware-override-headers")?.split(",")).not.toContain("authorization");
  });

  test("test_dp_ac11_dev_proxy_goes_to_the_local_backend", () => {
    withEnv({});
    const res = middleware(req("/api/v1/health"));
    expect(rewriteOf(res)).toBe("http://127.0.0.1:8000/api/v1/health");
    expect(res.headers.get("x-middleware-request-x-internal-token")).toBeNull();
  });
});
