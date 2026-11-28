/**
 * Deployment settings shared by next.config.ts and the middleware (Spec 11).
 * Kept free of Next.js imports so next.config.ts can load it.
 */

/** FR-DP-08: worst-case LLM call (3 × 60 s + backoff) plus a sleeping backend waking up. */
export const DEFAULT_PROXY_TIMEOUT_MS = 300_000;

export function resolveProxyTimeout(raw: string | undefined): number {
  const value = Number(raw);
  return raw && Number.isFinite(value) && value > 0 ? value : DEFAULT_PROXY_TIMEOUT_MS;
}

/**
 * FR-DP-09: the proxy must pass the largest upload whole. Next.js buffers request bodies
 * in middleware and silently cuts them at 10 MB by default; this covers the local
 * 25 MB limit with room for the multipart overhead.
 */
export const MIDDLEWARE_MAX_BODY = "30mb";

export const LOCAL_BACKEND_URL = "http://127.0.0.1:8000";
