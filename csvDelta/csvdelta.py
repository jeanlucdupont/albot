#!/usr/bin/env python3
"""Compare two CSV snapshots by one or more unique key columns."""
import argparse
import csv
import json
import sys
from pathlib import Path


def load(path, keys, encoding, delimiter):
    with Path(path).open(encoding=encoding, newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        columns = reader.fieldnames
        if not columns or any(not c.strip() for c in columns):
            raise ValueError(f"{path}: missing or empty column headers")
        if len(set(columns)) != len(columns):
            raise ValueError(f"{path}: duplicate column headers")
        missing = set(keys) - set(columns)
        if missing:
            raise ValueError(f"{path}: missing key columns: {', '.join(sorted(missing))}")
        rows = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}: malformed row ending at line {reader.line_num}")
            key = tuple(row[k] for k in keys)
            if any(not value.strip() for value in key):
                raise ValueError(f"{path}: empty key at line {reader.line_num}")
            if key in rows:
                raise ValueError(f"{path}: duplicate key {key!r}; choose more key columns")
            rows[key] = row
        return columns, rows


def compare(old_columns, old, new_columns, new, keys, ignore):
    columns = [c for c in old_columns if c in new_columns and c not in keys and c not in ignore]
    added = [row for key, row in new.items() if key not in old]
    removed = [row for key, row in old.items() if key not in new]
    changed = []
    unchanged = 0
    for key, after in new.items():
        if key not in old:
            continue
        before = old[key]
        differences = [c for c in columns if before[c] != after[c]]
        if not differences:
            unchanged += 1
        for column in differences:
            changed.append({"key": dict(zip(keys, key)), "column": column,
                            "before": before[column], "after": after[column]})
    changed_rows = len({tuple(change["key"][k] for k in keys) for change in changed})
    return {"summary": {"old_rows": len(old), "new_rows": len(new),
                        "added_rows": len(added), "removed_rows": len(removed),
                        "changed_rows": changed_rows, "changed_cells": len(changed),
                        "unchanged_rows": unchanged},
            "schema": {"added_columns": [c for c in new_columns if c not in old_columns],
                       "removed_columns": [c for c in old_columns if c not in new_columns]},
            "keys": keys, "ignored_columns": ignore,
            "added": added, "removed": removed, "changed": changed}


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", help="Earlier CSV report")
    parser.add_argument("new", help="Later CSV report")
    parser.add_argument("--key", nargs="+", required=True, help="Unique identifying column(s)")
    parser.add_argument("--ignore", nargs="+", default=[], help="Columns excluded from value comparisons")
    parser.add_argument("--output", default="csvdelta-output", help="New output directory (must not exist)")
    parser.add_argument("--delimiter", default=",", help="Single-character input delimiter")
    parser.add_argument("--encoding", default="utf-8-sig", help="Input encoding; default: utf-8-sig")
    args = parser.parse_args(argv)
    try:
        if len(args.delimiter) != 1:
            raise ValueError("--delimiter must be a single character")
        if len(set(args.key)) != len(args.key):
            raise ValueError("--key contains duplicate column names")
        if set(args.key) & set(args.ignore):
            raise ValueError("Key columns cannot be ignored")
        old_columns, old = load(args.old, args.key, args.encoding, args.delimiter)
        new_columns, new = load(args.new, args.key, args.encoding, args.delimiter)
        unknown = set(args.ignore) - (set(old_columns) | set(new_columns))
        if unknown:
            raise ValueError(f"Unknown ignored columns: {', '.join(sorted(unknown))}")
        result = compare(old_columns, old, new_columns, new, args.key, args.ignore)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=False)
        write_csv(out / "added.csv", new_columns, result["added"])
        write_csv(out / "removed.csv", old_columns, result["removed"])
        # Prefix key headers so keys named column/before/after cannot collide.
        change_columns = [f"key:{k}" for k in args.key] + ["column", "before", "after"]
        change_rows = [{**{f"key:{k}": c["key"][k] for k in args.key},
                        **{k: c[k] for k in ("column", "before", "after")}}
                       for c in result["changed"]]
        write_csv(out / "changed.csv", change_columns, change_rows)
        (out / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result["summary"], indent=2))
        if any(result["schema"].values()):
            print("Schema changes:", json.dumps(result["schema"]))
        print(f"Reports saved to {out.resolve()}")
        return 0
    except (OSError, ValueError, LookupError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
