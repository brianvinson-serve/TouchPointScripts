-- ============================================================
-- Data Dictionary Expander - 01 Table Inventory
-- RockPointe TouchPoint ChMS
--
-- PURPOSE:
--   Discover tables/views exposed to the TouchPoint SQL Script runner and
--   capture broad table notes for DB_REFERENCE.md.
--
-- IMPORTANT:
--   Run ONE query block at a time. Do not run this whole file at once.
--   All queries are read-only SELECTs.
-- ============================================================


/* ============================================================
   QUERY 1: List user tables/views exposed through INFORMATION_SCHEMA.
   Expected: table/view names and schema names.
   Notes for DB_REFERENCE.md:
     - Which object names exist.
     - Whether dbo prefix is required/accepted.
   ============================================================ */
SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    TABLE_TYPE
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY TABLE_SCHEMA, TABLE_NAME


/* ============================================================
   QUERY 2: Search for candidate tables by name.
   CONFIG: Change @NamePattern before running.
   Examples:
     '%Task%'
     '%Member%'
     '%Meeting%'
     '%Org%'
     '%Email%'
     '%Tag%'
   ============================================================ */
DECLARE @NamePattern VARCHAR(200) = '%Task%'

SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    TABLE_TYPE
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME LIKE @NamePattern
ORDER BY TABLE_NAME


/* ============================================================
   QUERY 3: Table list with column counts.
   Useful for prioritizing tables and detecting tiny lookup tables.
   ============================================================ */
SELECT
    t.TABLE_SCHEMA,
    t.TABLE_NAME,
    t.TABLE_TYPE,
    COUNT(c.COLUMN_NAME) AS ColumnCount
FROM INFORMATION_SCHEMA.TABLES t
LEFT JOIN INFORMATION_SCHEMA.COLUMNS c
    ON c.TABLE_SCHEMA = t.TABLE_SCHEMA
   AND c.TABLE_NAME = t.TABLE_NAME
WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
GROUP BY
    t.TABLE_SCHEMA,
    t.TABLE_NAME,
    t.TABLE_TYPE
ORDER BY
    t.TABLE_NAME


/* ============================================================
   QUERY 4: Approximate row counts from SQL Server metadata.
   This uses system metadata and may not be available in all TouchPoint contexts.
   If this errors, skip it and use QUERY 5 for individual tables.
   ============================================================ */
SELECT
    s.name AS SchemaName,
    o.name AS TableName,
    SUM(p.rows) AS ApproxRowCount
FROM sys.objects o
JOIN sys.schemas s
    ON s.schema_id = o.schema_id
JOIN sys.partitions p
    ON p.object_id = o.object_id
WHERE o.type IN ('U', 'V')
  AND p.index_id IN (0, 1)
GROUP BY
    s.name,
    o.name
ORDER BY
    ApproxRowCount DESC,
    o.name


/* ============================================================
   QUERY 5: Exact row count for one table.
   CONFIG: Replace dbo.People with the table being profiled.
   Keep this to one table at a time; COUNT(*) on huge tables can be slow.
   ============================================================ */
SELECT COUNT(*) AS RowCount
FROM dbo.People


/* ============================================================
   QUERY 6: Recent/error-safe sample of table names and columns matching a keyword.
   CONFIG: Change @ColumnPattern before running.
   Examples:
     '%Status%'
     '%Type%'
     '%Date%'
     '%PeopleId%'
     '%OrganizationId%'
   ============================================================ */
DECLARE @ColumnPattern VARCHAR(200) = '%Status%'

SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE @ColumnPattern
ORDER BY
    TABLE_NAME,
    ORDINAL_POSITION
