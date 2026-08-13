-- SM_StaffTaskDashboard_Diagnostic_SingleQueries.sql
-- RockPointe Student Ministry Staff Task Dashboard SQL diagnostics
--
-- IMPORTANT:
--   TouchPoint's SQL runner may not tolerate multi-statement diagnostic scripts well.
--   Copy/paste and run ONE query at a time. Do not run this whole file at once.
--
-- Confirmed SM staff/volunteer PeopleIds:
--   46965 Isaac Jiles
--   659   Price Peden
--   284   Courtney Edmondson
--   23164 Joseph McCalley
--   1675  Libbie Risberg
--   40594 Haven Burton
--   36696 Joshua Watson
--   28000 Abbie Vinson
--   19570 Weston Watts
--   118   Shawn Adams
--
-- If a query errors, copy the exact error and the query number back to Kyle.


/* ============================================================
   QUERY 1: Does TaskNote expose the base columns the dashboard uses?
   Expected: One recent TaskNote row. This intentionally does not select a task ID;
   RPC TouchPoint returned "Invalid column name 'Id'" for TaskNote.Id.
   ============================================================ */
SELECT TOP 1
    tn.OwnerId,
    tn.AssigneeId,
    tn.AboutPersonId,
    tn.StatusId,
    tn.CreatedDate,
    tn.DueDate,
    tn.IsNote,
    tn.Instructions
FROM TaskNote tn
ORDER BY tn.CreatedDate DESC


/* ============================================================
   QUERY 2: Minimal outstanding TaskNote count for SM staff/volunteers.
   Expected: One row with TaskTotal. If this passes, base filtering works.
   ============================================================ */
SELECT
    COUNT(*) AS TaskTotal
FROM TaskNote tn
WHERE (
    tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
)
AND tn.StatusId IN (2, 3, 4)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)


/* ============================================================
   QUERY 3: Count TaskNote records by IsNote value for SM staff/volunteers.
   Expected: Shows whether tasks are NULL, 0, or 1.
   ============================================================ */
SELECT
    CASE
        WHEN tn.IsNote IS NULL THEN 'NULL'
        ELSE CAST(tn.IsNote AS VARCHAR(20))
    END AS IsNoteValue,
    COUNT(*) AS TaskTotal
FROM TaskNote tn
WHERE (
    tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
)
GROUP BY
    CASE
        WHEN tn.IsNote IS NULL THEN 'NULL'
        ELSE CAST(tn.IsNote AS VARCHAR(20))
    END
ORDER BY IsNoteValue


/* ============================================================
   QUERY 4: Count outstanding SM staff/volunteer tasks by status.
   Expected: Rows for Pending, Active, and/or Declined if tasks exist.
   ============================================================ */
SELECT
    tn.StatusId,
    CASE tn.StatusId
        WHEN 1 THEN 'Complete'
        WHEN 2 THEN 'Pending'
        WHEN 3 THEN 'Active'
        WHEN 4 THEN 'Declined'
        WHEN 5 THEN 'Archived'
        WHEN 6 THEN 'Cancelled'
        ELSE 'Other'
    END AS StatusName,
    COUNT(*) AS TaskTotal
FROM TaskNote tn
WHERE (
    tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
)
AND tn.StatusId IN (2, 3, 4)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
GROUP BY tn.StatusId
ORDER BY tn.StatusId


/* ============================================================
   QUERY 5: Confirm SM staff PeopleIds resolve in People.
   Expected: 10 rows. Missing names indicate stale PeopleIds.
   Uses UNION ALL instead of table variables because TouchPoint is apparently picky.
   ============================================================ */
SELECT
    staff.PeopleId,
    staff.ExpectedName,
    COALESCE(p.NickName, p.FirstName) AS GoesBy,
    p.LastName,
    p.EmailAddress
FROM (
    SELECT 46965 AS PeopleId, 'Isaac Jiles' AS ExpectedName
    UNION ALL SELECT 659, 'Price Peden'
    UNION ALL SELECT 284, 'Courtney Edmondson'
    UNION ALL SELECT 23164, 'Joseph McCalley'
    UNION ALL SELECT 1675, 'Libbie Risberg'
    UNION ALL SELECT 40594, 'Haven Burton'
    UNION ALL SELECT 36696, 'Joshua Watson'
    UNION ALL SELECT 28000, 'Abbie Vinson'
    UNION ALL SELECT 19570, 'Weston Watts'
    UNION ALL SELECT 118, 'Shawn Adams'
) staff
LEFT JOIN People p ON p.PeopleId = staff.PeopleId
ORDER BY staff.ExpectedName


/* ============================================================
   QUERY 6: Can TaskNote join People for owner, assignee, and about-person?
   Expected: Up to 25 rows with joined names.
   ============================================================ */
SELECT TOP 25
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    tn.AssigneeId,
    COALESCE(assigneePerson.NickName, assigneePerson.FirstName) AS AssigneeFirst,
    assigneePerson.LastName AS AssigneeLast,
    tn.AboutPersonId,
    COALESCE(aboutPerson.NickName, aboutPerson.FirstName) AS AboutFirst,
    aboutPerson.LastName AS AboutLast,
    tn.StatusId,
    tn.CreatedDate,
    tn.DueDate,
    tn.IsNote
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN People aboutPerson ON aboutPerson.PeopleId = tn.AboutPersonId
WHERE (
    tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
)
ORDER BY tn.CreatedDate DESC


/* ============================================================
   QUERY 7: Dashboard detail query WITHOUT date math.
   Expected: Up to 100 dashboard candidate rows.
   If this passes but Query 8 fails, the problem is date math.
   ============================================================ */
SELECT TOP 100
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    tn.AssigneeId,
    COALESCE(assigneePerson.NickName, assigneePerson.FirstName) AS AssigneeFirst,
    assigneePerson.LastName AS AssigneeLast,
    tn.AboutPersonId,
    COALESCE(aboutPerson.NickName, aboutPerson.FirstName) AS AboutFirst,
    aboutPerson.LastName AS AboutLast,
    tn.StatusId,
    CASE tn.StatusId
        WHEN 2 THEN 'Pending'
        WHEN 3 THEN 'Active'
        WHEN 4 THEN 'Declined'
        ELSE CAST(tn.StatusId AS VARCHAR(20))
    END AS StatusName,
    tn.CreatedDate,
    tn.DueDate,
    tn.Instructions
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN People aboutPerson ON aboutPerson.PeopleId = tn.AboutPersonId
WHERE (
    tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
)
AND tn.StatusId IN (2, 3, 4)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
ORDER BY
    CASE WHEN tn.DueDate IS NULL THEN 1 ELSE 0 END,
    tn.DueDate ASC,
    tn.CreatedDate ASC


/* ============================================================
   QUERY 8: Dashboard detail query WITH date math.
   Expected: Up to 100 dashboard candidate rows with age/due calculations.
   If this fails, TouchPoint SQL dislikes one of the DATEDIFF/CAST expressions.
   ============================================================ */
SELECT TOP 100
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    tn.AssigneeId,
    COALESCE(assigneePerson.NickName, assigneePerson.FirstName) AS AssigneeFirst,
    assigneePerson.LastName AS AssigneeLast,
    tn.AboutPersonId,
    COALESCE(aboutPerson.NickName, aboutPerson.FirstName) AS AboutFirst,
    aboutPerson.LastName AS AboutLast,
    tn.StatusId,
    CASE tn.StatusId
        WHEN 2 THEN 'Pending'
        WHEN 3 THEN 'Active'
        WHEN 4 THEN 'Declined'
        ELSE CAST(tn.StatusId AS VARCHAR(20))
    END AS StatusName,
    tn.CreatedDate,
    tn.DueDate,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld,
    CASE
        WHEN tn.DueDate IS NULL THEN 0
        WHEN CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE) THEN 1
        ELSE 0
    END AS IsOverdue,
    DATEDIFF(day, CAST(GETDATE() AS DATE), CAST(tn.DueDate AS DATE)) AS DaysUntilDue,
    tn.Instructions
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN People aboutPerson ON aboutPerson.PeopleId = tn.AboutPersonId
WHERE (
    tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
)
AND tn.StatusId IN (2, 3, 4)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
ORDER BY
    CASE WHEN tn.DueDate IS NULL THEN 1 ELSE 0 END,
    tn.DueDate ASC,
    tn.CreatedDate ASC


/* ============================================================
   QUERY 9: Summary by owner.
   Expected: Counts grouped by owner.
   ============================================================ */
SELECT
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    COUNT(*) AS TaskTotal
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
WHERE tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
AND tn.StatusId IN (2, 3, 4)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
GROUP BY
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName),
    ownerPerson.LastName
ORDER BY TaskTotal DESC, ownerPerson.LastName


/* ============================================================
   QUERY 10: Summary by assignee.
   Expected: Counts grouped by assignee, including unassigned owner-held tasks.
   ============================================================ */
SELECT
    tn.AssigneeId,
    CASE
        WHEN tn.AssigneeId IS NULL THEN 'Unassigned'
        ELSE COALESCE(assigneePerson.NickName, assigneePerson.FirstName)
    END AS AssigneeFirst,
    CASE
        WHEN tn.AssigneeId IS NULL THEN 'Owner accountable'
        ELSE assigneePerson.LastName
    END AS AssigneeLast,
    COUNT(*) AS TaskTotal
FROM TaskNote tn
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
WHERE (
    tn.AssigneeId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118)
    OR (tn.AssigneeId IS NULL AND tn.OwnerId IN (46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118))
)
AND tn.StatusId IN (2, 3, 4)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
GROUP BY
    tn.AssigneeId,
    CASE
        WHEN tn.AssigneeId IS NULL THEN 'Unassigned'
        ELSE COALESCE(assigneePerson.NickName, assigneePerson.FirstName)
    END,
    CASE
        WHEN tn.AssigneeId IS NULL THEN 'Owner accountable'
        ELSE assigneePerson.LastName
    END
ORDER BY TaskTotal DESC, AssigneeLast
