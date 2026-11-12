"""Spec-driven development gate (CLAUDE.md rule 3).

For every spec whose status is `In progress` or `Done`:
  * every AC must have a row in docs/specs/traceability.md;
  * every test named in a row must exist (backend/tests or frontend/src/**/*.test.ts[x]);
  * `pending` rows are allowed only while the spec is not `Done`.
Exits non-zero with a list of problems.

Usage (from backend/):  python scripts/check_traceability.py
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SPECS = BACKEND.parent / "docs" / "specs"
MATRIX = SPECS / "traceability.md"
ENFORCED = ("In progress", "Done")

_STATUS = re.compile(r"\*\*Status:\*\*\s*([A-Za-z ]+?)(?:\s*\(|\s*·)")
_AC = re.compile(r"^- \*\*(AC-\d+)\*\*", re.MULTILINE)
_ROW = re.compile(r"^\|\s*(\d{2})\s*\|\s*(AC-\d+)\s*\|\s*([^|]+)\|", re.MULTILINE)
_TEST_DEF = re.compile(r"^def (test_\w+)", re.MULTILINE)
# Frontend (Vitest) tests are named by their title string: test("test_rv_ac1_...", ...)
_TEST_TITLE = re.compile(r"""\b(?:test|it)\(\s*["'`](test_\w+)["'`]""")
FRONTEND = BACKEND.parent / "frontend" / "src"


def main() -> int:
    tests = {
        name
        for path in (BACKEND / "tests").rglob("test_*.py")
        for name in _TEST_DEF.findall(path.read_text(encoding="utf-8"))
    }
    if FRONTEND.exists():
        tests |= {
            name
            for path in FRONTEND.rglob("*.test.ts*")
            for name in _TEST_TITLE.findall(path.read_text(encoding="utf-8"))
        }
    rows: dict[tuple[str, str], str] = {
        (spec, ac): cell.strip() for spec, ac, cell in _ROW.findall(MATRIX.read_text(encoding="utf-8"))
    }

    problems: list[str] = []
    checked = 0
    for spec_file in sorted(SPECS.glob("[0-9][0-9]-*.md")):
        text = spec_file.read_text(encoding="utf-8")
        match = _STATUS.search(text)
        status = match.group(1).strip() if match else "Draft"
        if status not in ENFORCED:
            continue
        number = spec_file.name[:2]
        for ac in _AC.findall(text):
            checked += 1
            cell = rows.get((number, ac))
            if cell is None:
                problems.append(f"Spec {number} {ac}: no row in traceability.md")
                continue
            if cell.startswith("pending"):
                if status == "Done":
                    problems.append(f"Spec {number} {ac}: still pending but the spec is Done")
                continue
            for name in re.findall(r"`(test_\w+)`", cell):
                if name not in tests:
                    problems.append(f"Spec {number} {ac}: test '{name}' does not exist")

    for problem in problems:
        print(f"[traceability] {problem}")
    print(f"[traceability] checked {checked} ACs, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
