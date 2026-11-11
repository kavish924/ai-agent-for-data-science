"""Retention sweep (PRD §7 privacy, Spec 10 NFR-08): delete expired sessions entirely."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from ..db import session_store
from ..storage.artifacts import session_dir_path

logger = logging.getLogger("retention")


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def sweep(db_path: Path, storage_root: Path, now: datetime | None = None) -> tuple[int, int]:
    """Delete every expired session (artifacts first, then the DB row).

    Returns (deleted_sessions, freed_bytes).
    """
    deleted, freed = 0, 0
    for session_id in session_store.list_expired(db_path, now):
        directory = session_dir_path(storage_root, session_id)
        if directory.exists():
            freed += _dir_size(directory)
            shutil.rmtree(directory)
        session_store.delete_session(db_path, session_id)
        deleted += 1
    logger.info(
        "retention.sweep",
        extra={"stage": "retention", "deleted_sessions": deleted, "freed_bytes": freed},
    )
    return deleted, freed
