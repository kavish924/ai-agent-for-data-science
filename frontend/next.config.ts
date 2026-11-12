import type { NextConfig } from "next";

// Same-origin proxy to the FastAPI backend (Spec 04 FR-RV-11): the browser only ever
// calls /api/v1/*, so no CORS and no backend URL in client code. BACKEND_URL is
// server-side configuration, never user input.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // No next/image optimisation: avoids running sharp (see docs/CHECKLIST.md follow-ups).
  images: { unoptimized: true },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
};

export default nextConfig;
