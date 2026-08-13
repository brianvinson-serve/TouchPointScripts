-- ============================================================
-- Data Dictionary Expander - 04 Column Profile Templates
-- RockPointe TouchPoint ChMS
--
-- PURPOSE:
--   Profile one column at a time for null behavior, distinct values,
--   status/type IDs, dates, and PII-safe examples.
--
-- IMPORTANT:
--   Run ONE query block at a time. Do not run this whole file at once.
--   All queries are read-only SELECTs.
--   Replace table/column names only after confirming them with 02-table-column-inventory.sql.
-- ============================================================


/* ============================================================
   QUERY 1: Basic null/distinct profile for one column.
   CONFIG: Replace dbo.TaskNote and StatusId.
   ============================================================ */
SELECT
    COUNT(*) AS RowCount,
    COUNT(StatusId) AS NonNullCount,
    COUNT(*) - COUNT(StatusId) AS NullCount,
    COUNT(DISTINCT StatusId) AS DistinctValueCount
FROM dbo.TaskNote


/* ============================================================
   QUERY 2: Top values for a status/type/category column.
   CONFIG: Replace dbo.TaskNote and StatusId.
   Good for: StatusId, OrganizationTypeId, MemberTypeId, OrganizationStatusId.
   ============================================================ */
SELECT TOP 100
    StatusId,
    COUNT(*) AS RowCount
FROM dbo.TaskNote
GROUP BY StatusId
ORDER BY
    RowCount DESC,
    StatusId


/* ============================================================
   QUERY 3: Top values with a human-readable label CASE block.
   CONFIG:
     - Replace dbo.TaskNote and StatusId.
     - Edit CASE labels only after confirming values elsewhere.
   ============================================================ */
SELECT TOP 100
    StatusId,
    CASE StatusId
        WHEN 1 THEN 'Complete'
        WHEN 2 THEN 'Pending'
        WHEN 3 THEN 'Active'
        WHEN 4 THEN 'Declined'
        WHEN 5 THEN 'Archived'
        WHEN 6 THEN 'Cancelled'
        ELSE 'Unconfirmed/Other'
    END AS StatusLabel,
    COUNT(*) AS RowCount
FROM dbo.TaskNote
GROUP BY StatusId
ORDER BY
    StatusId


/* ============================================================
   QUERY 4: Boolean/bit/null behavior profile.
   CONFIG: Replace dbo.TaskNote and IsNote.
   Useful when 0 vs NULL behavior changes filters.
   ============================================================ */
SELECT
    CASE
        WHEN IsNote IS NULL THEN 'NULL'
        ELSE CAST(IsNote AS VARCHAR(20))
    END AS IsNoteValue,
    COUNT(*) AS RowCount
FROM dbo.TaskNote
GROUP BY
    CASE
        WHEN IsNote IS NULL THEN 'NULL'
        ELSE CAST(IsNote AS VARCHAR(20))
    END
ORDER BY IsNoteValue


/* ============================================================
   QUERY 5: Date/datetime storage profile.
   CONFIG: Replace dbo.Meetings and MeetingDate.
   Confirms whether the column includes time and which weekdays appear.
   ============================================================ */
SET DATEFIRST 7

SELECT
    MIN(MeetingDate) AS EarliestValue,
    MAX(MeetingDate) AS LatestValue,
    COUNT(*) AS RowCount,
    COUNT(CASE WHEN MeetingDate IS NULL THEN 1 END) AS NullCount,
    COUNT(DISTINCT CAST(MeetingDate AS DATE)) AS DistinctDateCount,
    COUNT(DISTINCT CONVERT(TIME, MeetingDate)) AS DistinctTimeCount
FROM dbo.Meetings


/* ============================================================
   QUERY 6: Day-of-week profile for a datetime column.
   CONFIG: Replace dbo.Meetings and MeetingDate.
   ============================================================ */
SET DATEFIRST 7

SELECT
    DATEPART(dw, MeetingDate) AS DayOfWeekNumber,
    DATENAME(weekday, MeetingDate) AS DayOfWeekName,
    COUNT(*) AS RowCount
FROM dbo.Meetings
WHERE MeetingDate IS NOT NULL
GROUP BY
    DATEPART(dw, MeetingDate),
    DATENAME(weekday, MeetingDate)
ORDER BY DayOfWeekNumber


/* ============================================================
   QUERY 7: PII-safe string column profile.
   CONFIG: Replace dbo.Organizations and OrganizationName.
   Notes:
     - For public-ish names like organizations, showing example values is OK.
     - For people/email/phone/address fields, do NOT paste examples into DB_REFERENCE.md.
   ============================================================ */
SELECT TOP 100
    LEFT(OrganizationName, 80) AS ExampleValue,
    COUNT(*) AS RowCount
FROM dbo.Organizations
WHERE OrganizationName IS NOT NULL
GROUP BY LEFT(OrganizationName, 80)
ORDER BY
    RowCount DESC,
    ExampleValue


/* ============================================================
   QUERY 8: Prefix/name-pattern profile.
   CONFIG: Replace dbo.Organizations and OrganizationName.
   Useful for confirming naming conventions before parsing names.
   ============================================================ */
SELECT TOP 100
    LEFT(OrganizationName, 10) AS NamePrefix,
    COUNT(*) AS RowCount
FROM dbo.Organizations
WHERE OrganizationName IS NOT NULL
GROUP BY LEFT(OrganizationName, 10)
ORDER BY RowCount DESC, NamePrefix
