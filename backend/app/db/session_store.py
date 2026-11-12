"""SQLite session store (design.md §3.1, D5: thin interface, swappable)."""

from __future__ import annotations

import contextlib
import sqlite3
import uuid
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    state TEXT NOT NULL,
    n_rows INTEGER,
    n_columns INTEGER,
    encoding TEXT,
    delimiter TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    retention_expires_at TEXT NOT NULL,
    error TEXT
);

-- Spec 03 FR-PL-07 / Spec 10 NFR-03: one row per LLM attempt, metadata only - never
-- prompt or response content. Feeds the PRD §9 "schema validity rate" metric.
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    valid INTEGER NOT NULL,
    error TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    output_tokens INTEGER,
    duration_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS llm_calls_session ON llm_calls (session_id);
"""

# Columns added after M2; applied to existing databases by init_db (M0)
_ADDED_COLUMNS = {
    "failed_stage": "TEXT",  # profile | plan | execute | ... (Spec 09 state table)
    "target": "TEXT",  # Spec 07 FR-ML-10
    "plan_version": "INTEGER",  # latest plan version (FR-AP-03)
}

_UPDATABLE = {
    "original_filename", "state", "n_rows", "n_columns", "encoding", "delimiter",
    "retention_expires_at", "error", *_ADDED_COLUMNS,
}


@contextlib.contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open, commit (or roll back) and always close a connection.

    `with sqlite3.connect(...)` alone only manages the transaction - it never closes the
    connection, which leaks handles and keeps the DB file locked on Windows.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
        for name, sql_type in _ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {sql_type}")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def create_session(
    db_path: Path,
    *,
    session_id: str,
    original_filename: str,
    state: str,
    n_rows: int | None = None,
    n_columns: int | None = None,
    encoding: str | None = None,
    delimiter: str | None = None,
    retention_days: int = 7,
) -> None:
    now = _now()
    expires = (datetime.now(UTC) + timedelta(days=retention_days)).isoformat(
        timespec="seconds"
    )
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (id, original_filename, state, n_rows, n_columns,"
            " encoding, delimiter, created_at, updated_at, retention_expires_at, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (session_id, original_filename, state, n_rows, n_columns, encoding, delimiter,
             now, now, expires),
        )


def get_session(db_path: Path, session_id: str) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def _assignments(fields: dict[str, Any]) -> tuple[str, tuple]:
    unknown = set(fields) - _UPDATABLE - {"updated_at"}
    if unknown:  # column names are interpolated into SQL: whitelist them
        raise ValueError(f"unknown session fields: {sorted(unknown)}")
    fields = {**fields, "updated_at": _now()}
    return ", ".join(f"{key} = ?" for key in fields), tuple(fields.values())


def update_session(db_path: Path, session_id: str, **fields: Any) -> None:
    if not fields:
        return
    assignments, values = _assignments(fields)
    with _connect(db_path) as conn:
        conn.execute(f"UPDATE sessions SET {assignments} WHERE id = ?", (*values, session_id))


def transition(db_path: Path, session_id: str, from_states: Iterable[str], **fields: Any) -> bool:
    """Atomically update a session only if its state is one of `from_states`.

    Returns True when this caller won the transition (Spec 09 AC-7): two concurrent
    requests can both pass a read-then-check, but only one conditional UPDATE matches.
    """
    states = list(from_states)
    assignments, values = _assignments(fields)
    placeholders = ", ".join("?" for _ in states)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE sessions SET {assignments} WHERE id = ? AND state IN ({placeholders})",
            (*values, session_id, *states),
        )
        return cursor.rowcount == 1


def recover_inflight(db_path: Path, has_profile: Any) -> list[str]:
    """Startup recovery (Spec 10 NFR-07); `has_profile(session_id) -> bool`."""
    recovered: list[str] = []
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, state, error FROM sessions WHERE state IN ('executing', 'uploaded', 'modeling')"
        ).fetchall()
    for row in rows:
        if row["state"] == "executing":
            update_session(
                db_path, row["id"], state="awaiting_approval", failed_stage="execute",
                error="execution was interrupted by a server restart; approve and run it again",
            )
            recovered.append(row["id"])
        elif row["state"] == "modeling":
            update_session(
                db_path, row["id"], state="executed", failed_stage="model",
                error="training was interrupted by a server restart; train again",
            )
            recovered.append(row["id"])
        elif row["error"] is None and not has_profile(row["id"]):
            update_session(
                db_path, row["id"], failed_stage="profile",
                error="profiling was interrupted by a server restart; retry profiling",
            )
            recovered.append(row["id"])
    return recovered


def list_expired(db_path: Path, now: datetime | None = None) -> list[str]:
    cutoff = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM sessions WHERE retention_expires_at <= ?", (cutoff,)
        ).fetchall()
    return [row["id"] for row in rows]


def delete_session(db_path: Path, session_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM llm_calls WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def record_llm_call(
    db_path: Path,
    *,
    session_id: str,
    stage: str,
    attempt: int,
    valid: bool,
    error: str | None,
    model: str | None,
    prompt_tokens: int | None,
    output_tokens: int | None,
    duration_ms: int,
) -> None:
    """Persist one LLM attempt. `error` is a short error class, never content."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO llm_calls (session_id, stage, attempt, valid, error, model,"
            " prompt_tokens, output_tokens, duration_ms, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, stage, attempt, int(valid), error, model, prompt_tokens,
             output_tokens, duration_ms, _now()),
        )


def list_llm_calls(db_path: Path, session_id: str) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM llm_calls WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
    return [dict(row) for row in rows]
