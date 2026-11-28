/**
 * Spec 11 runtime gate, in front of every route:
 * - FR-DP-11: in production, a missing setting closes the app (503), never opens it;
 * - FR-DP-13: one shared Basic-auth password when ACCESS_USER/ACCESS_PASSWORD are set;
 * - FR-DP-14: /api/v1 is proxied to BACKEND_URL with the internal token added server-side.
 * /healthz stays open so platform health checks never need the password (FR-DP-17).
 *
 * The proxy lives here, not in next.config rewrites, because a standalone build fixes
 * rewrites at build time while BACKEND_URL is only known at runtime.
 */
import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";
import { LOCAL_BACKEND_URL } from "@/lib/deploy-config";

const REALM = 'Basic realm="Data Science Agent", charset="UTF-8"';
const REQUIRED_IN_PRODUCTION = ["ACCESS_USER", "ACCESS_PASSWORD", "INTERNAL_API_TOKEN", "BACKEND_URL"] as const;

export const config = {
  runtime: "nodejs",
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

function env(name: string): string | undefined {
  const value = process.env[name];
  return value ? value : undefined;
}

/** Constant-time comparison of two strings of any length (hash both first). */
function same(a: string, b: string): boolean {
  const digest = (s: string) => createHash("sha256").update(s, "utf8").digest();
  return timingSafeEqual(digest(a), digest(b));
}

function authorized(request: NextRequest, user: string, password: string): boolean {
  const header = request.headers.get("authorization") ?? "";
  if (!header.startsWith("Basic ")) return false;
  let decoded: string;
  try {
    decoded = Buffer.from(header.slice(6).trim(), "base64").toString("utf8");
  } catch {
    return false;
  }
  const colon = decoded.indexOf(":");
  if (colon < 0) return false;
  // evaluate both comparisons so timing does not reveal which one failed
  const userOk = same(decoded.slice(0, colon), user);
  const passwordOk = same(decoded.slice(colon + 1), password);
  return userOk && passwordOk;
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname, search } = request.nextUrl;
  if (pathname === "/healthz") return NextResponse.next();

  if (env("APP_ENV") === "production") {
    const missing = REQUIRED_IN_PRODUCTION.filter((name) => !env(name));
    if (missing.length) {
      return new NextResponse(`Not configured: ${missing.join(", ")} must be set (Spec 11 FR-DP-11).`, {
        status: 503,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
  }

  const user = env("ACCESS_USER");
  const password = env("ACCESS_PASSWORD");
  if (user && password && !authorized(request, user, password)) {
    return new NextResponse("Authentication required.", {
      status: 401,
      headers: { "www-authenticate": REALM, "content-type": "text/plain; charset=utf-8" },
    });
  }

  if (pathname.startsWith("/api/v1/") || pathname === "/api/v1") {
    const backend = (env("BACKEND_URL") ?? LOCAL_BACKEND_URL).replace(/\/+$/, "");
    const headers = new Headers(request.headers);
    headers.delete("authorization"); // the shared password stays at the edge
    const token = env("INTERNAL_API_TOKEN");
    if (token) headers.set("x-internal-token", token);
    return NextResponse.rewrite(new URL(`${backend}${pathname}${search}`), { request: { headers } });
  }

  return NextResponse.next();
}
