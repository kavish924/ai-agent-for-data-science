"""SQLite session store (design.md §3.1, D5: thin interface, swappable)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    expires = (
        datetime.now(timezone.utc) + timedelta(days=retention_days)
    ).isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (id, original_filename, state, n_rows, n_columns,"
            " encoding, delimiter, created_at, updated_at, retention_expires_at, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                session_id,
                original_filename,
                state,
                n_rows,
                n_columns,
                encoding,
                delimiter,
                now,
                now,
                expires,
            ),
        )


def get_session(db_path: Path, session_id: str) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def update_session(db_path: Path, session_id: str, **fields) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": _now()}
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE sessions SET {assignments} WHERE id = ?",
            (*fields.values(), session_id),
        )
