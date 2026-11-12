# AI Data Science Agent — working rules

Core principle (PRD §1): **the LLM plans and narrates; all data work is deterministic.**
LLM output never executes and never sees raw rows.

## Spec-driven development (mandatory)

Source of truth: `docs/specs/NN-*.md`. Workflow for every behavior change:

1. **Spec first.** Edit the FR/AC rows of the relevant spec and set its header
   `Status:` to `Approved` before writing code. Contract changes also update
   `09-api-contracts.md`.
2. **Tests from ACs.** Each AC gets at least one test named `test_<prefix>_ac<N>_<what>`
   (prefixes: `up` 01, `pr` 02, `pl` 03, `rv` 04, `ex` 05, `ch` 06, `ml` 07, `rp` 08,
   `ap` 09, `nfr` 10). Write it first and watch it fail.
3. **Implement** until green. No code without an FR; no FR without an AC.
4. **Trace.** Add the FR → AC → test → module row to `docs/specs/traceability.md`.
5. **Close.** Tick the spec's `## Tasks`, add a `## Changelog` line, set `Status: Done`
   only when every AC passes.

Spec status values: `Draft | Approved | In progress | Done`.

## Definition of done (per milestone)

All from `backend/` with the venv's tools; CI (`.github/workflows/ci.yml`) runs the same:

- `pytest -m "not live"` green (LLM always mocked; live tests are `@pytest.mark.live`)
- `ruff check .` and `mypy` green
- `python scripts/check_traceability.py` green
- `python scripts/smoke_mN.py` passes on all `samples/*.csv` (latest: `smoke_m3.py`; `--live` uses real Gemini)
- Frontend (from `frontend/`): `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
  green; after any backend API change run `npm run gen:api` and commit the regenerated types
- UI changes are checked in the browser pane: `.claude/launch.json` starts `backend`
  (planner per `.env`, Gemini by default), `backend-offline` (no key needed) and `frontend`
- The Gemini key goes in the repo-root `.env` (gitignored), never in `.env.example` (tracked)

## Branching & progress tracking

- **Never commit or push to `main`.** All work happens on a branch; `main` changes only
  by a reviewed PR merge.
- One branch per milestone, named as in `docs/CHECKLIST.md` (`m3-llm-planner`, …).
  Cut it from the latest `main` after the previous milestone's PR is merged. If the
  previous PR is still open, branch from that branch and rebase onto `main` after it merges.
- Unrelated fixes found mid-milestone go on their own short branch (`fix/<topic>`).
- Update `docs/CHECKLIST.md` in the same branch as the work: tick a task only when it is
  done and verified, and refresh "Last updated" / "Current branch".

## Guardrails

- Never modify `storage/sessions/*/upload.csv`; every stage writes new artifacts.
- Every LLM output passes a code-owned gate (Pydantic + `services/gate.py`).
- Only `llm_profile()` output may go into a prompt — no id_like/text values.
- Model preprocessing lives inside sklearn `Pipeline`s; no fit on full data.
- Runtime data lives in the root `/storage/` (gitignored); `backend/app/storage/` is code.

## Roadmap

See the milestone table (M0 hardening → M3 planner → M3.5 thin UI → M4 charts →
M5 ML → M6 report → M7 UI polish → M8 eval) in `docs/specs/00-project-overview.md`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
