# Spec 01 — Upload & Ingestion

> **Status:** Draft v0.1 · **Source:** PRD §6.1 · **Milestone:** M1 · **Agent:** Orchestrator/Profiler (ingestion duties)

## Purpose

Accept a CSV file, validate it against configured limits, detect its encoding and
delimiter, and create an immutable session for all downstream stages.

## User Story

> As a user, I want to upload a CSV and immediately know whether it was accepted, so I
> can start the analysis without guessing about file problems.

## Requirements

| ID | Requirement |
|---|---|
| FR-UP-01 | Accept exactly one CSV per session via `POST /sessions` (multipart). |
| FR-UP-02 | Detect file encoding (UTF-8 default; attempt detection for common alternatives such as latin-1/cp1252). Detected encoding is recorded in the session. |
| FR-UP-03 | Sniff the delimiter (comma, semicolon, tab, pipe). Detected delimiter is recorded in the session. |
| FR-UP-04 | Enforce a configurable max file size (`MAX_FILE_SIZE_MB`); on exceed, reject with a clear message stating the limit (HTTP 413). |
| FR-UP-05 | Enforce a configurable max row count (`MAX_ROWS`); on exceed, reject with a clear message (HTTP 413). |
| FR-UP-06 | Generate a UUID session ID per upload; initial state `uploaded`. |
| FR-UP-07 | Store the original file at `storage/sessions/{id}/upload.csv`, **immutable** for the session's lifetime. |
| FR-UP-08 | Reject non-CSV content (by content sniff, not extension alone) with a specific error message. |
| FR-UP-09 | Set `retention_expires_at = created_at + RETENTION_DAYS` on session creation. |
| FR-UP-10 | Return `201` with `{session_id, state, n_rows, n_columns}` after successful parse of a header row and at least one data row. |

## Interfaces

- `POST /sessions` — see `09-api-contracts.md` §2
- Session record fields: `id`, `original_filename`, `state`, `n_rows`, `n_columns`,
  `encoding`, `delimiter`, `created_at`, `retention_expires_at`
- Downstream consumers read `upload.csv` via the artifact store path convention

## Acceptance Criteria

- **AC-1** Given a valid UTF-8 comma CSV under limits, when uploaded, then response is
  `201` with a session ID, state `uploaded`, and correct row/column counts.
- **AC-2** Given a semicolon-delimited latin-1 CSV, when uploaded, then ingestion
  succeeds and the session records `encoding=latin-1`, `delimiter=";"`.
- **AC-3** Given a file over `MAX_FILE_SIZE_MB`, when uploaded, then response is `413`
  with a message naming the limit; **no** session is created.
- **AC-4** Given a CSV exceeding `MAX_ROWS`, when uploaded, then response is `413` with
  a message naming the row limit.
- **AC-5** Given a text file renamed to `.csv`, when uploaded, then response is `415`
  or `422` with a content-sniff explanation.
- **AC-6** Given any accepted upload, when any later stage runs, then the byte content
  and mtime of `upload.csv` are unchanged (immutability).

## Dependencies

- None upstream (first stage). Provides: session ID + `upload.csv` for Specs 02–08;
  artifact store and session store interfaces (`tech-stack.md` §3).

## Test Plan

- **Unit:** delimiter/encoding detection matrix; limit checks; content sniffing.
- **Integration (LLM mocked, not needed here):** upload → 201 → file exists at expected
  path; retry upload twice → two distinct sessions; immutability check after profiling.

## Out of Scope

- Chunked/streaming ingestion (stretch, PRD §10), Excel/Parquet (stretch, PRD §12),
  multiple files per session, resumable uploads.

## Open Questions

- ~~Default limits~~ **Resolved:** 25 MB / 100k rows accepted as v1 defaults.
