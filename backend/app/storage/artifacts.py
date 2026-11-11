"""Filesystem artifact store (architecture.md §5 layout, design D5)."""

from __future__ import annotations

import re
from pathlib import Path

PlanKind = str  # "generated" | "approved"
_PLAN_FILE = re.compile(r"^v(\d+)\.(generated|approved)\.json$")
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]")


def session_dir(storage_root: Path, session_id: str) -> Path:
    directory = storage_root / "sessions" / session_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def session_dir_path(storage_root: Path, session_id: str) -> Path:
    """The session directory without creating it (for deletion/inspection)."""
    return storage_root / "sessions" / session_id


def safe_filename(original_filename: str) -> str:
    """Strip any path and unsafe characters from a user-supplied filename.

    The upload's name ends up in an artifact path (`cleaned_<name>.csv`); without this a
    name such as `../../x.csv` would write outside the session directory.
    """
    name = Path(original_filename.replace("\\", "/")).name.strip()
    name = _UNSAFE_CHARS.sub("_", name).lstrip(".")
    if not name:
        name = "upload.csv"
    if not name.lower().endswith(".csv"):
        name += ".csv"
    return name[:120]


def upload_path(storage_root: Path, session_id: str) -> Path:
    return session_dir(storage_root, session_id) / "upload.csv"


def profile_path(storage_root: Path, session_id: str) -> Path:
    return session_dir(storage_root, session_id) / "profile.json"


def plan_path(storage_root: Path, session_id: str) -> Path:
    """Current review copy of the plan (what the review UI shows and edits)."""
    return session_dir(storage_root, session_id) / "plan.json"


def plans_dir(storage_root: Path, session_id: str) -> Path:
    directory = session_dir(storage_root, session_id) / "plans"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def plan_version_path(storage_root: Path, session_id: str, version: int, kind: PlanKind) -> Path:
    """Immutable plan versions: v{n}.generated.json / v{n}.approved.json (FR-AP-03/12)."""
    return plans_dir(storage_root, session_id) / f"v{version}.{kind}.json"


def list_plan_versions(storage_root: Path, session_id: str) -> list[tuple[int, str, Path]]:
    """All stored plan versions, ordered by version then kind (generated before approved)."""
    found = []
    for path in plans_dir(storage_root, session_id).iterdir():
        match = _PLAN_FILE.match(path.name)
        if match:
            found.append((int(match.group(1)), match.group(2), path))
    order = {"generated": 0, "approved": 1}
    return sorted(found, key=lambda item: (item[0], order[item[1]]))


def execution_log_path(storage_root: Path, session_id: str) -> Path:
    return session_dir(storage_root, session_id) / "execution_log.json"


def cleaned_filename(original_filename: str) -> str:
    return f"cleaned_{safe_filename(original_filename)}"


def cleaned_csv_path(storage_root: Path, session_id: str, original_filename: str) -> Path:
    return session_dir(storage_root, session_id) / cleaned_filename(original_filename)


def charts_dir(storage_root: Path, session_id: str) -> Path:  # used from M4
    return session_dir(storage_root, session_id) / "charts"


def save_upload(storage_root: Path, session_id: str, data: bytes) -> Path:
    """Persist the original upload bytes, immutable for the session lifetime (FR-UP-07)."""
    path = upload_path(storage_root, session_id)
    path.write_bytes(data)
    return path
