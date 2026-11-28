# Spec 11 — Deployment

> **Status:** Draft · **Source:** PRD §8, §13.4 · **Milestone:** M10 · **Supersedes:** Spec 00 §8 "Deployment: local demo only"

## Purpose

Make the app runnable as a **single-tenant hosted demo** on one container host: built
images, one `docker compose up`, persistent storage, secrets from the environment, access
control in front of everything, health checks, and a CI job that proves the deployed stack
works end to end. Today the app only runs as two dev servers on `localhost` (Spec 00 §8);
nothing defines how it runs anywhere else.

The deployment keeps the v1 architecture (design D5): one FastAPI process with SQLite and a
local artifact directory, one Next.js server proxying `/api/v1`. Postgres, object storage,
multiple workers and user accounts stay out of scope (see Out of Scope).

## User Story

> As the operator, I want to start the whole app on a server with one command and share a
> URL with a few trusted people, so they can try it on their own CSVs without installing
> anything, while their uploads stay private and the app survives restarts.

## Requirements

### Build

| ID | Requirement |
|---|---|
| FR-DP-01 | **Backend image.** `backend/Dockerfile` builds a runnable image from a pinned `python:3.11-slim` base: installs the package without dev extras (`pip install .`), runs as a non-root user, and starts `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`. No `.env`, keys, `storage/` or tests are copied into the image (a `.dockerignore` enforces it). |
| FR-DP-02 | **Frontend image.** `frontend/Dockerfile` is a multi-stage build on a pinned `node:22` base: `npm ci`, `npm run build` with Next.js `output: "standalone"`, and a slim runtime stage that runs `node server.js` as a non-root user on port 3000. `BACKEND_URL` is read at runtime (server-side only, never sent to the browser). |
| FR-DP-03 | **Sample datasets in the image.** The `/samples/{name}` route reads from `SAMPLES_DIR` when set, else from `<cwd>/../samples` (today's behaviour, unchanged for dev). The frontend image copies `samples/` and sets `SAMPLES_DIR`. The served names stay the fixed whitelist (Spec 04 FR-RV-13). |
| FR-DP-04 | **Version stamp.** Both images take a build argument `APP_VERSION` (the git SHA in CI, `dev` otherwise). `GET /api/v1/health` returns `{"status": "ok", "version": APP_VERSION}`. Images are tagged with the same SHA, so a deploy names exactly one build and a rollback is "run the previous tag". |

### Runtime topology

| ID | Requirement |
|---|---|
| FR-DP-05 | **Compose stack.** `deploy/compose.yaml` runs `backend` and `frontend` (and the optional `proxy` of FR-DP-15). Only the public entry point publishes a host port; the backend is reachable only on the compose network. `BACKEND_URL=http://backend:8000`. Both services `restart: unless-stopped`. |
| FR-DP-06 | **Single backend process.** The backend runs exactly one worker process. Background jobs are in-process `BackgroundTasks`, the startup recovery sweep (Spec 10 NFR-07) marks every in-flight session as interrupted, and the retention sweeper runs per process, so a second worker would corrupt the state of sessions the first is running. When `APP_ENV=production` the app refuses to start if `WEB_CONCURRENCY` (or `--workers`) is above 1, with a message naming this requirement. |
| FR-DP-07 | **Persistent storage.** `DB_PATH` and `STORAGE_ROOT` point into one named volume mounted at `/data` (`/data/app.db`, `/data/sessions/…`, `/data/logs/…`). Sessions, artifacts and recovery state survive container restarts and image upgrades. The image's own filesystem holds no state. |
| FR-DP-08 | **Proxy timeouts cover the slowest synchronous call.** `POST /plan` and `POST /report` call the LLM synchronously: worst case `PLAN_MAX_RETRIES × LLM_TIMEOUT_S` plus backoff (about 190 s with the defaults). Next.js rewrites time out after 30 s by default, so `next.config.ts` sets `experimental.proxyTimeout` from `PROXY_TIMEOUT_MS`, defaulting to `(PLAN_MAX_RETRIES × LLM_TIMEOUT_S + 30) × 1000`; any reverse proxy in front (FR-DP-15) uses at least the same read timeout. *This also fixes the local dev setup, where a plan slower than 30 s is cut off by the proxy today.* |
| FR-DP-09 | **Upload size at every hop.** Every hop before FastAPI accepts a request body of at least `MAX_FILE_SIZE_MB` + 1 MB, so the app, not a proxy, returns the Spec 01 `413` with its normal error envelope. |

### Configuration and secrets

| ID | Requirement |
|---|---|
| FR-DP-10 | **Twelve-factor config.** Every setting comes from the environment (`backend/app/config.py`, `BACKEND_URL`, `PROXY_TIMEOUT_MS`, `SAMPLES_DIR`, `APP_VERSION`, FR-DP-13/14's access variables). `deploy/.env.example` lists each one with its default and whether it is a secret. A real `deploy/.env` is gitignored. |
| FR-DP-11 | **Fail fast in production.** With `APP_ENV=production` the backend refuses to start, naming the missing variable, when: `LLM_PROVIDER=gemini` and the chosen backend is not configured (`GEMINI_API_KEY` for `aistudio`; `GOOGLE_CLOUD_PROJECT` plus readable credentials for `vertex`, Spec 03 FR-PL-19); or access control (FR-DP-13) is not configured. In development (`APP_ENV` unset) behaviour is unchanged: a missing key gives the existing `503` at plan time. |
| FR-DP-12 | **Secrets handling.** The Gemini key and the access password come only from environment variables or files mounted read-only (`*_FILE` variants, e.g. `GEMINI_API_KEY_FILE`, `ACCESS_PASSWORD_FILE`). For Vertex, a service-account key file is mounted read-only and named by `GOOGLE_APPLICATION_CREDENTIALS`. No secret appears in an image layer, a log line, `GET /health`, or an error message. |

### Access control and transport

| ID | Requirement |
|---|---|
| FR-DP-13 | **Access gate.** When `ACCESS_USER` and `ACCESS_PASSWORD` are set, the frontend server requires HTTP Basic auth for every route (pages, `/samples/*` and the `/api/v1` proxy) before anything else runs, and answers `401` with `WWW-Authenticate` otherwise. Credentials are compared in constant time. This is a shared-password gate for a trusted group, not user accounts. |
| FR-DP-14 | **Backend trusts only the frontend.** When `INTERNAL_API_TOKEN` is set, every backend route except `/api/v1/health` requires the header `X-Internal-Token` with that value (constant-time compare) and returns `401` with the error envelope otherwise. The frontend proxy adds the header server-side; the browser never sees it. This keeps the backend closed even if its port is exposed by mistake. |
| FR-DP-15 | **TLS at the edge.** An optional `proxy` service (Caddy) in the compose file terminates HTTPS for `PUBLIC_HOSTNAME` with automatic certificates and forwards to `frontend:3000` with FR-DP-08's timeout and FR-DP-09's body limit. Without it, the operator puts their own TLS-terminating proxy in front; plain HTTP is only for `localhost`. |
| FR-DP-16 | **CORS is configurable.** The backend's allowed origins come from `CORS_ORIGINS` (comma-separated, default today's two localhost origins). In the compose stack it is empty: the browser only talks to the frontend's own origin (Spec 04 FR-RV-11), so the backend needs no CORS at all. |

### Operations

| ID | Requirement |
|---|---|
| FR-DP-17 | **Health and readiness.** `GET /api/v1/health` is liveness (FR-DP-04). `GET /api/v1/ready` returns `200` only when the database answers a query and `STORAGE_ROOT` is writable, else `503` with which check failed; it never calls the LLM. Compose healthchecks use `/ready` for the backend and `/` for the frontend, and the frontend waits for a healthy backend. |
| FR-DP-18 | **Logs to stdout.** The structured JSON log lines of Spec 10 go to stdout, where the container runtime collects them. The rotating file under `STORAGE_ROOT/logs` is kept only when `LOG_TO_FILE=true`. The privacy rules of Spec 10 NFR-03/06 are unchanged: no row values, prompts or secrets in any log. |
| FR-DP-19 | **Graceful stop and restart.** On `SIGTERM` the backend stops accepting requests and exits within the compose `stop_grace_period` (30 s). A job cut off by the stop is handled on the next start by the existing recovery sweep (Spec 10 NFR-07): the session becomes retryable, never stuck. |
| FR-DP-20 | **Resource envelope.** The compose file sets memory limits (backend 2 GiB, frontend 512 MiB). The backend must complete the Spec 10 NFR-12 max-size fixture (100,000 rows) inside its limit; the limit and the measured peak are recorded in the runbook. |
| FR-DP-21 | **Hosted privacy notice.** When `APP_ENV=production`, the upload screen states that uploads are stored on the server for `RETENTION_DAYS` days and then deleted, in addition to the existing notice of what is sent to the LLM (Spec 10 NFR-03). The retention sweep (Spec 10 NFR-08) is the deletion mechanism; there are no backups of `/data`. |
| FR-DP-22 | **Runbook.** `docs/deployment.md` covers: prerequisites, first deploy, every environment variable (from `deploy/.env.example`), upgrading to a new image tag, rollback, reading logs, rotating the access password and the Gemini key, where data lives and how retention deletes it, and the known limits (single process, single host, shared password). |

### Verification

| ID | Requirement |
|---|---|
| FR-DP-23 | **Deployment smoke in CI.** A CI job builds both images, starts the compose stack with `LLM_PROVIDER=offline`, `APP_ENV=production`, test access credentials and a test internal token, waits for both healthchecks, then drives the public entry point only: unauthenticated request → `401`; authenticated upload of a sample → profile → plan → approve → execute → charts → model → report → bundle, all succeeding. It then restarts the backend container and checks that the session and its report are still there (FR-DP-07). |

## Acceptance Criteria

- **AC-1** *(FR-DP-01, 02)* Given the repo, when both images are built, then they start as non-root users, the
  backend image contains no `.env`, `storage/`, `tests/` or dev dependencies, and the frontend serves `/` with `200`.
- **AC-2** *(FR-DP-03)* Given `SAMPLES_DIR` pointing to a folder with `titanic.csv`, when `/samples/titanic.csv` is
  requested, then the file is served; without `SAMPLES_DIR` the route still reads `<cwd>/../samples`; a name outside
  the whitelist is `404` either way.
- **AC-3** *(FR-DP-04, FR-DP-17)* Given `APP_VERSION=abc123`, then `GET /health` returns `{"status":"ok","version":"abc123"}`;
  `GET /ready` is `200` with a working DB and writable storage, and `503` naming the failed check when the DB file is
  unreadable or `STORAGE_ROOT` is read-only. `/ready` makes no LLM call.
- **AC-4** *(FR-DP-06)* Given `APP_ENV=production` and `WEB_CONCURRENCY=2`, when the backend starts, then it exits with
  an error naming FR-DP-06; with `WEB_CONCURRENCY=1` or `APP_ENV` unset it starts.
- **AC-5** *(FR-DP-07, FR-DP-23)* Given a session that reached `reported`, when the backend container is restarted,
  then the session, its cleaned CSV and its report are still served.
- **AC-6** *(FR-DP-08)* Given `PLAN_MAX_RETRIES=3` and `LLM_TIMEOUT_S=60`, then the resolved proxy timeout is at least
  190 s; given an LLM stub that answers after 45 s, when `POST /plan` goes through the frontend proxy, then it returns
  the backend's `201`, not a proxy error.
- **AC-7** *(FR-DP-09)* Given `MAX_FILE_SIZE_MB=25`, when a 26 MB file is uploaded through the public entry point, then
  the response is the app's `413` with the Spec 09 error envelope, not a proxy's own error page.
- **AC-8** *(FR-DP-11)* Given `APP_ENV=production`, when the backend starts with `LLM_PROVIDER=gemini` and no key (or
  `vertex` with no project), or with access control unset, then it exits naming the missing variable; with
  `LLM_PROVIDER=offline` and access control set it starts.
- **AC-9** *(FR-DP-12)* Given `GEMINI_API_KEY_FILE` and `ACCESS_PASSWORD_FILE`, then their file contents are used; when
  the key is set, no log line emitted during a full mocked run, no `/health` or `/ready` body and no error response
  contains it.
- **AC-10** *(FR-DP-13)* Given `ACCESS_USER`/`ACCESS_PASSWORD`, then a request to `/`, to `/samples/titanic.csv` and to
  `/api/v1/health` through the frontend without credentials, or with a wrong password, is `401` with
  `WWW-Authenticate: Basic`, and with the right credentials it succeeds; without the variables nothing is gated (dev).
- **AC-11** *(FR-DP-14)* Given `INTERNAL_API_TOKEN`, then a backend request without the header or with a wrong value is
  `401` with the error envelope, `/api/v1/health` is open, and a request through the frontend proxy succeeds without
  the browser sending the header.
- **AC-12** *(FR-DP-16)* Given `CORS_ORIGINS=https://example.org`, then a preflight from that origin is allowed and one
  from `http://localhost:3000` is not; with `CORS_ORIGINS` unset, today's localhost origins are allowed.
- **AC-13** *(FR-DP-18)* Given `LOG_TO_FILE` unset, then log lines go to stdout and no file is created under
  `STORAGE_ROOT/logs`; with `LOG_TO_FILE=true` the rotating file is written as today.
- **AC-14** *(FR-DP-21)* Given `APP_ENV=production` and `RETENTION_DAYS=7`, the upload screen shows the server-storage
  notice with "7 days"; without `APP_ENV=production` it is not shown.
- **AC-15** *(FR-DP-23)* The CI deployment smoke job passes: images build, healthchecks pass, the unauthenticated
  request is `401`, the authenticated offline flow reaches `reported` with a downloadable bundle, and AC-5 holds after a
  backend restart.

## Dependencies

- Spec 01 (upload limits, `413`), Spec 03 (FR-PL-17 offline planner, FR-PL-18 backoff, FR-PL-19 Gemini backends),
  Spec 04 (FR-RV-11 same-origin proxy, FR-RV-13 samples), Spec 09 (error envelope, endpoints),
  Spec 10 (NFR-03/06 privacy and logs, NFR-07 recovery, NFR-08 retention, NFR-12 max-size fixture).
- `09-api-contracts.md` gains `GET /api/v1/ready`, the `version` field of `/health`, and the `401` responses of
  FR-DP-13/14 when this spec is approved.

## Test Plan

- **Unit (backend):** settings validation for production (AC-4, AC-8), `*_FILE` secret loading (AC-9), CORS origins
  parsing (AC-12), log sink selection (AC-13).
- **Integration (backend, TestClient):** `/health` version and `/ready` with a good and a broken DB/storage (AC-3),
  internal-token middleware (AC-11), secret never in logs or responses (AC-9).
- **Frontend (Vitest):** samples route with and without `SAMPLES_DIR` (AC-2), Basic-auth middleware (AC-10), proxy
  timeout resolution (AC-6 first half), production retention notice (AC-14).
- **Deployment smoke (CI, Docker):** `deploy/smoke.sh` or `scripts/smoke_deploy.py` against the compose stack (AC-1,
  AC-5, AC-6 second half, AC-7, AC-15).

## Out of Scope

- User accounts, sign-up, per-user data separation, audit logs (PRD §3 non-goal; the shared password is the v1 gate).
- Postgres, object storage, a job queue, more than one backend worker or host (design D5's upgrade path; FR-DP-06
  forbids multiple workers until that work exists).
- Kubernetes, autoscaling, serverless platforms whose filesystem does not persist (Cloud Run, Vercel functions) —
  they cannot keep SQLite and `/data`.
- Splitting the frontend onto Vercel (architecture.md §6 "hosting later"): the samples route and the server-side
  proxy assume both services sit on one private network.
- Backups and disaster recovery: sessions are temporary by design (`RETENTION_DAYS`).
- Rate limiting and LLM cost caps beyond the access gate and the existing bounded retries.

## Open Questions

- **Hosting target.** Assumed: any single VM or container host that runs Docker Compose with a persistent volume
  (e.g. a small cloud VM, Fly.io, Render with a disk). Which one is used decides the TLS option (FR-DP-15) and the
  memory limit (FR-DP-20).
- **Access gate.** Assumed: one shared Basic-auth password (FR-DP-13). Alternatives: an identity-aware proxy in front
  (Cloudflare Access, Google IAP), or per-person passwords. Any of them can replace FR-DP-13 without touching the app.
- **Gemini in production.** AI Studio key or Vertex AI (Spec 03 FR-PL-19)? Vertex needs a service-account key file
  mounted into the backend; AI Studio needs only `GEMINI_API_KEY`.
- **Data location.** Should hosted uploads stay in a given region? This decides where the host runs.
- **Long synchronous calls.** FR-DP-08 raises proxy timeouts to fit `POST /plan`. Making planning a background job
  with polling (like execute and model) would remove the long request entirely; it changes Spec 03/09 and is not
  part of this spec.

## Tasks

- [ ] Approve this spec (status → Approved), update `09-api-contracts.md`, add the `dp` prefix rows to
      `traceability.md`
- [ ] FR-DP-01..04 images, samples dir, version stamp (AC-1..3)
- [ ] FR-DP-05..09 compose, single worker, volume, proxy timeout, body size (AC-4..7)
- [ ] FR-DP-10..12 config, fail-fast, secrets (AC-8, AC-9)
- [ ] FR-DP-13..16 access gate, internal token, TLS proxy, CORS (AC-10..12)
- [ ] FR-DP-17..22 readiness, logs, shutdown, resources, privacy notice, runbook (AC-3, AC-13, AC-14)
- [ ] FR-DP-23 CI deployment smoke (AC-15)

## Changelog

- 2026-11-28 — Draft: first deployment spec (single-tenant hosted demo on one container host). Records that the
  Next.js proxy's 30 s default timeout cuts off slow `POST /plan` calls today (FR-DP-08).
