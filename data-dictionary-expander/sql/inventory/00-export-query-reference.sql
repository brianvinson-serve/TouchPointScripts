-- ============================================================
-- RockPointe TouchPoint - DataDictionary_Export query reference
--
-- These are the exact read-only SQL probes executed by
-- DataDictionary_Export.py. Run one block at a time only when diagnosing a
-- probe that the Python export marks ERROR.
-- ============================================================

/* Q01 - Collection metadata */
SELECT
    DB_NAME() AS DatabaseName,
    GETDATE() AS CollectedAt,
    @@VERSION AS SqlVersion

/* Q02 - Exposed tables and views */
SELECT
    TABLE_SCHEMA AS SchemaName,
    TABLE_NAME AS TableName,
    TABLE_TYPE AS ObjectType
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY TABLE_SCHEMA, TABLE_NAME

/* Q03 - Exposed columns */
SELECT
    TABLE_SCHEMA AS SchemaName,
    TABLE_NAME AS TableName,
    COLUMN_NAME AS ColumnName,
    ORDINAL_POSITION AS OrdinalPosition,
    DATA_TYPE AS DataType,
    CHARACTER_MAXIMUM_LENGTH AS MaxLength,
    NUMERIC_PRECISION AS NumericPrecision,
    NUMERIC_SCALE AS NumericScale,
    DATETIME_PRECISION AS DateTimePrecision,
    IS_NULLABLE AS Nullable
FROM INFORMATION_SCHEMA.COLUMNS
ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION

/* Q04 - Approximate table row counts; may be blocked in TouchPoint */
SELECT
    s.name AS SchemaName,
    o.name AS TableName,
    SUM(p.rows) AS ApproxRowCount
FROM sys.objects o
JOIN sys.schemas s ON s.schema_id = o.schema_id
JOIN sys.partitions p ON p.object_id = o.object_id
WHERE o.type = 'U'
  AND p.index_id IN (0, 1)
GROUP BY s.name, o.name
ORDER BY SUM(p.rows) DESC, s.name, o.name

/* Q05 - Primary keys */
SELECT
    tc.TABLE_SCHEMA AS SchemaName,
    tc.TABLE_NAME AS TableName,
    kcu.COLUMN_NAME AS ColumnName,
    tc.CONSTRAINT_NAME AS ConstraintName,
    tc.CONSTRAINT_TYPE AS ConstraintType,
    kcu.ORDINAL_POSITION AS KeyOrdinal
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
  ON kcu.CONSTRAINT_CATALOG = tc.CONSTRAINT_CATALOG
 AND kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
 AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
ORDER BY tc.TABLE_SCHEMA, tc.TABLE_NAME, kcu.ORDINAL_POSITION

/* Q06 - Foreign keys; may be blocked in TouchPoint */
SELECT
    OBJECT_SCHEMA_NAME(fkc.parent_object_id) AS SchemaName,
    OBJECT_NAME(fkc.parent_object_id) AS TableName,
    pc.name AS ColumnName,
    fk.name AS ConstraintName,
    fkc.constraint_column_id AS KeyOrdinal,
    OBJECT_SCHEMA_NAME(fkc.referenced_object_id) AS ReferencedSchema,
    OBJECT_NAME(fkc.referenced_object_id) AS ReferencedTable,
    rc.name AS ReferencedColumn
FROM sys.foreign_key_columns fkc
JOIN sys.foreign_keys fk
  ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns pc
  ON pc.object_id = fkc.parent_object_id
 AND pc.column_id = fkc.parent_column_id
JOIN sys.columns rc
  ON rc.object_id = fkc.referenced_object_id
 AND rc.column_id = fkc.referenced_column_id
ORDER BY
    OBJECT_SCHEMA_NAME(fkc.parent_object_id),
    OBJECT_NAME(fkc.parent_object_id),
    fk.name,
    fkc.constraint_column_id

/* Q07 - Index key columns; may be blocked in TouchPoint */
SELECT
    s.name AS SchemaName,
    o.name AS TableName,
    c.name AS ColumnName,
    i.name AS IndexName,
    i.is_unique AS IsUnique,
    i.is_primary_key AS IsPrimaryKey,
    ic.key_ordinal AS KeyOrdinal
FROM sys.indexes i
JOIN sys.objects o
  ON o.object_id = i.object_id
JOIN sys.schemas s
  ON s.schema_id = o.schema_id
JOIN sys.index_columns ic
  ON ic.object_id = i.object_id
 AND ic.index_id = i.index_id
JOIN sys.columns c
  ON c.object_id = ic.object_id
 AND c.column_id = ic.column_id
WHERE o.type = 'U'
  AND i.is_hypothetical = 0
  AND ic.is_included_column = 0
  AND ic.key_ordinal > 0
ORDER BY s.name, o.name, i.name, ic.key_ordinal
