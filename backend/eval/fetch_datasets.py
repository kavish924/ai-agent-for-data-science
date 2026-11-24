"""Fetch the benchmark datasets listed in the manifest (Spec 10 NFR-15).

Usage (from backend/; needs network access to openml.org):
    python -m eval.fetch_datasets                   # download missing datasets, verify recorded hashes
    python -m eval.fetch_datasets --record-hashes   # also store new hashes + licences in the manifest
    python -m eval.fetch_datasets --only credit-g

CSVs go to eval/benchmark/data/ (gitignored); only the manifest is committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from . import harness

MANIFEST = harness.EVAL_DIR / "benchmark" / "manifest.json"
DATA_DIR = harness.EVAL_DIR / "benchmark" / "data"
REQUIRED = ("name", "openml_id", "openml_name", "target", "task", "license", "sha256")
TASKS = ("classification", "regression")

Fetcher = Callable[[int], tuple[str, pd.DataFrame, "str | None"]]


def load_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["datasets"]
    for i, e in enumerate(entries):
        missing = [k for k in REQUIRED if k not in e]
        if missing:
            raise ValueError(f"manifest entry {i} ({e.get('name')}): missing {', '.join(missing)}")
        if e["task"] not in TASKS:
            raise ValueError(f"manifest entry {e['name']}: task must be one of {TASKS}")
    return entries


def openml_fetcher(openml_id: int) -> tuple[str, pd.DataFrame, str | None]:
    from sklearn.datasets import fetch_openml  # network access, only when really fetching

    try:
        bunch = fetch_openml(data_id=openml_id, as_frame=True, parser="auto")
    except TypeError:
        # scikit-learn 1.9's pandas ARFF parser fails on numeric category labels under
        # pandas 3 ("expected string ... got 'int'"); the pure-Python parser works.
        bunch = fetch_openml(data_id=openml_id, as_frame=True, parser="liac-arff")
    return str(bunch.details["name"]), bunch.frame, bunch.details.get("licence")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_all(entries: list[dict[str, Any]], data_dir: Path, *, fetcher: Fetcher = openml_fetcher,
              record_hashes: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch each entry; return (per-dataset report, entries with recorded hashes/licences)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for e in entries:
        e = dict(e)
        updated.append(e)
        path = data_dir / f"{e['name']}.csv"
        if path.exists() and (e["sha256"] is None or _sha(path.read_bytes()) == e["sha256"]):
            if record_hashes and e["sha256"] is None:
                e["sha256"] = _sha(path.read_bytes())
            report.append({"name": e["name"], "status": "cached"})
            continue
        try:
            name, frame, licence = fetcher(int(e["openml_id"]))
        except Exception as exc:  # network/provider failure: report, keep going
            report.append({"name": e["name"], "status": "error", "error": f"fetch failed: {exc}"})
            continue
        error = None
        if name.lower() != str(e["openml_name"]).lower():
            error = f"OpenML id {e['openml_id']} is {name!r}, expected {e['openml_name']!r}"
        elif e["target"] not in frame.columns:
            error = f"target {e['target']!r} not in columns"
        data = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        if error is None and e["sha256"] is not None and _sha(data) != e["sha256"]:
            error = "sha256 differs from the manifest (the dataset changed upstream?)"
        if error:
            report.append({"name": e["name"], "status": "error", "error": error})
            continue
        path.write_bytes(data)
        if record_hashes:
            e["sha256"] = e["sha256"] or _sha(data)
            e["license"] = e["license"] or licence
        report.append({"name": e["name"], "status": "ok", "rows": len(frame), "columns": frame.shape[1]})
    return report, updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", help="dataset name (repeatable)")
    parser.add_argument("--record-hashes", action="store_true",
                        help="write new hashes/licences to the manifest")
    args = parser.parse_args(argv)
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = load_manifest()
    chosen = [e for e in entries if not args.only or e["name"] in args.only]
    report, updated = fetch_all(chosen, DATA_DIR, record_hashes=args.record_hashes)
    for r in report:
        extra = r.get("error") or (f"{r['rows']} x {r['columns']}" if "rows" in r else "")
        print(f"[{r['status']}] {r['name']} {extra}")
    if args.record_hashes:
        by_name = {e["name"]: e for e in updated}
        doc["datasets"] = [by_name.get(e["name"], e) for e in entries]
        MANIFEST.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"updated {MANIFEST}")
    return 0 if all(r["status"] != "error" for r in report) else 1


if __name__ == "__main__":
    sys.exit(main())
