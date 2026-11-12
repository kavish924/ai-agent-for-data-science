"""Write the backend's OpenAPI document for the frontend's generated types (Spec 04 FR-RV-11).

Usage (from backend/):  python scripts/export_openapi.py [output-path]
Default output: ../frontend/src/lib/api/openapi.json
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    default = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "api" / "openapi.json"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default

    # Build the app against a throwaway storage root: exporting must not touch real data.
    from app.config import settings

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings.storage_root = Path(tmp) / "storage"
        settings.db_path = settings.storage_root / "app.db"
        from app.main import create_app

        spec = create_app().openapi()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
