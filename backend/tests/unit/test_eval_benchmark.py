"""Spec 10 NFR-15/16: benchmark manifest + fetcher, seeded corruption generator."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from eval import build_benchmark, corrupt, fetch_datasets

N = 200


def source_frame() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "age": rng.integers(18, 80, N),
        "income": rng.normal(50_000, 8_000, N).round(2),
        "score": rng.normal(0, 1, N).round(4),
        "city": rng.choice(["Paris", "Lyon", "Nice"], N),
        "label": rng.integers(0, 2, N),
    })


def write_source(tmp_path, df=None, name="toy.csv"):
    path = tmp_path / "src" / name
    path.parent.mkdir(exist_ok=True)
    (df if df is not None else source_frame()).to_csv(path, index=False)
    return path


def ops(entries):
    return {(e["op"], e["column"]) for e in entries}


def test_nfr_ac14_same_seed_is_byte_identical_and_source_untouched(tmp_path):
    src = write_source(tmp_path)
    before = src.read_bytes()
    sources = [build_benchmark.Source(path=src, target="label")]
    g1 = build_benchmark.build(sources, [1, 2], tmp_path / "a")
    g2 = build_benchmark.build(sources, [1, 2], tmp_path / "b")
    for name in g1:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert (tmp_path / "a" / "golden.json").read_bytes() == (tmp_path / "b" / "golden.json").read_bytes()
    assert g1 == g2
    assert (tmp_path / "a" / "toy__s1.csv").read_bytes() != (tmp_path / "a" / "toy__s2.csv").read_bytes()
    assert src.read_bytes() == before
    assert g1["toy__s1.csv"]["sha256"] and g1["toy__s1.csv"]["seed"] == 1


def test_nfr_ac15_every_injection_is_present_and_in_the_golden():
    df = source_frame()
    out, entry = corrupt.corrupt(df, "label", seed=3)
    inj = {i["type"]: i for i in entry["injections"]}
    assert set(inj) == set(corrupt.INJECTION_ORDER) and entry["skipped"] == []
    n_dup = inj["duplicates"]["rows"]
    assert n_dup == round(0.02 * N) and len(out) == N + n_dup
    assert int(out.duplicated().sum()) == n_dup
    # target untouched (first N rows, before the appended duplicates)
    assert out["label"].iloc[:N].tolist() == df["label"].tolist()

    ids = out["record_id"].iloc[:N]
    assert ids.is_unique and ids.str.match(r"^REC-\d{6}$").all()
    assert (out["export_batch"] == "B1").all()
    assert out["label_copy"].tolist() == out["label"].tolist()

    miss = inj["missing"]["column"]
    assert out[miss].iloc[:N].isna().sum() == round(0.10 * N) == inj["missing"]["rows"]
    heavy = inj["heavy_missing"]["column"]
    assert out[heavy].iloc[:N].isna().sum() == round(0.80 * N)
    outl = inj["outliers"]["column"]
    assert (out[outl].iloc[:N] == 50 * df[outl].abs().max()).sum() == inj["outliers"]["rows"] >= 1
    text = inj["text_noise"]["column"]
    assert text == "city"
    noisy = out[text].iloc[:N] != df[text]
    assert noisy.sum() == inj["text_noise"]["rows"] == round(0.20 * N)
    assert all(v.isupper() or v != v.strip() for v in out[text].iloc[:N][noisy])
    assert len({miss, heavy, outl, text}) == 4 and "label" not in {miss, heavy, outl, text}

    assert {("drop_column", "record_id"), ("drop_column", "export_batch"), ("drop_column", "label_copy"),
            ("impute", miss), ("drop_column", heavy), ("clip_outliers", outl),
            ("standardize_text", text), ("drop_duplicates", "*")} == ops(entry["expected"])
    assert {("drop_column", "label"), ("drop_column", miss)} <= ops(entry["forbidden"])
    assert entry["target"] == "label"


def test_nfr_ac15_types_without_eligible_column_are_skipped():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0] * 10, "y": [0, 1] * 20})
    _, entry = corrupt.corrupt(df, "y", seed=0)
    done = {i["type"] for i in entry["injections"]}
    assert "text_noise" in entry["skipped"]
    assert done | set(entry["skipped"]) == set(corrupt.INJECTION_ORDER)
    assert not set(entry["skipped"]) & done


def test_nfr_ac16_base_golden_is_merged(tmp_path):
    src = write_source(tmp_path)
    base = {"target": "label", "expected": [{"op": "impute", "column": "age", "why": "base"}],
            "acceptable": [{"op": "cast_type", "column": "city"}],
            "forbidden": [{"op": "drop_column", "column": "income"}]}
    g = build_benchmark.build([build_benchmark.Source(path=src, target="label", golden=base)], [1],
                              tmp_path / "out")
    entry = g["toy__s1.csv"]
    assert entry["target"] == "label" and entry["source"] == "toy.csv"
    assert ("impute", "age") in ops(entry["expected"])
    assert ("cast_type", "city") in ops(entry["acceptable"])
    assert ("drop_column", "income") in ops(entry["forbidden"])
    assert len(ops(entry["expected"])) == len(entry["expected"])  # no duplicates after the union


def test_nfr_ac16_protected_columns_and_no_binary_outliers(tmp_path):
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"a": rng.normal(size=N), "b": rng.normal(size=N), "flag": rng.integers(0, 2, N),
                       "y": rng.integers(0, 2, N)})
    # only "b" is left for heavy missing once "a" is protected; "flag" (0/1) can't take outliers
    base = {"target": "y", "expected": [], "acceptable": [],
            "forbidden": [{"op": "drop_column", "column": "a"}]}
    for seed in range(8):
        src = write_source(tmp_path, df, name=f"p{seed}.csv")
        entry = build_benchmark.build([build_benchmark.Source(path=src, target="y", golden=base)], [seed],
                                      tmp_path / f"out{seed}")[f"p{seed}__s{seed}.csv"]
        inj = {i["type"]: i["column"] for i in entry["injections"]}
        assert inj.get("heavy_missing") != "a"
        assert inj.get("outliers") != "flag"
        assert not ops(entry["expected"]) & ops(entry["forbidden"])


def stub_fetcher(table):
    calls = []

    def fetch(openml_id):
        calls.append(openml_id)
        return table[openml_id]
    fetch.calls = calls
    return fetch


def entry(name, oid, target="label", sha=None):
    return {"name": name, "openml_id": oid, "openml_name": name, "target": target,
            "task": "classification", "license": None, "sha256": sha}


def test_nfr_ac17_fetch_validates_names_targets_and_hashes(tmp_path):
    df = source_frame()
    fetch = stub_fetcher({1: ("good", df, "CC0"), 2: ("other-name", df, "CC0"),
                          3: ("notarget", df.drop(columns="label"), "CC0"), 4: ("badhash", df, "CC0")})
    manifest = [entry("good", 1), entry("wrongname", 2), entry("notarget", 3),
                entry("badhash", 4, sha="0" * 64)]
    report, updated = fetch_datasets.fetch_all(manifest, tmp_path, fetcher=fetch, record_hashes=True)
    status = {r["name"]: r["status"] for r in report}
    assert status == {"good": "ok", "wrongname": "error", "notarget": "error", "badhash": "error"}
    assert sorted(p.name for p in tmp_path.glob("*.csv")) == ["good.csv"]
    assert "label" in pd.read_csv(tmp_path / "good.csv").columns
    good = next(e for e in updated if e["name"] == "good")
    assert good["sha256"] and good["license"] == "CC0"
    assert next(e for e in updated if e["name"] == "wrongname")["sha256"] is None

    # a second run with the recorded hash does not fetch again
    report2, _ = fetch_datasets.fetch_all([good], tmp_path, fetcher=fetch)
    assert report2[0]["status"] == "cached" and fetch.calls.count(1) == 1


def test_nfr_ac17_manifest_requires_fields(tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"datasets": [{"name": "x", "openml_id": 1}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="target"):
        fetch_datasets.load_manifest(bad)
    entries = fetch_datasets.load_manifest(fetch_datasets.MANIFEST)
    assert len(entries) >= 12 and len({e["name"] for e in entries}) == len(entries)
