-- ============================================================
-- Data Dictionary Expander - 02 Table Column Inventory
-- RockPointe TouchPoint ChMS
--
-- PURPOSE:
--   Confirm the exact columns, data types, nullability, and ordinal order
--   for a specific table before writing scripts or DB_REFERENCE.md notes.
--
-- IMPORTANT:
--   Run ONE query block at a time. Do not run this whole file at once.
--   All queries are read-only SELECTs.
-- ============================================================


/* ============================================================
   QUERY 1: Column inventory for one table.
   CONFIG: Set @TableName. Leave @SchemaName = 'dbo' unless query 1 fails.
   Examples: 'People', 'Organizations', 'Meetings', 'TaskNote', 'OrganizationMembers'
   ============================================================ */
DECLARE @SchemaName VARCHAR(128) = 'dbo'
DECLARE @TableName  VARCHAR(128) = 'TaskNote'

SELECT
    c.ORDINAL_POSITION,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.DATETIME_PRECISION,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_SCHEMA = @SchemaName
  AND c.TABLE_NAME = @TableName
ORDER BY c.ORDINAL_POSITION


/* ============================================================
   QUERY 2: Does a candidate column exist?
   CONFIG: Set @TableName and @ColumnName before running.
   Use before selecting columns that might not exist in TouchPoint's SQL surface.
   ============================================================ */
DECLARE @TableName  VARCHAR(128) = 'TaskNote'
DECLARE @ColumnName VARCHAR(128) = 'Id'

SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_NAME = @TableName
  AND c.COLUMN_NAME = @ColumnName
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME


/* ============================================================
   QUERY 3: Common column inventory for core TouchPoint tables.
   Use to compare naming conventions across known tables.
   ============================================================ */
SELECT
    c.TABLE_NAME,
    c.ORDINAL_POSITION,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_NAME IN (
    'People',
    'Organizations',
    'Division',
    'DivOrg',
    'OrganizationMembers',
    'Meetings',
    'OrgSchedule',
    'TaskNote'
)
ORDER BY
    c.TABLE_NAME,
    c.ORDINAL_POSITION


/* ============================================================
   QUERY 4: Find tables exposing a likely PeopleId join.
   Useful before documenting relationship paths.
   ============================================================ */
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.COLUMN_NAME IN (
    'PeopleId',
    'PersonId',
    'OwnerId',
    'AssigneeId',
    'AboutPersonId',
    'CreatedBy',
    'ModifiedBy'
)
ORDER BY
    c.TABLE_NAME,
    c.COLUMN_NAME


/* ============================================================
   QUERY 5: Find tables exposing a likely OrganizationId join.
   ============================================================ */
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.COLUMN_NAME IN (
    'OrganizationId',
    'OrgId',
    'DivId',
    'DivisionId',
    'ProgId'
)
ORDER BY
    c.TABLE_NAME,
    c.COLUMN_NAME


/* ============================================================
   QUERY 6: Find status/type/date columns in one table.
   CONFIG: Set @TableName.
   Good candidates for focused profiling in 04-column-profile-templates.sql.
   ============================================================ */
DECLARE @TableName VARCHAR(128) = 'Organizations'

SELECT
    c.ORDINAL_POSITION,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_NAME = @TableName
  AND (
        c.COLUMN_NAME LIKE '%Status%'
     OR c.COLUMN_NAME LIKE '%Type%'
     OR c.COLUMN_NAME LIKE '%Date%'
     OR c.COLUMN_NAME LIKE '%Id%'
  )
ORDER BY c.ORDINAL_POSITION
