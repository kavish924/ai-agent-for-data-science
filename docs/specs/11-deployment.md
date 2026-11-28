# Spec 11 — Deployment

> **Status:** In progress · **Source:** PRD §8, §13.4 · **Milestone:** M10 · **Host:** Render (free tier, Singapore) · **Supersedes:** Spec 00 §8 "Deployment: local demo only"

## Purpose

Make the app runnable as a **single-tenant hosted demo** on **Render's free tier**: built
images, a Render Blueprint (`render.yaml`) with two web services in Singapore, secrets from
the environment, a shared password in front of everything, health checks, and a CI job that
proves the deployed stack works end to end. The same images also run locally and in CI
with one `docker compose up`, where storage persists. Today the app only runs as two dev
servers on `localhost` (Spec 00 §8); nothing defines how it runs anywhere else.

The deployment keeps the v1 architecture (design D5): one FastAPI process with SQLite and a
local artifact directory, one Next.js server proxying `/api/v1`. Postgres, object storage,
multiple workers and user accounts stay out of scope (see Out of Scope).

**Free-tier trade-offs, accepted 2026-11-28:** no persistent disk, so sessions are
temporary and disappear when a service restarts, redeploys or sleeps (after about 15
minutes without traffic; the first request after that waits about a minute while it wakes);
512 MB of memory, so hosted uploads are capped lower than locally; no private network, so
the backend has a public URL that only accepts requests carrying the internal token.

## User Story

> As the operator, I want to put the app on a free host and share a URL and a password with a
> few people, so they can try it on their own CSVs without installing anything, knowing their
> uploads stay private and are only kept temporarily.

## Requirements

### Build

| ID | Requirement |
|---|---|
| FR-DP-01 | **Backend image.** `backend/Dockerfile` builds a runnable image from a pinned `python:3.11-slim` base: installs the runtime dependencies listed in `pyproject.toml` (no dev extras), runs from the copied source tree (so `app/templates/` ships with it), runs as a non-root user, and starts one uvicorn worker on `0.0.0.0:${PORT:-8000}` (FR-DP-25). No `.env`, keys, `storage/` or tests are copied into the image (a `.dockerignore` enforces it). |
| FR-DP-02 | **Frontend image.** `frontend/Dockerfile` is a multi-stage build on a pinned `node:22` base: `npm ci`, `npm run build` with Next.js `output: "standalone"`, and a slim runtime stage that runs `node server.js` as a non-root user on `${PORT:-3000}`. `BACKEND_URL` and the access variables are read at runtime on the server only, never sent to the browser. |
| FR-DP-03 | **Sample datasets in the image.** The `/samples/{name}` route reads from `SAMPLES_DIR` when set, else from `<cwd>/../samples` (today's behaviour, unchanged for dev). The frontend image copies `samples/` and sets `SAMPLES_DIR`. The served names stay the fixed whitelist (Spec 04 FR-RV-13). |
| FR-DP-04 | **Version stamp.** `GET /api/v1/health` returns `{"status": "ok", "version": V}` where `V` is `APP_VERSION`, else Render's `RENDER_GIT_COMMIT`, else `"dev"`. A deploy therefore names exactly one commit. |

### Runtime topology

| ID | Requirement |
|---|---|
| FR-DP-05 | **Compose stack (local and CI).** `deploy/compose.yaml` runs the two images as `backend` and `frontend`. Only `frontend` publishes a host port; `backend` is reachable only on the compose network, with `BACKEND_URL=http://backend:8000`. Both services `restart: unless-stopped`. Production runs on Render (FR-DP-24); compose is for local runs and the CI smoke (FR-DP-23). |
| FR-DP-06 | **Single backend process.** The backend runs exactly one worker process. Background jobs are in-process `BackgroundTasks`, the startup recovery sweep (Spec 10 NFR-07) marks every in-flight session as interrupted, and the retention sweeper runs per process, so a second worker would corrupt the state of sessions the first is running. When `APP_ENV=production` the app refuses to start if `WEB_CONCURRENCY` is above 1, with a message naming this requirement. |
| FR-DP-07 | **Storage location and persistence.** `DB_PATH` and `STORAGE_ROOT` point under `/data` (`/data/app.db`, `/data/sessions/…`). In compose, `/data` is a named volume, so sessions survive container restarts and image upgrades. On Render's free tier `/data` is the container's own filesystem: it starts empty on every restart, redeploy or wake-up. `STORAGE_PERSISTENT` (`true`/`false`, default `true`) declares which case applies; it drives the notice of FR-DP-21. |
| FR-DP-08 | **Proxy timeouts cover the slowest synchronous call.** `POST /plan` and `POST /report` call the LLM synchronously: worst case `PLAN_MAX_RETRIES × LLM_TIMEOUT_S` plus backoff (about 190 s with the defaults), plus up to a minute for a sleeping backend to wake. Next.js rewrites time out after 30 s by default, so `next.config.ts` sets `experimental.proxyTimeout` from `PROXY_TIMEOUT_MS`, default 300,000 ms. *This also fixes the local dev setup, where a plan slower than 30 s is cut off by the proxy today.* |
| FR-DP-09 | **Upload size at every hop.** Every hop before FastAPI accepts a request body of at least `MAX_FILE_SIZE_MB` + 1 MB, so the app, not a proxy, returns the Spec 01 `413` with its normal error envelope. |

### Configuration and secrets

| ID | Requirement |
|---|---|
| FR-DP-10 | **Twelve-factor config.** Every setting comes from the environment: the backend's settings (`backend/app/config.py`, now including `APP_ENV`, `CORS_ORIGINS`, `INTERNAL_API_TOKEN`, `LOG_TO_FILE`, `STORAGE_PERSISTENT`, `APP_VERSION`) and the frontend's (`BACKEND_URL`, `PROXY_TIMEOUT_MS`, `SAMPLES_DIR`, `ACCESS_USER`, `ACCESS_PASSWORD`, `INTERNAL_API_TOKEN`, `APP_ENV`). `deploy/.env.example` lists each with its default and whether it is a secret. A real `deploy/.env` is gitignored. |
| FR-DP-11 | **Fail fast, fail closed in production.** With `APP_ENV=production`: the backend refuses to start, naming the missing variable, when `INTERNAL_API_TOKEN` is unset, or when `LLM_PROVIDER=gemini` and the chosen Gemini backend is not configured (`GEMINI_API_KEY` for `aistudio`; `GOOGLE_CLOUD_PROJECT` for `vertex`, Spec 03 FR-PL-19). The frontend answers every route except `/healthz` with `503` and a message naming the missing variable when `ACCESS_USER`, `ACCESS_PASSWORD`, `INTERNAL_API_TOKEN` or `BACKEND_URL` is unset, so a misconfigured deploy is closed, never open. In development (`APP_ENV` unset) behaviour is unchanged. |
| FR-DP-12 | **Secrets handling.** The Gemini key comes from `GEMINI_API_KEY` or a read-only file named by `GEMINI_API_KEY_FILE`. No secret (`GEMINI_API_KEY`, `ACCESS_PASSWORD`, `INTERNAL_API_TOKEN`) appears in an image layer, a log line, `/health`, `/ready`, `/config` or an error message. |

### Access control and transport

| ID | Requirement |
|---|---|
| FR-DP-13 | **Access gate.** When `ACCESS_USER` and `ACCESS_PASSWORD` are set, the frontend server requires HTTP Basic auth for every route (pages, `/samples/*` and the `/api/v1` proxy) except `/healthz` (FR-DP-17), before anything else runs, and answers `401` with `WWW-Authenticate: Basic` otherwise. Credentials are compared in constant time. This is one shared password for a trusted group, not user accounts. |
| FR-DP-14 | **Backend accepts only the frontend.** When `INTERNAL_API_TOKEN` is set, every backend route except `/api/v1/health` and `/api/v1/ready` requires the header `X-Internal-Token` with that value (constant-time compare) and returns `401` with the error envelope otherwise. The frontend adds the header server-side when it proxies `/api/v1`; the browser never sees it. On Render's free tier the backend has a public URL, so this token is what keeps it closed. |
| FR-DP-15 | **TLS.** On Render, Render's managed HTTPS terminates TLS on both `onrender.com` hostnames and redirects HTTP to HTTPS. The frontend reaches the backend over HTTPS. The compose stack is plain HTTP and only for `localhost` and CI. |
| FR-DP-16 | **CORS is configurable.** The backend's allowed origins come from `CORS_ORIGINS` (comma-separated, default today's two localhost origins; empty means none). On Render and in compose it is empty: the browser only talks to the frontend's own origin (Spec 04 FR-RV-11), and the backend is called server-to-server. |

### Operations

| ID | Requirement |
|---|---|
| FR-DP-17 | **Health and readiness.** `GET /api/v1/health` is liveness (FR-DP-04). `GET /api/v1/ready` returns `200` only when the database answers a query and `STORAGE_ROOT` is writable, else `503` with which check failed; it never calls the LLM. The frontend serves `GET /healthz` → `200 {"status":"ok"}` with no data, outside the access gate, so a platform health check never needs the password. Render's health check paths are `/healthz` (frontend) and `/api/v1/ready` (backend); compose uses the same. |
| FR-DP-18 | **Logs to stdout.** The structured JSON log lines of Spec 10 go to stdout, where Render and Docker collect them. The rotating file under `STORAGE_ROOT/logs` is written only when `LOG_TO_FILE=true` (default `true` for local dev, `false` in the images). The privacy rules of Spec 10 NFR-03/06 are unchanged: no row values, prompts or secrets in any log. |
| FR-DP-19 | **Graceful stop and restart.** On `SIGTERM` the backend stops accepting requests and exits within 30 s. With persistent storage, a job cut off by the stop is handled on the next start by the recovery sweep (Spec 10 NFR-07); on the free tier the session is simply gone, which the notice of FR-DP-21 tells users in advance. |
| FR-DP-20 | **Hosted limits fit 512 MB.** On Render the backend runs with `MAX_FILE_SIZE_MB=5`, `MAX_ROWS=20000` and `MODEL_MAX_ROWS=10000`. The CI smoke (FR-DP-23) runs the backend container with a 512 MB memory limit and these settings, and a file at the row cap must go through profile, plan, execute, model and report without the container being killed. Local defaults (25 MB, 100,000 rows) are unchanged. |
| FR-DP-21 | **Hosted privacy notice.** When the backend reports `hosted: true` (FR-DP-30), the upload screen adds a notice about server storage: with `storage_persistent: false`, "Uploads are kept only temporarily: they are deleted when the server restarts or sleeps after about 15 minutes without use, and after `RETENTION_DAYS` days at most"; with `true`, "Uploads are kept on the server for `RETENTION_DAYS` days, then deleted". The existing notice of what is sent to the LLM (Spec 10 NFR-03) stays. There are no backups. |
| FR-DP-22 | **Runbook.** `docs/deployment.md` covers: prerequisites, the first deploy (creating the Render Blueprint from the repo, entering the secrets, setting `BACKEND_URL`), every environment variable (from `deploy/.env.example`), redeploying, rollback, reading logs, changing the password and the Gemini key, the free-tier limits (sleep and wake-up, temporary sessions, upload caps, monthly free hours), and the path to a paid plan with a disk. |
| FR-DP-30 | **Public config endpoint.** `GET /api/v1/config` returns `{max_file_size_mb, max_rows, retention_days, storage_persistent, hosted}` (`hosted` = `APP_ENV=production`) and nothing else. The upload screen shows the limits from it ("Up to N MB and M rows") instead of the hard-coded "25 MB and 100,000 rows", falling back to the local defaults if the call fails. |

### Render (production host, free tier)

| ID | Requirement |
|---|---|
| FR-DP-24 | **Render Blueprint.** `render.yaml` at the repo root defines two Docker **web services** on the **free** plan in region **singapore**: `ai-ds-agent-frontend` (built from `frontend/Dockerfile`, repo-root context so it can copy `samples/`) and `ai-ds-agent-backend` (built from `backend/Dockerfile`). The backend has one instance. The frontend's `BACKEND_URL` is the backend's public HTTPS URL, entered once after the first deploy (free instances cannot receive private-network traffic), and the backend is closed by FR-DP-14. |
| FR-DP-25 | **Listen on `$PORT`.** Both servers bind to `0.0.0.0:$PORT` when Render sets `PORT`, and to 8000 (backend) / 3000 (frontend) otherwise, so the same images run on Render, in compose and locally. |
| FR-DP-26 | **Secrets on Render.** `render.yaml` holds no secret values. `INTERNAL_API_TOKEN` lives in one environment group shared by both services and is generated by Render (`generateValue: true`). `ACCESS_PASSWORD`, `GEMINI_API_KEY` and `BACKEND_URL` are declared `sync: false` and entered once in the dashboard. `ACCESS_USER` has a non-secret default. |
| FR-DP-27 | **Deploys and rollback.** Both services deploy automatically from `main` only after the GitHub checks pass. Rollback is Render's "roll back to a previous deploy". Every deploy restarts the services and, on the free tier, clears all sessions; the runbook says to deploy when nobody is mid-run. |
| FR-DP-28 | **Free-tier settings.** Both services use the free instance type. The backend runs with `APP_ENV=production`, `LLM_PROVIDER=gemini`, `GEMINI_BACKEND=aistudio`, `STORAGE_PERSISTENT=false`, `LOG_TO_FILE=false`, `CORS_ORIGINS` empty, `DB_PATH=/data/app.db`, `STORAGE_ROOT=/data` and the limits of FR-DP-20. The runbook records the free tier's monthly instance-hour allowance and that two services share it. |
| FR-DP-29 | **Domain.** The app is used through the frontend's `onrender.com` hostname. A custom domain can be added in Render later with its managed certificate; the access gate covers every hostname because it runs in the frontend. |

### Verification

| ID | Requirement |
|---|---|
| FR-DP-23 | **Deployment smoke in CI.** A CI job builds both images, starts the compose stack with `APP_ENV=production`, `LLM_PROVIDER=offline`, the hosted limits of FR-DP-20, a 512 MB memory limit on the backend, test access credentials and a test internal token, waits for both healthchecks, then drives the frontend's port only: no credentials → `401`; with credentials, `/api/v1/config` reports the hosted limits; a sample and a file at the row cap each go through upload → profile → plan → approve → execute → charts → model → report → bundle. A direct backend request without the token is `401`. Finally it restarts the backend container and checks that a session is still there (compose storage persists, FR-DP-07). |

## Acceptance Criteria

- **AC-1** *(FR-DP-01, 02)* Given the repo, when both images are built, then they run as non-root users, the
  backend image contains no `.env`, `storage/`, `tests/` or dev dependencies, and the frontend serves `/healthz` with `200`.
- **AC-2** *(FR-DP-03)* Given `SAMPLES_DIR` pointing to a folder with `titanic.csv`, when `/samples/titanic.csv` is
  requested, then the file is served; without `SAMPLES_DIR` the route still reads `<cwd>/../samples`; a name outside
  the whitelist is `404` either way.
- **AC-3** *(FR-DP-04, FR-DP-17)* Given `APP_VERSION=abc123`, then `GET /health` returns `{"status":"ok","version":"abc123"}`;
  `GET /ready` is `200` with a working DB and writable storage, and `503` naming the failed check when the database
  cannot be queried or `STORAGE_ROOT` is not writable. `/ready` makes no LLM call.
- **AC-4** *(FR-DP-06)* Given `APP_ENV=production` and `WEB_CONCURRENCY=2`, when the backend's settings are checked,
  then startup fails with an error naming FR-DP-06; with `WEB_CONCURRENCY=1` or `APP_ENV` unset it passes.
- **AC-5** *(FR-DP-07, FR-DP-23)* Given the compose stack and a session that reached `reported`, when the backend
  container is restarted, then the session and its report are still served.
- **AC-6** *(FR-DP-08)* Given no `PROXY_TIMEOUT_MS`, the resolved proxy timeout is 300,000 ms; given
  `PROXY_TIMEOUT_MS=1000`, it is 1,000 ms.
- **AC-7** *(FR-DP-09, FR-DP-20)* Given `MAX_FILE_SIZE_MB=5`, when a 6 MB file is uploaded through the frontend's port,
  then the response is the app's `413` with the Spec 09 error envelope.
- **AC-8** *(FR-DP-11)* Given `APP_ENV=production`, when the backend's settings are checked with `INTERNAL_API_TOKEN`
  unset, or with `LLM_PROVIDER=gemini` and no key (or `vertex` and no project), then startup fails naming the missing
  variable; with `LLM_PROVIDER=offline` and the token set it passes. Given `APP_ENV=production` and a missing
  `ACCESS_PASSWORD`, `INTERNAL_API_TOKEN` or `BACKEND_URL`, the frontend answers `/` with `503` naming it and still
  answers `/healthz` with `200`.
- **AC-9** *(FR-DP-12)* Given `GEMINI_API_KEY_FILE`, then its contents are the key; given a key and an internal token,
  no log line emitted during a full mocked run, no `/health`, `/ready` or `/config` body and no error response
  contains either value.
- **AC-10** *(FR-DP-13)* Given `ACCESS_USER`/`ACCESS_PASSWORD`, then a request to `/`, to `/samples/titanic.csv` and to
  `/api/v1/health` through the frontend without credentials, or with a wrong password, is `401` with
  `WWW-Authenticate: Basic`, and with the right credentials it goes through; `/healthz` answers `200` without
  credentials and returns no data; without the variables (and without `APP_ENV=production`) nothing is gated.
- **AC-11** *(FR-DP-14)* Given `INTERNAL_API_TOKEN`, then a backend request without the header or with a wrong value
  is `401` with the error envelope, `/health` and `/ready` are open, and the right header passes; the frontend's
  `/api/v1` proxy adds the header, so a browser request succeeds without sending it.
- **AC-12** *(FR-DP-16)* Given `CORS_ORIGINS=https://example.org`, then a preflight from that origin is allowed and one
  from `http://localhost:3000` is not; with `CORS_ORIGINS` unset, today's localhost origins are allowed; with it set
  to an empty string, no origin is.
- **AC-13** *(FR-DP-18)* Given `LOG_TO_FILE=false`, then log lines go to stdout and no file is created under
  `STORAGE_ROOT/logs`; with `LOG_TO_FILE=true` the rotating file is written as today.
- **AC-14** *(FR-DP-21)* Given `/config` reports `hosted: true`, `storage_persistent: false` and `retention_days: 7`,
  the upload screen shows the temporary-storage notice mentioning 7 days; with `storage_persistent: true` it shows the
  7-day notice; with `hosted: false` it shows neither.
- **AC-15** *(FR-DP-23)* The CI deployment smoke job passes as FR-DP-23 describes, including AC-5 after a backend
  restart and the row-cap file under the 512 MB limit.
- **AC-16** *(FR-DP-24, FR-DP-26, FR-DP-28)* Given `render.yaml`, when it is parsed, then it defines two Docker web
  services on the free plan in `singapore`, with health check paths `/healthz` and `/api/v1/ready`; the backend has
  one instance and FR-DP-28's settings; both use one env group whose `INTERNAL_API_TOKEN` has `generateValue: true`;
  `ACCESS_PASSWORD`, `GEMINI_API_KEY` and `BACKEND_URL` have `sync: false` and no value; no other variable holds a
  secret.
- **AC-17** *(FR-DP-25)* Given `PORT=10000`, when each image starts, then it serves on port 10000; without `PORT`
  the backend serves on 8000 and the frontend on 3000.
- **AC-18** *(FR-DP-04)* Given `RENDER_GIT_COMMIT=def456` and no `APP_VERSION`, then `/health` reports `def456`; an
  explicit `APP_VERSION` wins; with neither it reports `dev`.
- **AC-19** *(FR-DP-30)* `GET /config` returns exactly the five fields from the settings; the upload screen shows
  "Up to 5 MB and 20,000 rows" when `/config` says so, and the local defaults when the call fails.

## Dependencies

- Spec 01 (upload limits, `413`), Spec 03 (FR-PL-17 offline planner, FR-PL-18 backoff, FR-PL-19 Gemini backends),
  Spec 04 (FR-RV-11 same-origin proxy, FR-RV-13 samples), Spec 09 (error envelope, endpoints),
  Spec 10 (NFR-03/06 privacy and logs, NFR-07 recovery, NFR-08 retention).
- `09-api-contracts.md` gains `GET /api/v1/ready`, `GET /api/v1/config`, the `version` field of `/health`, and the
  `401` of FR-DP-14 (FR-AP-23..25).

## Test Plan

- **Unit (backend):** production settings checks (AC-4, AC-8), `GEMINI_API_KEY_FILE` (AC-9), CORS origins (AC-12),
  log sink (AC-13), version resolution (AC-18), Blueprint shape (AC-16).
- **Integration (backend, TestClient):** `/health`, `/ready` good and broken (AC-3), internal-token middleware (AC-11),
  `/config` (AC-19), secrets never in logs or responses (AC-9).
- **Frontend (Vitest):** samples route with and without `SAMPLES_DIR` (AC-2), access gate and fail-closed middleware
  (AC-8 frontend half, AC-10), proxy header and timeout resolution (AC-6, AC-11 frontend half), limits and notice on
  the upload screen (AC-14, AC-19).
- **Deployment smoke (CI, Docker):** `scripts/smoke_deploy.py` against the compose stack (AC-1, AC-5, AC-7, AC-15,
  AC-17). Render itself cannot run in CI; after each real deploy the runbook's manual check repeats the flow on the
  Render URL.

## Out of Scope

- User accounts, sign-up, per-user data separation, audit logs (PRD §3 non-goal; the shared password is the v1 gate).
- Persistent hosted storage. It needs a paid Render instance with a disk (the earlier draft of FR-DP-24..28); the
  images and `STORAGE_PERSISTENT` already support it, so upgrading is a `render.yaml` change.
- Postgres, object storage, a job queue, more than one backend worker or host (design D5's upgrade path; FR-DP-06
  forbids multiple workers until that work exists).
- Hosts other than Render. The images and the compose file stay portable, but only Render is specified and verified.
- Kubernetes, autoscaling, serverless platforms (Cloud Run, Vercel functions).
- Backups and disaster recovery: hosted sessions are temporary by design.
- Rate limiting and LLM cost caps beyond the access gate and the existing bounded retries.

## Open Questions

- ~~Hosting target~~ **Resolved 2026-11-28: Render, free tier.** Two web services; temporary storage, 512 MB and a
  public backend URL closed by the internal token are accepted trade-offs. Vercel and Cloud Run were ruled out (no
  persistent process for background jobs). Render's free-tier limits (sleep timing, request timeout, upload size,
  monthly hours, private networking) are re-checked against FR-DP-08/09/20/24 on the first deploy.
- ~~Access gate~~ **Resolved 2026-11-28:** one shared Basic-auth password (FR-DP-13).
- ~~Gemini in production~~ **Resolved 2026-11-28:** AI Studio key (`GEMINI_API_KEY`).
- ~~Data location~~ **Resolved 2026-11-28:** Render region Singapore.
- **Long synchronous calls.** FR-DP-08 raises proxy timeouts to fit `POST /plan`. Making planning a background job
  with polling (like execute and model) would remove the long request entirely; it changes Spec 03/09 and is not
  part of this spec.

## Tasks

- [x] Approve this spec, resolve its open questions
- [x] Update `09-api-contracts.md` (FR-AP-23..25) and add the `dp` rows to `traceability.md`
- [x] Backend: version, `/ready`, `/config`, internal token, CORS, log sink, production checks, key file (AC-3, 4, 8,
      9, 11, 12, 13, 18, 19)
- [x] Frontend: access gate, fail-closed, `/healthz`, proxy header and timeout, samples dir, limits and notice from
      `/config`, standalone output (AC-2, 6, 8, 10, 11, 14, 19)
- [x] Dockerfiles, `.dockerignore`, `deploy/compose.yaml`, `deploy/.env.example` (AC-1, 17)
- [x] `render.yaml` (AC-16)
- [~] CI deployment smoke (AC-5, 7, 15): job written; the same flow passed locally without Docker; first
      Docker run is on the PR
- [x] Runbook `docs/deployment.md`
- [ ] First Render deploy: create the Blueprint, enter the secrets and `BACKEND_URL`, run the manual check

## Changelog

- 2026-11-28 — Draft: first deployment spec (single-tenant hosted demo on one container host). Records that the
  Next.js proxy's 30 s default timeout cuts off slow `POST /plan` calls today (FR-DP-08).
- 2026-11-28 — Hosting resolved: Render. Added FR-DP-24..29 (paid: web service + private service with a disk).
- 2026-11-28 — **Approved** for Render's free tier in Singapore, a shared password and an AI Studio key. FR-DP-24..29
  rewritten for two free web services (no disk, no private network); storage persistence becomes a setting
  (FR-DP-07); hosted limits fit 512 MB (FR-DP-20); the frontend fails closed when misconfigured (FR-DP-11); new
  `GET /config` so the UI shows the real limits and the storage notice (FR-DP-30, AC-19). Caddy dropped (TLS by
  Render, compose is local/CI only).
- 2026-11-28 — Implemented (tests first): backend settings and checks, internal token, `/ready`, `/config`;
  frontend Node.js middleware (gate, fail-closed, token proxy), standalone build, limits and notice; Dockerfiles,
  compose, `render.yaml`, CI `deploy-smoke`, runbook. Found while building: next.config rewrites are fixed at build
  time in a standalone build (proxy moved to middleware) and middleware truncates bodies over 10 MB by default (cap
  raised, FR-DP-09). Status stays In progress until CI's Docker smoke and the first Render deploy pass.
