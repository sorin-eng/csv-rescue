#!/usr/bin/env python3
"""Offline CSV import audit and explicitly requested safe cleanup. Python 3.10+."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|"}

class Blocked(Exception):
    def __init__(self, reason):
        self.reason = reason

def delimiter_arg(value):
    value = DELIMITERS.get(value, value)
    if value not in (",", ";", "\t", "|"):
        raise argparse.ArgumentTypeError("Choose comma, semicolon, tab or pipe.")
    return value

def audit_and_clean(args):
    if (args.trim or args.drop_exact_duplicates or args.out_delimiter) and not args.output:
        raise Blocked("output_required")
    source = Path(args.input)
    if not source.is_file():
        raise Blocked("input_unavailable")
    if args.output and Path(args.output).resolve() == source.resolve():
        raise Blocked("source_is_output")
    if source.stat().st_size > MAX_BYTES:
        raise Blocked("byte_limit")
    raw = source.read_bytes()
    if len(raw) > MAX_BYTES:
        raise Blocked("byte_limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Blocked("invalid_utf8") from None
    if not text.strip():
        raise Blocked("empty_file")
    delimiter = args.delimiter
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
        except csv.Error:
            first = text.splitlines()[0]
            candidates = [d for d in (",", ";", "\t", "|") if d in first]
            if len(candidates) > 1:
                raise Blocked("ambiguous_delimiter") from None
            delimiter = candidates[0] if candidates else ","
    csv.field_size_limit(MAX_BYTES)
    try:
        records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
    except csv.Error:
        raise Blocked("invalid_csv") from None
    if not records or not records[0]:
        raise Blocked("empty_file")
    headers, body = records[0], records[1:]
    if any(not name.strip() for name in headers):
        raise Blocked("blank_headers")
    if len(set(headers)) != len(headers):
        raise Blocked("duplicate_headers")
    if len(body) > MAX_ROWS:
        raise Blocked("row_limit")
    if any(len(row) != len(headers) for row in body):
        raise Blocked("inconsistent_columns")
    seen = set()
    duplicates = 0
    for row in body:
        key = tuple(row)
        if key in seen:
            duplicates += 1
        seen.add(key)
    issues = {
        "exact_duplicate_rows": duplicates,
        "blank_cells": sum(not cell.strip() for row in body for cell in row),
        "whitespace_cells": sum(cell != cell.strip() for row in body for cell in row),
        "formula_like_cells": sum(cell.lstrip().startswith(("=", "+", "-", "@")) for row in body for cell in row),
    }
    report = {
        "ok": True,
        "mode": "clean" if args.output else "audit",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(body),
        "columns": headers,
        "delimiter": delimiter,
        "issues": issues,
        "trimmed_cells": 0,
        "removed_rows": 0,
    }
    if not args.output:
        return report
    result = []
    seen = set()
    for row in body:
        if args.trim:
            report["trimmed_cells"] += sum(cell != cell.strip() for cell in row)
            row = [cell.strip() for cell in row]
        key = tuple(row)
        if args.drop_exact_duplicates and key in seen:
            report["removed_rows"] += 1
            continue
        seen.add(key)
        result.append(row)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=args.out_delimiter or delimiter, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(result)
    output_bytes = buf.getvalue().encode("utf-8")
    # Validate everything before creating the destination. Never overwrite it.
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise Blocked("output_exists") from None
    with os.fdopen(fd, "wb") as output:
        output.write(output_bytes)
    report["output_rows"] = len(result)
    report["output_sha256"] = hashlib.sha256(output_bytes).hexdigest()
    report["output_delimiter"] = args.out_delimiter or delimiter
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 CSV; max 5,000 data rows / 10 MiB")
    parser.add_argument("--delimiter", type=delimiter_arg, help="Input delimiter override")
    parser.add_argument("--output", help="New file only; cannot overwrite input or existing files")
    parser.add_argument("--out-delimiter", type=delimiter_arg, help="Explicit output delimiter")
    parser.add_argument("--trim", action="store_true", help="Trim data cells; header names stay literal")
    parser.add_argument("--drop-exact-duplicates", action="store_true", help="Keep first exact row after any requested trim; never merge by name/email")
    args = parser.parse_args()
    try:
        report = audit_and_clean(args)
    except Blocked as error:
        print(json.dumps({"ok": False, "blocked_reason": error.reason}))
        return 2
    except OSError:
        # Do not echo filenames or cell content. On a write failure, inspect the
        # destination before using it; a newly created partial file may remain.
        print(json.dumps({"ok": False, "blocked_reason": "io_error"}))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
