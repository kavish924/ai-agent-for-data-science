"""CSV ingestion: encoding detection, delimiter sniffing, parsing (Spec 01)."""

from __future__ import annotations

import csv
import io

import pandas as pd
from charset_normalizer import from_bytes


class IngestionError(Exception):
    """Raised when an upload cannot be accepted; maps to an API error (Spec 09)."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def detect_encoding(head: bytes) -> str:
    """Detect file encoding (FR-UP-02).

    Order: strict UTF-8 (most CSVs) -> cp1252 (Windows/Excel exports) ->
    charset detection -> latin-1 (never fails). Charset detection on tiny
    samples can guess exotic codecs, so it only runs when the common ones fail.
    """
    for candidate in ("utf-8", "cp1252"):
        try:
            head.decode(candidate, errors="strict")
            return candidate
        except UnicodeDecodeError:
            continue
    match = from_bytes(head).best() if head else None
    if match is None:
        return "latin-1"  # always decodable last resort
    encoding = (match.encoding or "utf-8").lower().replace("_", "-")
    aliases = {
        "iso-8859-1": "latin-1",
        "windows-1252": "cp1252",
        "mbcs": "cp1252",
    }
    return aliases.get(encoding, encoding)


def sniff_delimiter(sample: str) -> str:
    """Sniff the field delimiter from a text sample; fall back to comma (FR-UP-03)."""
    try:
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_upload(data: bytes) -> tuple[pd.DataFrame, str, str]:
    """Parse raw upload bytes into a DataFrame.

    Returns:
        (dataframe, encoding_used, delimiter)

    Raises:
        IngestionError: 415 for non-CSV content, 422 for header-only files (FR-UP-08/10).

    Note:
        Single-column CSVs are rejected by the delimiter-presence check in v1;
        this is a documented sniffing limitation (see Spec 01, FR-UP-08 note).
    """
    encoding = detect_encoding(data[:65536])
    sample = data[:65536].decode(encoding, errors="replace")
    delimiter = sniff_delimiter(sample)

    lines = sample.splitlines()
    if not lines or delimiter not in lines[0]:
        raise IngestionError(
            415, "not_a_csv", "File content is not a delimited CSV (encoding/delimiter detection failed)."
        )

    try:
        df = pd.read_csv(io.BytesIO(data), sep=delimiter, encoding=encoding, engine="python")
    except UnicodeDecodeError:
        encoding = "latin-1"  # always decodable; record the fallback (FR-UP-02)
        df = pd.read_csv(io.BytesIO(data), sep=delimiter, encoding=encoding, engine="python")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise IngestionError(
            415, "not_a_csv", "File content could not be parsed as CSV."
        ) from exc

    if df.shape[1] == 0 or len(df) == 0:
        raise IngestionError(
            422, "no_data_rows", "CSV must contain a header and at least one data row."
        )
    return df, encoding, delimiter
