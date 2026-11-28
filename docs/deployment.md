# Deployment runbook

How the AI Data Science Agent runs as a hosted demo. Requirements: [Spec 11](specs/11-deployment.md).

**Where it runs:** Render, free tier, region Singapore, as two web services built from this
repo's Dockerfiles ([`render.yaml`](../render.yaml)):

| Service | What it is | Health check |
|---|---|---|
| `ai-ds-agent-frontend` | Next.js server: the UI, the shared-password gate, and the `/api/v1` proxy | `/healthz` |
| `ai-ds-agent-backend` | FastAPI: the pipeline. Public URL, but it only answers requests carrying the internal token | `/api/v1/ready` |

People use the **frontend URL** with the shared password. Nobody needs the backend URL.

## What the free tier means

- **Sessions are temporary.** There is no disk: everything (uploads, plans, reports) is lost
  when a service restarts, redeploys or goes to sleep. The upload screen tells users this.
- **Sleep and wake-up.** A free service sleeps after about 15 minutes without traffic. The
  next visit waits about a minute while it wakes, and the frontend then wakes the backend,
  which can take another minute. The `/api/v1` proxy waits up to 5 minutes, so this works.
- **Smaller uploads.** 512 MB of memory: hosted uploads are capped at 5 MB and 20,000 rows,
  and models train on at most 10,000 rows (`MAX_FILE_SIZE_MB`, `MAX_ROWS`, `MODEL_MAX_ROWS`).
- **Monthly hours.** The free instance hours are shared by both services in the workspace.
  Sleeping services don't use them. Check the current allowance on Render's pricing page.
- Re-check Render's current free-tier limits (sleep time, hours, request timeout) when
  something behaves unexpectedly; they are set by Render and can change.

## First deploy

1. **Merge to `main`** with CI green. Render builds from `main`.
2. In the Render dashboard: **New → Blueprint**, connect the GitHub repository, pick
   `render.yaml`. Render shows the two services and the env group `ai-ds-agent-shared`
   (it generates `INTERNAL_API_TOKEN` itself).
3. Render asks for the values marked `sync: false`:
   - `ai-ds-agent-backend` → **`GEMINI_API_KEY`**: the AI Studio key.
   - `ai-ds-agent-frontend` → **`ACCESS_PASSWORD`**: the shared password (the user is `demo`).
   - `ai-ds-agent-frontend` → **`BACKEND_URL`**: leave a placeholder (e.g. `https://example.invalid`)
     for now; the frontend answers `503` until it is set.
4. Apply. Wait for both services to be **Live**.
5. Copy the backend's URL (e.g. `https://ai-ds-agent-backend.onrender.com`; Render may add a
   suffix if the name is taken) and set it as the frontend's **`BACKEND_URL`**. The frontend
   redeploys.
6. **Check it** (below).

## Check a deploy

From `backend/`, against the frontend URL (the row-cap file is slow on 0.1 CPU, so skip it):

```bash
.venv/Scripts/python scripts/smoke_deploy.py --base https://ai-ds-agent-frontend.onrender.com --user demo --password "<password>" --skip-row-cap
```

It checks `/healthz`, the password gate, `/api/v1/config`, an oversize upload (`413`), and
the full flow on `titanic.csv` through to the report and bundle. It uses the real Gemini key,
so it costs one plan and one narration call.

Also: `https://<backend>/api/v1/health` shows the deployed commit (`version`), and
`https://<backend>/api/v1/config` without the token must answer `401`.

## Everyday operations

| Task | How |
|---|---|
| **Deploy** | Merge to `main`. Each service deploys after the GitHub checks pass (`autoDeployTrigger: checksPass`). Deploying restarts the services and clears all sessions, so deploy when nobody is mid-run. |
| **Roll back** | Service → **Events** → pick an earlier deploy → **Rollback**. Same effect on sessions. |
| **Logs** | Service → **Logs**. Lines are JSON (Spec 10 catalog); they never contain row values, prompts or secrets. |
| **Change the password** | Frontend → **Environment** → `ACCESS_PASSWORD` → save (redeploys). |
| **Change the Gemini key** | Backend → **Environment** → `GEMINI_API_KEY` → save (redeploys). |
| **Rotate the internal token** | Env group `ai-ds-agent-shared` → generate a new `INTERNAL_API_TOKEN` → redeploy **both** services. |
| **Run without Gemini** | Backend → `LLM_PROVIDER=offline`: rule-based plans and template summaries, no key used. |
| **Custom domain** | Frontend → **Settings → Custom Domains**. Render issues the certificate; the password gate covers every hostname. |

If the frontend shows **"Not configured: … must be set"**, a production setting is missing
(Spec 11 FR-DP-11): set the named variable on the frontend. If the backend fails to start,
its log names the missing variable (`INTERNAL_API_TOKEN`, `GEMINI_API_KEY`) or the
`WEB_CONCURRENCY` problem.

## Environment variables

Every variable, with its default and whether it is a secret, is in
[`deploy/.env.example`](../deploy/.env.example). On Render they are set by `render.yaml` and
the dashboard; never put a secret value in `render.yaml`.

## Run the same stack locally

Needs Docker. From the repo root:

```bash
cp deploy/.env.example deploy/.env   # fill in INTERNAL_API_TOKEN, ACCESS_PASSWORD, GEMINI_API_KEY
docker compose -f deploy/compose.yaml --env-file deploy/.env up -d --build --wait
```

Open http://localhost:3000 (user `demo`). Here `/data` is a Docker volume, so sessions survive
restarts. CI runs this stack with [`deploy/ci.env`](../deploy/ci.env) and the offline planner
(the `deploy-smoke` job).

## Moving to persistent storage

A paid Render instance can have a disk. Then: give the backend a disk mounted at `/data`, set
`STORAGE_PERSISTENT=true`, and raise the limits if the instance has more memory. The upload
screen switches to the "kept for N days" notice by itself. Nothing else in the app changes.
