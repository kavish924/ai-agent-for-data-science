"""Chart selection, cap, determinism and overlays (Spec 06) - pure service, no API."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.services.charts import generate_charts
from app.services.profiler import profile_dataframe

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
TITANIC = pd.read_csv(SAMPLES / "titanic.csv")


def _cleaned_titanic() -> pd.DataFrame:
    df = TITANIC.drop(columns=["Cabin"]).copy()
    df["Age"] = df["Age"].fillna(df["Age"].median())
    df["Embarked"] = df["Embarked"].fillna("S")
    return df


def _run(cleaned, out: Path, *, original=None, changed=frozenset(), max_charts=12):
    original = original if original is not None else cleaned
    return generate_charts(
        cleaned,
        after_profile=profile_dataframe("sid", cleaned),
        original_profile=profile_dataframe("sid", original),
        out_dir=out,
        max_charts=max_charts,
        before=original,
        changed_columns=set(changed),
    )


def _kinds(manifest: dict) -> list[tuple[str, str | None]]:
    return [(c["kind"], c["column"]) for c in manifest["charts"]]


def test_ch_ac1_titanic_standard_charts(tmp_path):
    manifest = _run(_cleaned_titanic(), tmp_path, original=TITANIC, changed={"Age", "Embarked"})
    kinds = _kinds(manifest)
    assert manifest["status"] == "completed"
    assert ("distribution", "Age") in kinds
    assert ("distribution", "Fare") in kinds
    assert ("bar", "Sex") in kinds
    assert ("correlation", None) in kinds
    for chart in manifest["charts"]:
        assert (tmp_path / chart["file"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_ch_ac2_cap_enforced_and_skips_recorded(tmp_path):
    rng = np.random.default_rng(42)
    wide = pd.DataFrame({f"x{i:02d}": rng.normal(size=200) for i in range(30)})
    manifest = _run(wide, tmp_path, max_charts=12)
    assert len(manifest["charts"]) == 12
    assert len(list(tmp_path.glob("*.png"))) == 12
    capped = [s for s in manifest["skipped"] if "cap" in s["reason"]]
    assert len(capped) == 30 + 1 - 12  # 30 distributions + 1 heatmap, 12 kept


def test_ch_ac3_no_nulls_means_no_missing_map(tmp_path):
    manifest = _run(_cleaned_titanic(), tmp_path)
    assert ("missing_map", None) not in _kinds(manifest)
    assert {"kind": "missing_map", "column": None, "reason": "no missing values"} in manifest["skipped"]


def test_ch_fr05_missing_map_when_nulls_remain(tmp_path):
    manifest = _run(TITANIC, tmp_path)
    assert _kinds(manifest)[0] == ("missing_map", None)


def test_ch_ac4_png_bytes_are_deterministic(tmp_path):
    first = _run(_cleaned_titanic(), tmp_path / "a", original=TITANIC, changed={"Age"})
    second = _run(_cleaned_titanic(), tmp_path / "b", original=TITANIC, changed={"Age"})
    assert [c["file"] for c in first["charts"]] == [c["file"] for c in second["charts"]]
    for chart in first["charts"]:
        assert (tmp_path / "a" / chart["file"]).read_bytes() == (tmp_path / "b" / chart["file"]).read_bytes()


def test_ch_ac5_text_only_dataset_does_not_crash(tmp_path):
    notes = [f"free text number {i} about {i % 7}" for i in range(60)]
    text = pd.DataFrame({"note": notes * 2})  # 60 distinct in 120 rows: text, not an identifier
    manifest = _run(text, tmp_path)
    assert manifest["status"] == "completed"
    assert manifest["charts"] == []
    assert any(s["column"] == "note" and "text" in s["reason"] for s in manifest["skipped"])


def test_ch_ac8_before_overlay_only_on_changed_columns(tmp_path):
    manifest = _run(_cleaned_titanic(), tmp_path, original=TITANIC, changed={"Age"})
    by_column = {c["column"]: c for c in manifest["charts"] if c["kind"] == "distribution"}
    assert by_column["Age"]["before_overlay"] is True
    assert by_column["Fare"]["before_overlay"] is False


def test_ch_fr06_priority_follows_original_issues(tmp_path):
    # After cleaning there are no nulls; Age/Embarked had nulls in the ORIGINAL profile,
    # so they come right after the dataset-wide heatmap.
    manifest = _run(_cleaned_titanic(), tmp_path, original=TITANIC, max_charts=3)
    assert _kinds(manifest) == [("correlation", None), ("distribution", "Age"), ("bar", "Embarked")]


def test_ch_fr12_no_chart_for_identifiers_or_text(tmp_path):
    manifest = _run(_cleaned_titanic(), tmp_path, max_charts=50)
    charted = {c["column"] for c in manifest["charts"]}
    assert not charted & {"PassengerId", "Name", "Ticket"}
    reasons = {s["column"]: s["reason"] for s in manifest["skipped"] if s["column"]}
    assert "identifier" in reasons["PassengerId"]
    assert "text" in reasons["Ticket"]


def test_ch_fr07_file_names_are_ordered_and_safe(tmp_path):
    df = pd.DataFrame({"a b/c": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 1.0, 4.0, 3.0]})
    manifest = _run(df, tmp_path)
    names = [c["file"] for c in manifest["charts"]]
    assert names[0].startswith("01_")
    assert all("/" not in n and " " not in n for n in names)
