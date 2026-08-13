# Data Dictionary Expander

Read-only tooling for discovering and documenting the RockPointe TouchPoint schema. This is general TouchPoint infrastructure, not Student Ministry-specific.

## Architecture

Use three layers:

1. **Dated CSV exports are evidence.** They capture exactly what TouchPoint returned.
2. **Generated SQLite is the query layer.** It supports fast local SQL exploration and is reproducible from CSV.
3. **`../DB_REFERENCE.md` is curated knowledge.** Keep confirmed meanings, important IDs, safe joins, null behavior, and pitfalls there—not all 4,539 columns.

Postgres is intentionally not used. This is a small, single-user, snapshot-driven dataset. A server database would add credentials, service management, backups, and migrations without solving a current problem.

## Directory map

```text
data-dictionary-expander/
├── README.md
├── TESTING.md
├── touchpoint/
│   └── DataDictionary_Export.py
├── sql/
│   ├── inventory/
│   │   ├── 00-export-query-reference.sql
│   │   ├── 01-table-inventory.sql
│   │   ├── 02-table-column-inventory.sql
│   │   ├── 03-table-profile-template.sql
│   │   ├── 04-column-profile-templates.sql
│   │   └── 05-join-probe-templates.sql
│   └── focused/
│       └── 06-focused-live-confirmation.sql
├── local/
│   ├── parse_data_dictionary_export.py
│   └── build_data_dictionary_sqlite.py
├── templates/
│   └── DB_REFERENCE_OUTPUT_TEMPLATE.md
├── exports/
│   └── YYYY-MM-DD/
│       ├── rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv
│       └── rockpointe-touchpoint-focused-confirmation-YYYY-MM-DD.csv
├── reports/
│   └── YYYY-MM-DD/
│       ├── structural-summary.md
│       └── focused-confirmation-summary.md
└── generated/
    └── data-dictionary.sqlite   # gitignored, rebuildable
```

## First-pass workflow

1. Deploy only `touchpoint/DataDictionary_Export.py` as TouchPoint Python Script `DataDictionary_Export`.
2. Run it and download both CSV files.
3. Store them under `exports/YYYY-MM-DD/` without manually editing them.
4. Validate the structural export:

```bash
python3 local/parse_data_dictionary_export.py \
  exports/YYYY-MM-DD/rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv \
  --output reports/YYYY-MM-DD/structural-summary.md
```

5. Build the local query index:

```bash
python3 local/build_data_dictionary_sqlite.py \
  exports/YYYY-MM-DD/rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv \
  --focused exports/YYYY-MM-DD/rockpointe-touchpoint-focused-confirmation-YYYY-MM-DD.csv \
  --output generated/data-dictionary.sqlite
```

6. Review focused results and update `../DB_REFERENCE.md` with only confirmed, meaningful facts.

## Focused follow-up workflow

Use SQL scripts under `sql/` only when the exporter leaves a question unanswered or a specific application needs deeper profiling.

- Run one query block at a time in TouchPoint SQL Scripts.
- Keep everything read-only (`SELECT` only).
- Keep `TOP` limits in sample queries.
- Do not copy raw PII into exports, reports, issues, or `DB_REFERENCE.md`.
- Capture exact error text when a query fails.
- Use the schema name from the structural export. RPC lookup tables commonly live under `lookup`, not `dbo`.

## What belongs in DB_REFERENCE.md

Good entries:

- Confirmed table purpose in RockPointe TouchPoint.
- Important IDs and lookup meanings.
- Declared and empirically confirmed join paths.
- Duplicate-row traps and safe `EXISTS` patterns.
- Null behavior that changes filters.
- Date/time storage behavior that changes reports.
- Explicit corrections to prior assumptions.

Do not add:

- Raw table/column inventory dumps.
- Person names, emails, phone numbers, addresses, task text, or attendance details.
- Generic TouchPoint guesses not confirmed against RPC.
- Platform/API behavior unrelated to database structure.

## Current evidence snapshot

The 2026-08-13 export confirmed:

- 505 tables/views
- 4,539 columns
- 457 primary-key columns
- 456 foreign-key columns
- 781 index-key columns
- 61 focused aggregate rows
- zero probe errors

See `reports/2026-08-13/` for human-readable summaries and `../DB_REFERENCE.md` for curated findings.
