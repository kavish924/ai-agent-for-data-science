import type { NextConfig } from "next";
import { MIDDLEWARE_MAX_BODY, resolveProxyTimeout } from "./src/lib/deploy-config";

// The browser only ever calls /api/v1/* on this origin (Spec 04 FR-RV-11). The proxy to
// the FastAPI backend lives in src/middleware.ts (Spec 11 FR-DP-14), because a standalone
// build would fix next.config rewrites at build time and BACKEND_URL is a runtime setting.
const nextConfig: NextConfig = {
  // Spec 11 FR-DP-02: a self-contained server for the container image.
  output: "standalone",
  // No next/image optimisation: avoids running sharp (see docs/CHECKLIST.md follow-ups).
  images: { unoptimized: true },
  experimental: {
    // Spec 11 FR-DP-08: rewrites otherwise give up after 30 s, before a slow plan answers.
    proxyTimeout: resolveProxyTimeout(process.env.PROXY_TIMEOUT_MS),
    // Spec 11 FR-DP-09: middleware would otherwise truncate uploads over 10 MB.
    middlewareClientMaxBodySize: MIDDLEWARE_MAX_BODY,
  },
};

export default nextConfig;
