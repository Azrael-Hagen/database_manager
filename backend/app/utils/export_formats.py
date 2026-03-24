"""
Export format utilities: TXT (tab-delimited) and DAT (pipe-delimited) writers.
CSV and Excel are handled inline in the export router for performance reasons;
these helpers cover the less-common formats used by legacy systems.
"""

from __future__ import annotations

from io import StringIO
from typing import Any


def _ser(v: Any) -> str:
    """Serialize a value to a safe string."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def write_txt(
    data: list[dict],
    campos: list[str],
    delimiter: str = "\t",
) -> bytes:
    """
    Serialize rows as tab-delimited UTF-8 text (with BOM for Excel compatibility).

    Args:
        data:      List of row dicts.
        campos:    Ordered column names (used as header and to pick values).
        delimiter: Column separator (default: tab).

    Returns:
        Encoded bytes (UTF-8 with BOM).
    """
    output = StringIO()
    output.write(delimiter.join(campos) + "\n")
    for row in data:
        output.write(delimiter.join(_ser(row.get(c)) for c in campos) + "\n")
    return output.getvalue().encode("utf-8-sig")


def write_dat(
    data: list[dict],
    campos: list[str],
    delimiter: str = "|",
) -> bytes:
    """
    Serialize rows as pipe-delimited DAT file.

    Internal occurrences of the delimiter character inside values are escaped
    with a backslash.  Newline characters inside values are replaced with the
    literal string ``\\n``.

    Args:
        data:      List of row dicts.
        campos:    Ordered column names.
        delimiter: Column separator (default: pipe ``|``).

    Returns:
        Encoded bytes (UTF-8 with BOM).
    """
    output = StringIO()
    output.write(delimiter.join(campos) + "\n")
    for row in data:
        values: list[str] = []
        for c in campos:
            val = _ser(row.get(c))
            # Escape embedded delimiters and newlines so the file stays parseable
            val = val.replace("\\", "\\\\")  # escape backslash first
            val = val.replace(delimiter, "\\" + delimiter)
            val = val.replace("\n", "\\n").replace("\r", "")
            values.append(val)
        output.write(delimiter.join(values) + "\n")
    return output.getvalue().encode("utf-8-sig")
