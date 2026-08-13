#!/usr/bin/env python3
"""Build a queryable SQLite index from RockPointe data-dictionary CSV exports.

SQLite is a generated local index, not the authored source of truth:
- CSV exports are immutable evidence from TouchPoint.
- DB_REFERENCE.md contains curated, reviewed knowledge.
- This SQLite file supports fast ad-hoc queries without running Postgres.
"""

import argparse
import csv
from pathlib import Path
import sqlite3
import sys


def safe_int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def build_database(structural_path, focused_path, output_path):
    structural_fields, structural_rows = read_csv(structural_path)
    required = {"Section", "QueryId", "SchemaName", "TableName", "ColumnName", "Finding", "Error"}
    missing = sorted(required - set(structural_fields))
    if missing:
        raise ValueError("Structural CSV missing columns: {}".format(", ".join(missing)))

    focused_fields = []
    focused_rows = []
    if focused_path:
        focused_fields, focused_rows = read_csv(focused_path)
        missing = sorted(required - set(focused_fields))
        if missing:
            raise ValueError("Focused CSV missing columns: {}".format(", ".join(missing)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(output_path))
    try:
        connection.executescript("""
        PRAGMA foreign_keys = ON;
        DROP TABLE IF EXISTS export_rows;
        DROP TABLE IF EXISTS exports;
        CREATE TABLE exports (
            export_id INTEGER PRIMARY KEY,
            export_kind TEXT NOT NULL CHECK (export_kind IN ('structural', 'focused')),
            source_file TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER NOT NULL
        );
        CREATE TABLE export_rows (
            export_id INTEGER NOT NULL REFERENCES exports(export_id) ON DELETE CASCADE,
            row_number INTEGER NOT NULL,
            section TEXT,
            query_id TEXT,
            schema_name TEXT,
            table_name TEXT,
            column_name TEXT,
            ordinal_position INTEGER,
            data_type TEXT,
            nullable TEXT,
            object_type TEXT,
            approximate_row_count INTEGER,
            constraint_name TEXT,
            constraint_type TEXT,
            key_ordinal INTEGER,
            referenced_schema TEXT,
            referenced_table TEXT,
            referenced_column TEXT,
            index_name TEXT,
            is_unique TEXT,
            is_primary_key TEXT,
            finding TEXT,
            error TEXT,
            PRIMARY KEY (export_id, row_number)
        );
        CREATE INDEX ix_export_rows_section ON export_rows(section);
        CREATE INDEX ix_export_rows_table ON export_rows(schema_name, table_name);
        CREATE INDEX ix_export_rows_column ON export_rows(column_name);
        CREATE INDEX ix_export_rows_query ON export_rows(query_id);
        CREATE INDEX ix_export_rows_reference ON export_rows(referenced_table, referenced_column);
        """)

        def insert_export(kind, path, rows):
            cursor = connection.execute(
                "INSERT INTO exports(export_kind, source_file, row_count) VALUES (?, ?, ?)",
                (kind, path.name, len(rows)),
            )
            export_id = cursor.lastrowid
            payload = []
            for row_number, row in enumerate(rows, 1):
                payload.append((
                    export_id, row_number, row.get("Section"), row.get("QueryId"),
                    row.get("SchemaName"), row.get("TableName"), row.get("ColumnName"),
                    safe_int(row.get("OrdinalPosition")), row.get("DataType"), row.get("Nullable"),
                    row.get("ObjectType"), safe_int(row.get("ApproxRowCount")),
                    row.get("ConstraintName"), row.get("ConstraintType"), safe_int(row.get("KeyOrdinal")),
                    row.get("ReferencedSchema"), row.get("ReferencedTable"), row.get("ReferencedColumn"),
                    row.get("IndexName"), row.get("IsUnique"), row.get("IsPrimaryKey"),
                    row.get("Finding"), row.get("Error"),
                ))
            connection.executemany("""
                INSERT INTO export_rows(
                    export_id, row_number, section, query_id, schema_name, table_name,
                    column_name, ordinal_position, data_type, nullable, object_type,
                    approximate_row_count, constraint_name, constraint_type, key_ordinal,
                    referenced_schema, referenced_table, referenced_column, index_name,
                    is_unique, is_primary_key, finding, error
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, payload)

        insert_export("structural", structural_path, structural_rows)
        if focused_path:
            insert_export("focused", focused_path, focused_rows)
        connection.commit()
    finally:
        connection.close()

    return len(structural_rows), len(focused_rows)


def main():
    parser = argparse.ArgumentParser(description="Build local SQLite index for RockPointe TouchPoint data dictionary exports.")
    parser.add_argument("structural_csv", type=Path)
    parser.add_argument("--focused", type=Path, help="Optional focused-confirmation CSV from the second download button.")
    parser.add_argument("--output", type=Path, default=Path("data-dictionary.sqlite"))
    args = parser.parse_args()

    if not args.structural_csv.is_file():
        parser.error("Structural CSV not found: {}".format(args.structural_csv))
    if args.focused and not args.focused.is_file():
        parser.error("Focused CSV not found: {}".format(args.focused))

    try:
        structural_count, focused_count = build_database(args.structural_csv, args.focused, args.output)
    except (OSError, ValueError, csv.Error, sqlite3.Error) as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1

    print("Built {} with {} structural rows and {} focused rows".format(args.output, structural_count, focused_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
