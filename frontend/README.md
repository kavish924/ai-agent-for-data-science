# Frontend — AI Data Science Agent

Next.js 15 (App Router) + TypeScript + Tailwind CSS 4 + Framer Motion. Implements the
guided flow in `docs/specs/04-plan-review-ui.md`: Upload → Profile & target → Review plan
→ Run → Download.

## Run locally

Start the backend first (from the repo root; `LLM_PROVIDER=offline` plans without a key):

```bash
cd backend && LLM_PROVIDER=offline .venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Then the frontend:

```bash
npm install
npm run dev        # http://localhost:3000
```

The browser only calls `/api/v1/*`; `next.config.ts` proxies it to `BACKEND_URL`
(default `http://127.0.0.1:8000`).

## Scripts

| Script | What it does |
|---|---|
| `npm run gen:api` | Re-export the backend OpenAPI and regenerate `src/lib/api/schema.d.ts` — run after any API change |
| `npm test` | Vitest + Testing Library component tests (`test_rv_ac*` = Spec 04 ACs) |
| `npm run lint` · `npm run typecheck` · `npm run build` | CI gates |

## Layout

- `src/components/AgentFlow.tsx` — picks the screen from the session `state`, polls, syncs `?session=`
- `src/components/PlanReview.tsx` + `ParamEditor.tsx` — the review screen
- `src/lib/plan.ts` — review logic (statuses, client hints, destructive warnings), no React
- `src/lib/api/` — typed client and generated OpenAPI types

Visual design: the Claude Design canvas "Data Science Agent UI".
