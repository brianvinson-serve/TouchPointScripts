#!/usr/bin/env python3
"""Validate and summarize a DataDictionary_Export.py CSV download.

Usage:
    python3 local/parse_data_dictionary_export.py path/to/export.csv
    python3 local/parse_data_dictionary_export.py path/to/export.csv --output report.md

LOCAL MAC UTILITY ONLY. Do not deploy this file into TouchPoint.
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
import sys

REQUIRED_COLUMNS = {
    "Section",
    "QueryId",
    "SchemaName",
    "TableName",
    "ColumnName",
    "DataType",
    "Nullable",
    "ApproxRowCount",
    "ConstraintType",
    "ReferencedTable",
    "IndexName",
    "Finding",
    "Error",
}


def load_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fields)
        if missing:
            raise ValueError("CSV is missing required columns: {}".format(", ".join(missing)))
        return list(reader)


def markdown_report(path, rows):
    by_section = Counter(row["Section"] for row in rows)
    errors = [row for row in rows if row.get("Error", "").strip()]
    tables = [row for row in rows if row["Section"] == "TableInventory" and row.get("TableName")]
    columns = [row for row in rows if row["Section"] == "ColumnInventory" and row.get("ColumnName")]
    row_counts = [row for row in rows if row["Section"] == "ApproximateRowCounts" and row.get("TableName")]
    primary_keys = [row for row in rows if row["Section"] == "PrimaryKeys" and row.get("ColumnName")]
    foreign_keys = [row for row in rows if row["Section"] == "ForeignKeys" and row.get("ColumnName")]
    indexes = [row for row in rows if row["Section"] == "Indexes" and row.get("ColumnName")]

    columns_by_table = defaultdict(list)
    for row in columns:
        columns_by_table[(row.get("SchemaName", ""), row.get("TableName", ""))].append(row)

    count_lookup = {}
    for row in row_counts:
        count_lookup[(row.get("SchemaName", ""), row.get("TableName", ""))] = row.get("ApproxRowCount", "")

    lines = [
        "# RockPointe TouchPoint Data Dictionary Export Summary",
        "",
        "Source CSV: `{}`".format(path.name),
        "",
        "## Validation",
        "",
        "- CSV rows: `{}`".format(len(rows)),
        "- Tables/views: `{}`".format(len(tables)),
        "- Columns: `{}`".format(len(columns)),
        "- Primary-key columns: `{}`".format(len(primary_keys)),
        "- Foreign-key columns: `{}`".format(len(foreign_keys)),
        "- Index key columns: `{}`".format(len(indexes)),
        "- Probe errors: `{}`".format(len(errors)),
        "",
        "## Sections",
        "",
        "| Section | Rows |",
        "|---|---:|",
    ]
    for section, count in sorted(by_section.items()):
        lines.append("| `{}` | {} |".format(section, count))

    lines.extend(["", "## Probe errors", ""])
    if errors:
        for row in errors:
            lines.append("- **{} / {}:** {}".format(row.get("QueryId") or "unknown", row.get("Section") or "unknown", row["Error"].replace("\n", " ")))
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Table inventory",
        "",
        "| Schema | Table/view | Type | Columns | Approx. rows |",
        "|---|---|---|---:|---:|",
    ])
    for row in sorted(tables, key=lambda item: (item.get("SchemaName", ""), item.get("TableName", ""))):
        key = (row.get("SchemaName", ""), row.get("TableName", ""))
        lines.append("| `{}` | `{}` | {} | {} | {} |".format(
            row.get("SchemaName", ""),
            row.get("TableName", ""),
            row.get("ObjectType", ""),
            len(columns_by_table.get(key, [])),
            count_lookup.get(key, ""),
        ))

    lines.extend([
        "",
        "## Next profiling candidates",
        "",
        "These are candidates, not confirmed meanings. Run focused value/null/join probes before adding semantic claims to `DB_REFERENCE.md`.",
        "",
    ])
    candidate_names = ("status", "type", "date", "peopleid", "personid", "organizationid", "orgid", "ownerid", "assigneeid")
    candidates = []
    for row in columns:
        name = row.get("ColumnName", "")
        if any(token in name.lower() for token in candidate_names):
            candidates.append(row)
    for row in candidates[:250]:
        lines.append("- `{}.{}`.`{}` — `{}`, nullable `{}`".format(
            row.get("SchemaName", ""),
            row.get("TableName", ""),
            row.get("ColumnName", ""),
            row.get("DataType", ""),
            row.get("Nullable", ""),
        ))
    if len(candidates) > 250:
        lines.append("- … {} more candidates omitted from this summary.".format(len(candidates) - 250))

    lines.extend([
        "",
        "## Documentation guardrail",
        "",
        "This report confirms exposed object/column structure and database-declared relationships. It does **not** establish business meaning for a table, status ID, type ID, or nullable value. Add those meanings to `DB_REFERENCE.md` only after focused live probes confirm them.",
        "",
    ])
    return "\n".join(lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Validate and summarize a RockPointe TouchPoint data dictionary CSV export.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path, help="Write Markdown report to this path instead of stdout.")
    args = parser.parse_args()

    if not args.csv_path.is_file():
        parser.error("CSV file does not exist: {}".format(args.csv_path))

    try:
        rows = load_rows(args.csv_path)
    except (OSError, ValueError, csv.Error) as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1

    report = markdown_report(args.csv_path, rows)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
        print("Wrote {}".format(args.output))
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
