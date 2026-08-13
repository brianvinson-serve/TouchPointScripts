# TouchPoint Development - RockPointe Church

Local development environment for TouchPoint scripts and automation.

## Projects

| Directory | Description |
|-----------|-------------|
| `outstanding-task-notifications/` | SM staff outstanding task email notification system |
| `attendance-dashboard/` | Attendance reporting dashboard |
| `data-dictionary-expander/` | Read-only exploratory SQL scripts for confirming TouchPoint table/column notes for `DB_REFERENCE.md` |

## Quick Start

### Outstanding Task Notifications
```bash
cd outstanding-task-notifications
./automation/deploy_scripts.sh status
./automation/deploy_scripts.sh validate
```

### API Testing
```bash
cd outstanding-task-notifications/api_test
python3 tp_api_test.py
```

### Data Dictionary Expander
```bash
cd data-dictionary-expander
open README.md
```

Use the SQL files there as copy/paste-one-query-at-a-time TouchPoint SQL Script diagnostics, then add only confirmed live RockPointe findings to `DB_REFERENCE.md`.

For a full refresh, deploy only `data-dictionary-expander/touchpoint/DataDictionary_Export.py` as a TouchPoint Python Script, download both PII-safe CSVs, and store them under a dated `exports/` directory. See `data-dictionary-expander/TESTING.md`.
