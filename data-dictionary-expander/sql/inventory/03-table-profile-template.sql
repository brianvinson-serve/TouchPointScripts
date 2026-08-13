-- ============================================================
-- Data Dictionary Expander - 03 Table Profile Template
-- RockPointe TouchPoint ChMS
--
-- PURPOSE:
--   Safely profile one table's row count, sample rows, date range,
--   and null behavior before adding confirmed notes to DB_REFERENCE.md.
--
-- IMPORTANT:
--   Run ONE query block at a time. Do not run this whole file at once.
--   All queries are read-only SELECTs.
--   Replace dbo.TaskNote with the table being profiled.
-- ============================================================


/* ============================================================
   QUERY 1: Exact row count for the table.
   CONFIG: Replace dbo.TaskNote.
   ============================================================ */
SELECT COUNT(*) AS RowCount
FROM dbo.TaskNote


/* ============================================================
   QUERY 2: Small non-PII sample without assuming an Id/key column.
   CONFIG:
     - Replace dbo.TaskNote.
     - Replace selected columns with confirmed columns from 02-table-column-inventory.sql.
     - Keep TOP small.
     - Select only IDs, lookup/status values, flags, and dates. Never include
       names, contact fields, addresses, free text, notes, or instructions.
   ============================================================ */
SELECT TOP 25
    OwnerId,
    AssigneeId,
    AboutPersonId,
    StatusId,
    CreatedDate,
    DueDate,
    IsNote
FROM dbo.TaskNote
ORDER BY CreatedDate DESC


/* ============================================================
   QUERY 3: Null profile for manually selected columns.
   CONFIG:
     - Replace dbo.TaskNote.
     - Replace COUNT(CASE...) lines with columns being profiled.
   Notes:
     - This avoids dynamic SQL so it is easier to paste into TouchPoint.
   ============================================================ */
SELECT
    COUNT(*) AS RowCount,
    COUNT(CASE WHEN OwnerId IS NULL THEN 1 END) AS OwnerId_NullCount,
    COUNT(CASE WHEN AssigneeId IS NULL THEN 1 END) AS AssigneeId_NullCount,
    COUNT(CASE WHEN AboutPersonId IS NULL THEN 1 END) AS AboutPersonId_NullCount,
    COUNT(CASE WHEN StatusId IS NULL THEN 1 END) AS StatusId_NullCount,
    COUNT(CASE WHEN CreatedDate IS NULL THEN 1 END) AS CreatedDate_NullCount,
    COUNT(CASE WHEN DueDate IS NULL THEN 1 END) AS DueDate_NullCount,
    COUNT(CASE WHEN IsNote IS NULL THEN 1 END) AS IsNote_NullCount
FROM dbo.TaskNote


/* ============================================================
   QUERY 4: Date range profile.
   CONFIG:
     - Replace dbo.TaskNote.
     - Replace CreatedDate with the confirmed date/datetime column.
   ============================================================ */
SELECT
    MIN(CreatedDate) AS EarliestCreatedDate,
    MAX(CreatedDate) AS LatestCreatedDate,
    COUNT(*) AS RowCount,
    COUNT(CASE WHEN CreatedDate IS NULL THEN 1 END) AS CreatedDate_NullCount
FROM dbo.TaskNote


/* ============================================================
   QUERY 5: Recent activity by month.
   CONFIG:
     - Replace dbo.TaskNote.
     - Replace CreatedDate with the confirmed date/datetime column.
   ============================================================ */
SELECT TOP 36
    YEAR(CreatedDate) AS CreatedYear,
    MONTH(CreatedDate) AS CreatedMonth,
    COUNT(*) AS RowCount
FROM dbo.TaskNote
WHERE CreatedDate IS NOT NULL
GROUP BY
    YEAR(CreatedDate),
    MONTH(CreatedDate)
ORDER BY
    CreatedYear DESC,
    CreatedMonth DESC


/* ============================================================
   QUERY 6: Candidate key uniqueness probe.
   CONFIG:
     - Replace dbo.Organizations.
     - Replace OrganizationId with the candidate key column.
   Expected:
     - DistinctCandidateKeyCount equals NonNullCandidateKeyCount for a unique key.
   ============================================================ */
SELECT
    COUNT(*) AS RowCount,
    COUNT(OrganizationId) AS NonNullCandidateKeyCount,
    COUNT(DISTINCT OrganizationId) AS DistinctCandidateKeyCount,
    COUNT(*) - COUNT(OrganizationId) AS NullCandidateKeyCount
FROM dbo.Organizations
