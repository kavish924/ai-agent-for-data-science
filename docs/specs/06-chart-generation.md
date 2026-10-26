# Spec 06 — Chart Generation

> **Status:** Draft v0.1 · **Source:** PRD §6.6 · **Milestone:** M4 · **Agent:** Visualizer (deterministic)

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
| FR-CH-02 | Numeric column → histogram and box plot. |
| FR-CH-03 | Categorical column (low cardinality) → top-category bar chart. |
| FR-CH-04 | Dataset with ≥ 2 numeric columns → correlation heatmap. |
| FR-CH-05 | Dataset with any null values → missing-value map. |
| FR-CH-06 | Enforce the chart cap (`MAX_CHARTS`, default 12) using the documented priority: missing-value map → correlation heatmap → columns with nulls → columns with outliers → remaining by column order. Skipped chart types/columns are recorded in a chart manifest. |
| FR-CH-07 | Rendering is deterministic: fixed style/theme, fixed figure sizes, no timestamps or session IDs drawn into images. |
| FR-CH-08 | Ineligible chart types are skipped without failure (e.g., no numeric columns → no heatmap); the manifest explains why. |
| FR-CH-09 | Charts are generated from the **cleaned** dataset (post-execution), and a before-set is included for columns changed by execution where feasible. |

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
  consumed by Spec 08 (report embedding)

## Acceptance Criteria

- **AC-1** Given Titanic-like cleaned data, when generated, then histogram + box plot
  exist for `Age`/`Fare`, a bar chart exists for `Sex`, and a heatmap exists.
- **AC-2** Given `MAX_CHARTS=12` and 30 eligible numeric columns, then exactly 12 PNGs
  are produced and the manifest lists the skipped ones with reasons.
- **AC-3** Given a dataset with zero nulls, then no missing-value map is produced and
  the manifest records `missing_map: skipped (no nulls)`.
- **AC-4** Given the same inputs rendered twice, then PNG bytes are identical (AC-7
  determinism).
- **AC-5** Given a dataset with only text columns, then generation completes
  successfully with the eligible charts only (no crash — PRD §7 Reliability).

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
