-- ============================================================
-- Data Dictionary Expander - 05 Join Probe Templates
-- RockPointe TouchPoint ChMS
--
-- PURPOSE:
--   Confirm join paths and cardinality before documenting DB_REFERENCE.md
--   relationship notes or building reports.
--
-- IMPORTANT:
--   Run ONE query block at a time. Do not run this whole file at once.
--   All queries are read-only SELECTs.
--   These probes are designed to reveal duplicate-row traps.
-- ============================================================


/* ============================================================
   QUERY 1: Left join coverage probe.
   CONFIG:
     - Replace child/parent tables and join columns.
     - Example shown: OrganizationMembers -> People.
   Expected:
     - RowsWithoutParent should usually be 0 for a reliable join.
   ============================================================ */
SELECT
    COUNT(*) AS ChildRowCount,
    COUNT(p.PeopleId) AS RowsWithParent,
    COUNT(*) - COUNT(p.PeopleId) AS RowsWithoutParent
FROM dbo.OrganizationMembers om
LEFT JOIN dbo.People p
    ON p.PeopleId = om.PeopleId


/* ============================================================
   QUERY 2: Parent fan-out / duplicate-row risk probe.
   CONFIG:
     - Replace relationship table and parent key.
     - Example shown: Organizations can belong to multiple DivOrg rows.
   If MaxChildRowsPerParent > 1, a direct join can duplicate parent rows.
   ============================================================ */
SELECT
    COUNT(*) AS ParentCount,
    SUM(CASE WHEN x.ChildRows = 0 THEN 1 ELSE 0 END) AS ParentsWithNoChildren,
    SUM(CASE WHEN x.ChildRows = 1 THEN 1 ELSE 0 END) AS ParentsWithOneChild,
    SUM(CASE WHEN x.ChildRows > 1 THEN 1 ELSE 0 END) AS ParentsWithMultipleChildren,
    MAX(x.ChildRows) AS MaxChildRowsPerParent
FROM (
    SELECT
        o.OrganizationId,
        COUNT(d.OrgId) AS ChildRows
    FROM dbo.Organizations o
    LEFT JOIN dbo.DivOrg d
        ON d.OrgId = o.OrganizationId
    GROUP BY o.OrganizationId
) x


/* ============================================================
   QUERY 3: Show sample parent records that would duplicate on direct join.
   CONFIG: Replace Organizations/DivOrg example as needed.
   ============================================================ */
SELECT TOP 50
    o.OrganizationId,
    o.OrganizationName,
    COUNT(d.DivId) AS DivisionLinkCount
FROM dbo.Organizations o
JOIN dbo.DivOrg d
    ON d.OrgId = o.OrganizationId
GROUP BY
    o.OrganizationId,
    o.OrganizationName
HAVING COUNT(d.DivId) > 1
ORDER BY
    DivisionLinkCount DESC,
    o.OrganizationName


/* ============================================================
   QUERY 4: Compare direct join count vs EXISTS-filter count.
   CONFIG:
     - Example shown: active orgs in a program through DivOrg/Division.
   If DirectJoinRowCount > ExistsParentCount, document an EXISTS pattern.
   ============================================================ */
DECLARE @ProgramId INT = 1109

SELECT
    (SELECT COUNT(*)
     FROM dbo.Organizations o
     JOIN dbo.DivOrg d ON d.OrgId = o.OrganizationId
     JOIN dbo.Division dv ON dv.Id = d.DivId
     WHERE dv.ProgId = @ProgramId
       AND o.OrganizationStatusId = 30) AS DirectJoinRowCount,

    (SELECT COUNT(*)
     FROM dbo.Organizations o
     WHERE o.OrganizationStatusId = 30
       AND EXISTS (
           SELECT 1
           FROM dbo.DivOrg d
           JOIN dbo.Division dv ON dv.Id = d.DivId
           WHERE d.OrgId = o.OrganizationId
             AND dv.ProgId = @ProgramId
       )) AS ExistsParentCount


/* ============================================================
   QUERY 5: Candidate relationship coverage without parent PII.
   CONFIG:
     - Replace tables/columns after confirming each exists.
     - Return aggregate coverage only. Do not select person names or contact
       fields merely to prove an ID relationship.
   Example shown: TaskNote owner/assignee/about-person joins.
   ============================================================ */
SELECT
    COUNT(*) AS TaskRowCount,
    COUNT(tn.OwnerId) AS OwnerIdCount,
    COUNT(ownerPerson.PeopleId) AS OwnerJoinCount,
    COUNT(tn.AssigneeId) AS AssigneeIdCount,
    COUNT(assigneePerson.PeopleId) AS AssigneeJoinCount,
    COUNT(tn.AboutPersonId) AS AboutPersonIdCount,
    COUNT(aboutPerson.PeopleId) AS AboutPersonJoinCount
FROM dbo.TaskNote tn
LEFT JOIN dbo.People ownerPerson
    ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN dbo.People assigneePerson
    ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN dbo.People aboutPerson
    ON aboutPerson.PeopleId = tn.AboutPersonId


/* ============================================================
   QUERY 6: Lookup-table discovery for IDs.
   CONFIG:
     - Search for table/column names that might describe a known ID column.
     - Then run focused joins manually.
   ============================================================ */
DECLARE @SearchTerm VARCHAR(100) = '%Status%'

SELECT
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_NAME LIKE @SearchTerm
   OR c.COLUMN_NAME LIKE @SearchTerm
ORDER BY
    c.TABLE_NAME,
    c.ORDINAL_POSITION
