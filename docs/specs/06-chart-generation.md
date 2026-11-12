# Spec 06 — Chart Generation

> **Status:** Done · **Source:** PRD §6.6 · **Milestone:** M4 · **Agent:** Visualizer (deterministic)

## Purpose

Automatically produce the standard exploratory charts for the cleaned dataset and embed
them in the report — capped so the report stays readable.

## User Story

> As a user, I want the obvious charts generated for me, so I can see distributions,
> correlations, and missingness without writing plotting code.

## Requirements

| ID | Requirement |
|---|---|
| FR-CH-01 | Generate charts per the selection rules below, using matplotlib, saved as PNG artifacts under `storage/sessions/{id}/charts/`. |
| FR-CH-02 | *(rev. M4)* Numeric column → one **distribution** chart: a histogram with a box-plot strip above it (one PNG, two panels), so the cap covers twice as many columns. |
| FR-CH-03 | Categorical or boolean column → top-category bar chart (top 10 values). |
| FR-CH-04 | Dataset with ≥ 2 numeric columns → correlation heatmap. |
| FR-CH-05 | Dataset with any null values → missing-value map. |
| FR-CH-06 | Enforce the chart cap (`MAX_CHARTS`, default 12) using the documented priority: missing-value map → correlation heatmap → columns with nulls → columns with outliers → remaining by column order. *(M4)* "With nulls/outliers" refers to the **original** upload's profile (the issues the user saw), since cleaning usually removes them. Skipped chart types/columns are recorded in a chart manifest with a reason. |
| FR-CH-07 | Rendering is deterministic: fixed style/theme, fixed figure sizes, no timestamps or session IDs drawn into images. |
| FR-CH-08 | Ineligible chart types are skipped without failure (e.g., no numeric columns → no heatmap); the manifest explains why. |
| FR-CH-09 | Charts are generated from the **cleaned** dataset (the deliverable CSV as written). *(M4)* For a numeric column that an executed step changed, the distribution chart also draws the original upload's histogram as a grey "before" outline; the manifest marks it `before_overlay: true`. |
| FR-CH-10 | *(M4)* After a successful run, the cleaned CSV is re-profiled into `profile.after.json` (same profiler, Spec 02), the input to before/after comparison (Spec 08). |
| FR-CH-11 | *(M4)* Re-profiling and charts run automatically inside the execution job, after the cleaned CSV is written and **before** the session becomes `executed`, so a finished run always has its charts. Their failure never fails the run: the session still becomes `executed`, and `charts_manifest.json` records `status: failed` with the reason. |
| FR-CH-12 | *(M4)* Text, `id_like` and datetime columns get no per-column chart in v1; the manifest says so. Charts never draw raw text or ID values; category bars show the categorical column's own top values only. |
| FR-CH-13 | *(M4, UI)* The Download screen shows a chart gallery from the manifest (title per chart; click to enlarge; skipped charts listed with reasons). |

### Selection summary

| Input condition | Chart |
|---|---|
| Numeric column | Histogram + box plot |
| Categorical column | Top-category bar |
| ≥ 2 numeric columns | Correlation heatmap |
| Any nulls | Missing-value map |

## Interfaces

- **Input:** `cleaned_<name>.csv` (Spec 05), `profile.json` (for column types),
  `execution_log.json` (for changed columns)
- **Output:** `charts/*.png` + `charts_manifest.json` (which charts, why others skipped);
  consumed by Spec 08 (report embedding) and the UI gallery
- **Manifest shape:** `{"status": "completed"|"failed", "max_charts", "duration_ms",
  "charts": [{"file", "kind", "column", "title", "before_overlay"}], "skipped":
  [{"kind", "column", "reason"}], "error"?}`; files are named `NN_<kind>[_<column>].png`
- **Code:** `services/charts.py` (pure: data in, PNGs + manifest out),
  `services/orchestrator.py` (post-execution steps), endpoints in `routers/execution.py`

## Acceptance Criteria

- **AC-1** Given Titanic-like cleaned data, when generated, then distribution charts
  exist for `Age`/`Fare`, a bar chart exists for `Sex`, and a heatmap exists.
- **AC-2** Given `MAX_CHARTS=12` and 30 eligible numeric columns, then exactly 12 PNGs
  are produced and the manifest lists the skipped ones with reasons.
- **AC-3** Given a dataset with zero nulls, then no missing-value map is produced and
  the manifest records `missing_map: skipped (no nulls)`.
- **AC-4** Given the same inputs rendered twice, then PNG bytes are identical (AC-7
  determinism).
- **AC-5** Given a dataset with only text columns, then generation completes
  successfully with the eligible charts only (no crash — PRD §7 Reliability).
- **AC-6** *(M4)* Given chart rendering raises, the run still ends `executed`, the cleaned
  CSV exists, and the manifest has `status: failed` with the reason.
- **AC-7** *(M4)* Given a completed run, `profile.after.json` exists and reports the
  cleaned data (e.g. 0 nulls in a column the plan imputed).
- **AC-8** *(M4)* Given an imputed numeric column, its distribution chart is marked
  `before_overlay: true`; unchanged columns are not.
- **AC-9** *(M4)* The chart file endpoint serves only files listed in the manifest
  (unknown or path-like names → `404`).
- **AC-10** *(M4, UI)* Given a manifest, the gallery shows one image per chart with its
  title and lists skipped charts with their reasons.

## Dependencies

- Requires Specs 02 + 05. Feeds Spec 08. No LLM.

## Test Plan

- **Unit:** eligibility logic per rule; cap/priority ordering; manifest contents.
- **Integration:** golden PNG byte-comparison on a fixed sample dataset (determinism);
  skip-path assertions; report embedding smoke test.

## Out of Scope

- Interactive charts (HTML/JS), user-chosen custom charts, 3-D or pair plots,
  before/after overlay charts beyond the FR-CH-09 feasible set.

## Open Questions

- PNG vs SVG for the report (PNG chosen: deterministic bytes, universal embedding).

## Tasks

- [x] FR-CH-01..09 chart selection, cap, determinism, before overlay
- [x] FR-CH-10 after-cleaning profile
- [x] FR-CH-11 automatic post-execution step with failure isolation
- [x] FR-CH-12 no text/ID values drawn
- [x] FR-CH-13 UI gallery

## Changelog

- 2026-11-12 — M4: FR-CH-02 combines histogram + box plot into one distribution chart;
  FR-CH-06 priority uses the original profile; added FR-CH-10..13 and AC-6..10.
- 2026-11-12 — M4 complete: AC-1..10 pass; verified in the browser on titanic.csv (9 charts, before overlay on Age).
