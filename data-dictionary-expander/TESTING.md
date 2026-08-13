# Data Dictionary Export Testing

## TouchPoint deployment

- Type: Python Script
- TouchPoint path: `Admin > Advanced > Special Content > Python Scripts > +New`
- Script name: `DataDictionary_Export`
- Source: **`touchpoint/DataDictionary_Export.py`**
- Writes data: No. Every database probe is `SELECT`-only.

Do not paste anything under `local/` into TouchPoint. Those files are Python 3 command-line utilities for the Mac.

## Run and export

1. Replace the TouchPoint `DataDictionary_Export` script with the full contents of `touchpoint/DataDictionary_Export.py`.
2. Run it once.
3. Confirm the page shows:
   - structural probe status,
   - focused probe status,
   - **Download Structural CSV**, and
   - **Download Focused Confirmation CSV**.
4. It is acceptable for a blocked probe to show `ERROR`; the exporter records the error and continues. Investigate before treating that section as complete.
5. Download both CSV files.
6. Store them unchanged under `exports/YYYY-MM-DD/`.

Expected filenames:

```text
rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv
rockpointe-touchpoint-focused-confirmation-YYYY-MM-DD.csv
```

## Local validation

```bash
cd "/Users/praxen/RockPointe Dev/TouchPointScripts/data-dictionary-expander"

python3 local/parse_data_dictionary_export.py \
  exports/YYYY-MM-DD/rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv \
  --output reports/YYYY-MM-DD/structural-summary.md

python3 local/build_data_dictionary_sqlite.py \
  exports/YYYY-MM-DD/rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv \
  --focused exports/YYYY-MM-DD/rockpointe-touchpoint-focused-confirmation-YYYY-MM-DD.csv \
  --output generated/data-dictionary.sqlite
```

The SQLite database is generated and gitignored. CSV evidence and curated Markdown are durable sources.

## If a probe fails

1. Confirm the deployed source is the current `touchpoint/DataDictionary_Export.py` version.
2. Match the failed query ID to:
   - `sql/inventory/00-export-query-reference.sql`, or
   - `sql/focused/06-focused-live-confirmation.sql`.
3. Run only that query block in TouchPoint SQL Scripts.
4. Capture the exact query ID and error text.
5. Verify table schemas through the structural CSV rather than assuming `dbo`.
6. Do not weaken read-only/privacy protections to force a query through.

## Rollback

Delete or disable the `DataDictionary_Export` Python Special Content script. It creates no database records and changes no TouchPoint data.
