"""Unit tests for CSV ingestion (Spec 01)."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from app.services.ingestion import IngestionError, detect_encoding, parse_upload, sniff_delimiter


def test_detect_encoding_latin1_decodes():
    raw = "caf\xe9,1\nrow,2\n".encode("latin-1")
    encoding = detect_encoding(raw[:65536])
    df = pd.read_csv(io.BytesIO(raw), encoding=encoding)
    assert list(df.columns) == ["café", "1"]  # header decoded correctly
    assert df.iloc[0, 0] == "row"


def test_detect_encoding_utf8_fallback():
    assert detect_encoding(b"") == "utf-8"


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ("a,b,c\n1,2,3\n", ","),
        ("a;b;c\n1;2;3\n", ";"),
        ("a\tb\tc\n1\t2\t3\n", "\t"),
        ("a|b|c\n1|2|3\n", "|"),
    ],
)
def test_sniff_delimiter_matrix(sample, expected):
    assert sniff_delimiter(sample) == expected


def test_sniff_delimiter_fallback_comma():
    assert sniff_delimiter("just some words\n") == ","


def test_parse_upload_happy_path():
    df, encoding, delimiter = parse_upload("name,age\nann,30\nbob,25\n".encode("utf-8"))
    assert list(df.columns) == ["name", "age"]
    assert len(df) == 2
    assert delimiter == ","
    assert encoding


def test_parse_upload_semicolon_latin1():
    raw = "naam;leeftijd\nann;30\nbob;25\n".encode("latin-1")
    df, encoding, delimiter = parse_upload(raw)
    assert delimiter == ";"
    assert list(df.columns) == ["naam", "leeftijd"]


def test_parse_upload_rejects_binary_junk():
    with pytest.raises(IngestionError) as excinfo:
        parse_upload(b"\x00\x01\x02\x03binaryjunk\x00\x01")
    assert excinfo.value.status_code == 415
    assert excinfo.value.code == "not_a_csv"


def test_parse_upload_rejects_header_only():
    with pytest.raises(IngestionError) as excinfo:
        parse_upload(b"a,b\n")
    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "no_data_rows"


def test_parse_upload_rejects_single_column():
    with pytest.raises(IngestionError) as excinfo:
        parse_upload(b"only\n1\n2\n")
    assert excinfo.value.status_code == 415
