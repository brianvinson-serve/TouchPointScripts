# DB_REFERENCE Output Template

Use this after running the Data Dictionary Expander SQL scripts. Paste cleaned, confirmed notes into `../DB_REFERENCE.md`; do **not** paste raw query dumps or PII.

## Candidate DB_REFERENCE.md Entry

### `[TableName]`

Confirmed against RockPointe TouchPoint on: `YYYY-MM-DD`

Source queries:

- `data-dictionary-expander/[file].sql`, Query `N`
- TouchPoint SQL Script runner at `rockpointe.tpsdb.com`

Purpose / observed behavior:

- `[What this table appears to store in RockPointe TouchPoint.]`

Confirmed columns:

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `[ColumnName]` | `[DataType]` | `YES/NO` | `[Meaning, caveat, or join behavior.]` |

Confirmed IDs / values:

| Column | Value | Meaning | Evidence |
|--------|-------|---------|----------|
| `[StatusId]` | `[2]` | `[Pending]` | `[Observed count / docs / joined lookup]` |

Join patterns:

```sql
-- Confirmed safe join/filter pattern
SELECT ...
FROM dbo.[Table] t
WHERE EXISTS (
    SELECT 1
    FROM dbo.[LinkTable] lt
    WHERE lt.[Key] = t.[Key]
)
```

Pitfalls / failed assumptions:

- `[Column X does not exist in TouchPoint SQL surface.]`
- `[Direct join through Y duplicates rows; use EXISTS.]`
- `[NULL means active/task/current in practice, so filters must include IS NULL.]`

Privacy note:

- `[No raw person/email/phone/address values were copied into DB_REFERENCE.md.]`

Open questions:

- `[What still needs live confirmation.]`

## Compact entry format

Use this for small confirmations:

```markdown
### [TableName]
Confirmed YYYY-MM-DD via `data-dictionary-expander/[file].sql` Query N.

- Purpose: ...
- Key columns: `A`, `B`, `C`.
- Null behavior: ...
- Join pattern: ...
- Pitfall: ...
```
